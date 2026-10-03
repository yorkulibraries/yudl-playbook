# YUDL Playbook
[![LICENSE](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](./LICENSE)

## Introduction

This repository contains a collection of [Ansible](https://github.com/ansible/ansible) playbooks used to build York University Digital Library. It is based on the [Islandora Foundation's Playbook](https://github.com/Islandora-Devops/islandora-playbook).

## Use

### Requirements

* [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/index.html)
* [Multipass](https://canonical.com/multipass/install) (Linux, macOS including Apple Silicon, or Windows)

### System Resources

By default, the dev VM is allocated **4 CPUs, 6156MB of RAM, and a 40GB disk**. Ensure your host machine has enough available memory to support this.

You can override these by setting the `YUDL_VM_CPUS`, `YUDL_VM_MEMORY` (in MB), and `YUDL_VM_DISK` environment variables.

For example, on an **Ubuntu host**, you can add the following lines to `~/.bashrc`:

```bash
export YUDL_VM_CPUS=4
export YUDL_VM_MEMORY=5040
```

Other settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `YUDL_VM_NAME` | `yudl-dev` | Multipass instance name |
| `YUDL_UBUNTU_RELEASE` | `22.04` | Ubuntu release for the VM |
| `YUDL_ASK_VAULT_PASS` | `false` | Pass `--ask-vault-pass` to `ansible-playbook` |
| `YUDL_MOUNT` | `false` | Mount this repository in the VM at `/home/vagrant/islandora` |

### DEV

```bash
./dev.sh up
```

This creates an Ubuntu VM with Multipass and runs `playbook.yml` against it, installing the Galaxy roles from `requirements.yml` first. Run `./dev.sh help` for all commands.

To start over from scratch:

```bash
./dev.sh destroy && ./dev.sh up
```

To re-run the playbook against an existing VM, optionally passing extra arguments to `ansible-playbook`:

```bash
./dev.sh provision
./dev.sh provision -- --start-at-task="Get sample data"
```

### PRODUCTION

1. `ansible-galaxy install -r requirements.yml`
2. `ansible-playbook --ask-vault-pass -i inventory/production playbook.yml -e "islandora_distro=ubuntu/focal64" --extra-vars "env=production"`

## Connect

The dev VM has its own IP address (`./dev.sh ip`). To use the `localhost` URLs below, forward the ports in a separate terminal and leave it running:

```bash
./dev.sh forward
```

Otherwise, replace `localhost` with the VM's IP address.

To get a shell on the VM:

```bash
./dev.sh ssh
```

### Drupal

You can connect to the machine via the browser at [http://localhost:8000](http://localhost:8000).

The default Drupal login details are:

  * username: admin
  * password: islandora

### MySQL

  * username: drupal8
  * password: islandora

### Fedora

The Fedora REST API can be accessed at [http://localhost:8080/fcrepo/rest](http://localhost:8080/fcrepo/rest).

Authentication is done via [Syn](https://github.com/Islandora-CLAW/Syn) using [JWT](https://jwt.io) tokens.

### Solr

You can access the Solr administration UI at http://localhost:8983/solr/

### ActiveMQ

The default ActiveMQ login details are:

  * username: admin
  * password: islandora

You can access the ActiveMQ administrative interface at: http://localhost:8161/admin

### Cantaloupe

You can access the Cantaloupe admin interface at: http://localhost:8080/cantaloupe/admin

  * username: admin
  * password: islandora

You can access the IIIF interface at: http://localhost:8080/cantaloupe/iiif/2/

### JWT

Islandora uses JWT for authentication across the stack. Crayfish microservices, Fedora, and Drupal all use them.
Crayfish and Fedora have been set up to use a default token of `islandora` to make testing easier. To use it, just set
the following header in HTTP requests:

  * `Authorization: Bearer islandora`

### FITS

You can access the FITS Web Service at http://localhost:8080/fits/

## Base snapshot

Snapshots replace the old base box. Build the generic stack once, snapshot it, and reset to it whenever you want a fresh YUDL layer:

```bash
./dev.sh up --base   # Build the generic stack, snapshot it as "base", then apply the YUDL layer.
./dev.sh reset       # Restore "base" and re-apply only the YUDL layer.
```

Snapshots are also useful for rehearsing upgrades:

```bash
./dev.sh snapshot pre-upgrade
./dev.sh provision            # try the upgrade
./dev.sh restore pre-upgrade  # roll back and try again
```

Snapshots are local to your machine. Taking or restoring one briefly stops the VM. Snapshots require Multipass 1.13 or newer.

## Vagrant equivalents

The dev environment used to run on Vagrant. `dev.sh` replaces it:

| Vagrant | dev.sh |
| --- | --- |
| `vagrant up` | `./dev.sh up` |
| `YUDL_BUILD_ALL=true vagrant up` | `./dev.sh up` (always builds everything) |
| `YUDL_BUILD_BASE=true vagrant up` + `vagrant package` | `./dev.sh up --base` |
| `vagrant provision` | `./dev.sh provision` (or `--yudl-only` for just the YUDL layer) |
| `vagrant ssh` | `./dev.sh ssh` |
| `vagrant halt` | `./dev.sh stop` |
| `vagrant up` (on a stopped VM) | `./dev.sh start` |
| `vagrant destroy` | `./dev.sh destroy` |
| `vagrant status` | `./dev.sh status` |
| `vagrant snapshot save/restore` | `./dev.sh snapshot <name>` / `./dev.sh restore <name>` |
| Forwarded ports (8000, 8080, …) | `./dev.sh forward`, or the VM's IP (`./dev.sh ip`) |
| Synced folder `/home/vagrant/islandora` | `YUDL_MOUNT=true ./dev.sh up` |
| `ISLANDORA_VAGRANT_CPUS` / `_MEMORY` / `_HOSTNAME` | `YUDL_VM_CPUS` / `_MEMORY` / `_NAME` (the old names still work) |
| `YUDL_ASK_VAULT_PASS` | Unchanged |

Differences to be aware of:

* The VM still has a `vagrant` user, because the playbooks expect one. `./dev.sh ssh` logs in as that user. `multipass shell` logs in as `ubuntu` instead.
* There is no shared, downloadable base box. Each developer builds the stack locally once, with `./dev.sh up --base`.
* Some dev settings point at the VM's IP address. If Multipass assigns the VM a new IP after a restart, run `./dev.sh provision` again.
* State lives in `.multipass/` (SSH key, cloud-init file, generated inventory). It is gitignored.
