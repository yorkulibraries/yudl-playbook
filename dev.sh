#!/usr/bin/env bash
#
# Multipass-based YUDL dev environment (prototype replacement for the Vagrantfile).
#
# Creates an Ubuntu VM with Multipass, then runs the same playbook.yml against it
# using the inventory/dev group_vars. Run `./dev.sh help` for usage.
#
# Written for bash 3.2 so it runs unmodified on macOS.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$ROOT/.multipass"
INVENTORY_DIR="$STATE_DIR/inventory"
SSH_KEY="$STATE_DIR/id_ed25519"
CLOUD_INIT="$STATE_DIR/cloud-init.yaml"

# Fall back to the old Vagrant variable names so existing habits keep working.
VM_NAME="${YUDL_VM_NAME:-${ISLANDORA_VAGRANT_HOSTNAME:-yudl-dev}}"
CPUS="${YUDL_VM_CPUS:-${ISLANDORA_VAGRANT_CPUS:-4}}"
MEMORY="${YUDL_VM_MEMORY:-${ISLANDORA_VAGRANT_MEMORY:-6156}}"
DISK="${YUDL_VM_DISK:-40G}"
UBUNTU_RELEASE="${YUDL_UBUNTU_RELEASE:-22.04}"
ASK_VAULT_PASS="$(echo "${YUDL_ASK_VAULT_PASS:-false}" | tr '[:upper:]' '[:lower:]')"
MOUNT_REPO="$(echo "${YUDL_MOUNT:-false}" | tr '[:upper:]' '[:lower:]')"
DRUPAL_ROOT="/var/www/html/drupal"
# Packages './dev.sh mount' can replace with a local checkout.
DEV_PACKAGES="theme customizations"

# The playbooks hardcode vagrant_user: "vagrant", so keep that user name.
VM_USER="vagrant"

# Same ports the Vagrantfile forwarded.
FORWARD_PORTS="8000 8080 3306 5432 8983 8161 8081 8888 8889 8890 8891"

SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR)

usage() {
  cat <<EOF
Usage: ./dev.sh <command> [options]

Commands:
  up [--base]                 Create the VM and provision it.
                                default: build everything (like YUDL_BUILD_ALL=true)
                                --base:  build the generic stack, snapshot it as "base",
                                         then apply the YUDL layer on top
  provision [--yudl-only] [-- <ansible-playbook args>]
                              Re-run playbook.yml against the VM.
                                --yudl-only: only yudl-configuration.yml / yudl-theme.yml
                                e.g. ./dev.sh provision -- --start-at-task="Get sample data"
  snapshot <name>             Stop the VM and take a snapshot.
  restore <name>              Restore a snapshot (discards current state) and start the VM.
  reset                       Restore the "base" snapshot and re-apply the YUDL layer.
  snapshots                   List snapshots.
  ssh [cmd...]                SSH into the VM as $VM_USER.
  composer <args>             Run composer in the VM against files/drupal and copy the
                              updated composer.json/composer.lock back, e.g.
                                ./dev.sh composer update --no-install drupal/core-recommended -W
  mount <package> [dir]       Mount a local checkout over the composer-installed package
                              so host edits show up in Drupal. The installed copy is set
                              aside, not deleted. Packages (default local dir):
                                theme           ../york_drupal_theme  (\$YUDL_THEME_DIR)
                                customizations  ../yudl_customizations (\$YUDL_CUSTOMIZATIONS_DIR)
  unmount <package>           Unmount it and put the composer-installed copy back.
  mounts                      Show which packages are mounted from local checkouts.
  forward                     Forward the old Vagrant ports to localhost (runs until Ctrl-C).
  ip                          Print the VM's IP address.
  status                      Show Multipass info for the VM.
  stop | start                Stop or start the VM.
  destroy                     Delete and purge the VM.

Environment:
  YUDL_VM_NAME         (default: yudl-dev)
  YUDL_VM_CPUS         (default: 4)
  YUDL_VM_MEMORY       in MB (default: 6156)
  YUDL_VM_DISK         (default: 40G)
  YUDL_UBUNTU_RELEASE  (default: 22.04) - should match production
  YUDL_ASK_VAULT_PASS  true to pass --ask-vault-pass
  YUDL_MOUNT           true to mount this repo at /home/$VM_USER/islandora
  YUDL_THEME_DIR            local checkout for 'mount theme' (default: ../york_drupal_theme)
  YUDL_CUSTOMIZATIONS_DIR   local checkout for 'mount customizations' (default: ../yudl_customizations)
EOF
}

die() { echo "dev.sh: $*" >&2; exit 1; }
info() { echo "==> $*"; }

require() {
  command -v "$1" >/dev/null 2>&1 || die "'$1' not found. $2"
}

vm_exists() {
  multipass info "$VM_NAME" >/dev/null 2>&1
}

vm_ip() {
  multipass info "$VM_NAME" | awk '/IPv4/ { print $2; exit }'
}

ensure_key() {
  mkdir -p "$STATE_DIR"
  if [ ! -f "$SSH_KEY" ]; then
    info "Generating SSH key $SSH_KEY"
    ssh-keygen -q -t ed25519 -N "" -C "yudl-dev" -f "$SSH_KEY"
  fi
}

write_cloud_init() {
  cat >"$CLOUD_INIT" <<EOF
#cloud-config
users:
  - default
  - name: $VM_USER
    gecos: YUDL dev user
    shell: /bin/bash
    groups: [adm, sudo]
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - $(cat "$SSH_KEY.pub")
EOF
}

# Writes an inventory pointing at the VM. group_vars are symlinked from
# inventory/dev so dev settings stay in one place.
write_inventory() {
  local ip
  ip="$(vm_ip)"
  [ -n "$ip" ] || die "could not determine IP for $VM_NAME"

  mkdir -p "$INVENTORY_DIR"
  ln -sfn ../../inventory/dev/group_vars "$INVENTORY_DIR/group_vars"
  cat >"$INVENTORY_DIR/hosts" <<EOF
# Generated by dev.sh - do not edit.

default ansible_host=$ip ansible_user=$VM_USER ansible_ssh_private_key_file='$SSH_KEY' ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'

[alpaca]
default

[database]
default

[webserver]
default

[tomcat]
default

[solr]
default

[crayfish]
default
EOF
}

wait_for_ssh() {
  local ip tries=30
  ip="$(vm_ip)"
  info "Waiting for SSH on $ip"
  until ssh "${SSH_OPTS[@]}" -o ConnectTimeout=5 "$VM_USER@$ip" true 2>/dev/null; do
    tries=$((tries - 1))
    [ "$tries" -gt 0 ] || die "SSH to $VM_USER@$ip never came up"
    sleep 2
  done
}

mount_repo() {
  local uid gid
  uid="$(multipass exec "$VM_NAME" -- id -u "$VM_USER")"
  gid="$(multipass exec "$VM_NAME" -- id -g "$VM_USER")"
  info "Mounting $ROOT at /home/$VM_USER/islandora"
  multipass mount -u "$(id -u):$uid" -g "$(id -g):$gid" "$ROOT" "$VM_NAME:/home/$VM_USER/islandora"
}

# run_playbook <build_base> <build_all> [ansible-playbook args...]
run_playbook() {
  local build_base="$1" build_all="$2"
  shift 2

  require ansible-playbook "Install Ansible on this machine."
  # composer install could replace a mounted package's directory, which would
  # delete files in the local checkout through the mount.
  local pkg
  for pkg in $DEV_PACKAGES; do
    pkg_mounted "$pkg" && die "'$pkg' is mounted from a local checkout; run './dev.sh unmount $pkg' first."
  done
  write_inventory

  info "Installing Galaxy roles"
  (cd "$ROOT" && ansible-galaxy install --force --role-file=requirements.yml)

  local args=(-i "$INVENTORY_DIR" playbook.yml
    -e "islandora_distro=ubuntu/$UBUNTU_RELEASE"
    -e "yudl_build_base_box=$build_base"
    -e "yudl_build_all=$build_all"
    -e "env=dev")
  [ "$ASK_VAULT_PASS" = "true" ] && args+=(--ask-vault-pass)

  info "Running playbook.yml (base=$build_base, all=$build_all)"
  (cd "$ROOT" && ansible-playbook "${args[@]}" "$@")
}

take_snapshot() {
  local name="$1"
  info "Stopping $VM_NAME to snapshot it as '$name'"
  multipass stop "$VM_NAME"
  multipass snapshot --name "$name" "$VM_NAME"
  multipass start "$VM_NAME"
}

restore_snapshot() {
  local name="$1"
  info "Restoring $VM_NAME.$name"
  multipass stop "$VM_NAME"
  multipass restore --destructive "$VM_NAME.$name"
  multipass start "$VM_NAME"
  wait_for_ssh
}

cmd_up() {
  local base=false
  [ "${1:-}" = "--base" ] && base=true

  require multipass "See https://canonical.com/multipass/install"
  require ssh-keygen "Install OpenSSH."
  vm_exists && die "$VM_NAME already exists; use 'provision', or 'destroy' first."

  ensure_key
  write_cloud_init

  info "Launching $VM_NAME (Ubuntu $UBUNTU_RELEASE, ${CPUS} CPUs, ${MEMORY}M RAM, $DISK disk)"
  multipass launch "$UBUNTU_RELEASE" \
    --name "$VM_NAME" \
    --cpus "$CPUS" \
    --memory "${MEMORY}M" \
    --disk "$DISK" \
    --cloud-init "$CLOUD_INIT" \
    --timeout 900
  multipass exec "$VM_NAME" -- cloud-init status --wait >/dev/null

  [ "$MOUNT_REPO" = "true" ] && mount_repo
  wait_for_ssh

  if [ "$base" = "true" ]; then
    run_playbook true false
    take_snapshot base
    wait_for_ssh
    run_playbook false false
  else
    run_playbook false true
  fi

  info "Done. Drupal: http://$(vm_ip):8000  (or run './dev.sh forward' for http://localhost:8000)"
}

cmd_provision() {
  local build_all=true
  if [ "${1:-}" = "--yudl-only" ]; then
    build_all=false
    shift
  fi
  [ "${1:-}" = "--" ] && shift
  vm_exists || die "$VM_NAME does not exist; run './dev.sh up' first."
  run_playbook false "$build_all" "$@"
}

ssh_vm() {
  ssh "${SSH_OPTS[@]}" "$VM_USER@$(vm_ip)" "$@"
}

# Runs composer in the VM against a scratch copy of files/drupal, then copies
# composer.json and composer.lock back. The VM's Drupal install is untouched.
cmd_composer() {
  local src="$ROOT/files/drupal" dir=/tmp/yudl-composer
  [ $# -gt 0 ] || die "usage: ./dev.sh composer <composer args>"
  vm_exists || die "$VM_NAME does not exist; run './dev.sh up' first."

  info "Running 'composer $*' against files/drupal in $VM_NAME"
  ssh_vm "rm -rf $dir && mkdir -p $dir"
  ssh_vm "cat > $dir/composer.json" <"$src/composer.json"
  ssh_vm "cat > $dir/composer.lock" <"$src/composer.lock"
  ssh_vm "cd $dir && COMPOSER_MEMORY_LIMIT=-1 composer $(printf '%q ' "$@")"

  # Copy to temp files first so a failed transfer can't truncate the originals.
  ssh_vm "cat $dir/composer.json" >"$STATE_DIR/composer.json.new"
  ssh_vm "cat $dir/composer.lock" >"$STATE_DIR/composer.lock.new"
  mv "$STATE_DIR/composer.json.new" "$src/composer.json"
  mv "$STATE_DIR/composer.lock.new" "$src/composer.lock"
  info "Updated files/drupal/composer.json and composer.lock"
}

# pkg_info <package> <field>: vm_path | local_dir | composer_name
pkg_info() {
  case "$1:$2" in
    theme:vm_path) echo "$DRUPAL_ROOT/web/themes/custom/york_drupal_theme" ;;
    theme:local_dir) echo "${YUDL_THEME_DIR:-$ROOT/../york_drupal_theme}" ;;
    theme:composer_name) echo "yorkulibraries/york_drupal_theme" ;;
    customizations:vm_path) echo "$DRUPAL_ROOT/web/modules/contrib/yudl_customizations" ;;
    customizations:local_dir) echo "${YUDL_CUSTOMIZATIONS_DIR:-$ROOT/../yudl_customizations}" ;;
    customizations:composer_name) echo "yorkulibraries/yudl_customizations" ;;
    *) die "unknown package '$1' (choose from: $DEV_PACKAGES)" ;;
  esac
}

pkg_mounted() {
  vm_exists && multipass info "$VM_NAME" | grep -q "=> $(pkg_info "$1" vm_path)\$"
}

# Mounts a local checkout over a composer-installed package so edits on the
# host show up in Drupal immediately (after a cache rebuild for CSS/JS
# aggregation, Twig, PHP hooks and services). The installed copy is moved to
# <path>.composer meanwhile.
cmd_mount() {
  local pkg="${1:-}" dir vm_path name uid gid
  [ -n "$pkg" ] || die "usage: ./dev.sh mount <$(echo $DEV_PACKAGES | tr ' ' '|')> [dir]"
  vm_path="$(pkg_info "$pkg" vm_path)"
  name="$(pkg_info "$pkg" composer_name)"
  dir="${2:-$(pkg_info "$pkg" local_dir)}"
  vm_exists || die "$VM_NAME does not exist; run './dev.sh up' first."

  [ -d "$dir" ] || die "$dir does not exist."
  dir="$(cd "$dir" && pwd)"
  grep -q "\"name\": *\"$name\"" "$dir/composer.json" 2>/dev/null ||
    die "$dir doesn't look like $name (no matching composer.json name)."
  pkg_mounted "$pkg" && die "'$pkg' is already mounted; run './dev.sh unmount $pkg' first."

  ssh_vm "set -e
    if [ -e '$vm_path.composer' ]; then
      echo 'dev.sh: $vm_path.composer already exists; refusing to overwrite it.' >&2; exit 1
    fi
    sudo mv '$vm_path' '$vm_path.composer'
    sudo mkdir '$vm_path'"

  # Owned by the vagrant user in the VM (files stay world-readable for
  # Apache), and by you on the host.
  uid="$(multipass exec "$VM_NAME" -- id -u "$VM_USER")"
  gid="$(multipass exec "$VM_NAME" -- id -g "$VM_USER")"
  info "Mounting $dir at $vm_path"
  if ! multipass mount -u "$(id -u):$uid" -g "$(id -g):$gid" "$dir" "$VM_NAME:$vm_path"; then
    ssh_vm "sudo rmdir '$vm_path' && sudo mv '$vm_path.composer' '$vm_path'"
    die "mount failed; restored the composer-installed copy."
  fi
  ssh_vm "cd $DRUPAL_ROOT && vendor/bin/drush cr"
  info "Edit $dir. After CSS/JS/Twig/PHP changes run:"
  info "  ./dev.sh ssh -- 'cd $DRUPAL_ROOT && vendor/bin/drush cr'"
}

cmd_unmount() {
  local pkg="${1:-}" vm_path
  [ -n "$pkg" ] || die "usage: ./dev.sh unmount <$(echo $DEV_PACKAGES | tr ' ' '|')>"
  vm_path="$(pkg_info "$pkg" vm_path)"
  pkg_mounted "$pkg" || die "'$pkg' is not mounted."

  info "Unmounting $vm_path"
  multipass umount "$VM_NAME:$vm_path"
  ssh_vm "set -e
    sudo rmdir '$vm_path'
    sudo mv '$vm_path.composer' '$vm_path'
    cd $DRUPAL_ROOT && vendor/bin/drush cr"
  info "Restored the composer-installed $pkg."
}

cmd_mounts() {
  local pkg any=false
  vm_exists || die "$VM_NAME does not exist; run './dev.sh up' first."
  for pkg in $DEV_PACKAGES; do
    if pkg_mounted "$pkg"; then
      any=true
      printf '%-15s %s\n' "$pkg" "$(multipass info "$VM_NAME" | grep "=> $(pkg_info "$pkg" vm_path)\$" | sed 's/^ *Mounts: *//; s/^ *//')"
    else
      printf '%-15s %s\n' "$pkg" "composer-installed"
    fi
  done
}

cmd_forward() {
  local ip args=() port
  ip="$(vm_ip)"
  for port in $FORWARD_PORTS; do
    args+=(-L "$port:localhost:$port")
  done
  info "Forwarding ports $FORWARD_PORTS from $ip to localhost (Ctrl-C to stop)"
  ssh "${SSH_OPTS[@]}" -N "${args[@]}" "$VM_USER@$ip"
}

main() {
  local cmd="${1:-help}"
  [ $# -gt 0 ] && shift

  case "$cmd" in
    up) cmd_up "$@" ;;
    provision) cmd_provision "$@" ;;
    snapshot) [ -n "${1:-}" ] || die "snapshot needs a name"; take_snapshot "$1" ;;
    restore) [ -n "${1:-}" ] || die "restore needs a name"; restore_snapshot "$1" ;;
    reset) restore_snapshot base; run_playbook false false ;;
    snapshots) multipass list --snapshots ;;
    ssh) exec ssh "${SSH_OPTS[@]}" "$VM_USER@$(vm_ip)" "$@" ;;
    composer) cmd_composer "$@" ;;
    mount) cmd_mount "$@" ;;
    unmount | umount) cmd_unmount "$@" ;;
    mounts) cmd_mounts ;;
    forward) cmd_forward ;;
    ip) vm_ip ;;
    status) multipass info "$VM_NAME" ;;
    stop) multipass stop "$VM_NAME" ;;
    start) multipass start "$VM_NAME" ;;
    destroy) multipass delete --purge "$VM_NAME" ;;
    help | -h | --help) usage ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
