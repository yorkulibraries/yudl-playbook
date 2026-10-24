# YUDL Playbook
[![LICENSE](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](./LICENSE)

## Introduction

This repository contains a collection of [Ansible](https://github.com/ansible/ansible) playbooks used to build a dev instance of York University Digital Library. It is based on the [Islandora Foundation's Playbook](https://github.com/Islandora-Devops/islandora-playbook).

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

Ansible refuses to run when its output isn't a terminal or a blocking pipe, which is the case for commands run through some tools. If you see `Ansible requires blocking IO on stdin/stdout/stderr`, add `</dev/null 2>&1 | cat` to the end of the command.

## Dev Drupal site

The dev site is built from files in this repository rather than assembled module by module. The codebase and configuration come from production, so dev runs the same code and config as production.

| What | Where | Used by |
| --- | --- | --- |
| Drupal codebase | `files/drupal/composer.json`, `files/drupal/composer.lock` | `composer install` (`webserver.yml`) |
| Site configuration | `files/drupal/config/sync/` | `drush site:install --existing-config` |
| Taxonomy data | `files/drupal/migrate/*.csv` | the `islandora_defaults_*` migrations |
| Collections and sample objects | `files/workbench/*.csv` | Islandora Workbench (`yudl-configuration.yml`) |

### Codebase

`files/drupal/composer.json` is production's, plus `yudl_customizations`. It also installs our forks of `group_solr`, `openseadragon`, and `yudl_groups` from our GitHub repositories. The theme, `york_drupal_theme`, comes from Packagist, so the playbook no longer git-clones Drupal code.

Update dependencies with `./dev.sh composer`. It runs Composer in the VM against a copy of `files/drupal/` and copies the updated `composer.json` and `composer.lock` back, without touching the VM's site. For example:

```bash
./dev.sh composer update --no-install drupal/core-recommended -W
./dev.sh composer require --no-install drupal/some_module:^1.0
```

The lock is only copied into a new build, so rebuild (`./dev.sh destroy && ./dev.sh up`) to test a lock change.

### Developing the theme and yudl_customizations

To work on `york_drupal_theme` or `yudl_customizations`, mount your local checkout over the copy Composer installed in the VM. Edits on your machine then show up in the dev site.

```bash
./dev.sh mount theme             # ../york_drupal_theme -> web/themes/custom/york_drupal_theme
./dev.sh mount customizations    # ../yudl_customizations -> web/modules/contrib/yudl_customizations
./dev.sh mounts                  # show what's mounted
./dev.sh unmount theme
```

The checkouts are expected next to this repository. To use another location, pass it as an argument (`./dev.sh mount theme ~/src/york_drupal_theme`), or set `YUDL_THEME_DIR` / `YUDL_CUSTOMIZATIONS_DIR`. `mount` checks the directory's `composer.json` name before mounting. It moves the Composer-installed copy to `/var/www/html/drupal/dev-mount-backups/<package>`, outside `web/` so Drupal doesn't find two copies of the extension, and `unmount` puts it back. Both rebuild Drupal's cache.

`mount` and `unmount` restart the VM: they stop it, add or remove the mount, start it, and wait for SSH and the database before rebuilding the cache. This takes about a minute and restarts the VM's services. The mounts are Multipass *native* mounts (`--type native`), which can only be changed while the VM is stopped. The default *classic* mounts use sshfs, which PHP's `RecursiveDirectoryIterator` sees as empty, so Drupal never finds a mounted theme, module, or Twig template. Native mounts stay in place across `./dev.sh stop` / `start`. Editing files in a mounted checkout doesn't need a restart.

Drupal caches aggregated CSS/JS, Twig templates, `.theme`/`.module` hooks, and services. After changing any of those, rebuild the cache:

```bash
./dev.sh drush cr
```

`./dev.sh drush <args>` runs any drush command in the VM's Drupal root.

`provision`, `up`, and `reset` refuse to run while anything is mounted. `composer install` could otherwise replace the mounted directory and delete files in your checkout. Unmount first.

Both packages track a branch (`dev-main` / `1.x-dev`), but a build installs the commit recorded in `composer.lock`. After pushing changes, update the lock so new builds pick them up:

```bash
./dev.sh composer update --no-install yorkulibraries/york_drupal_theme
./dev.sh composer update --no-install yorkulibraries/yudl_customizations
```

### Configuration

`files/drupal/config/sync/` is an export of production's configuration (`drush config:export`), with these changes for dev:

* Production-only modules removed from `core.extension.yml` and their config deleted: `ldap_*`, `authorization`, `externalauth`, `captcha`, `turnstile`, `islandora_microservice_rewrite` (and `views.view.authmap`). This also removes the LDAP bind password and Turnstile key.
* Install profile changed from `standard` to `minimal` (`profile:` and the module list in `core.extension.yml`), since profiles with an install hook can't be installed from config. The `standard` dependency was removed from the three `rdf.mapping.*` files that declared one.
* Contact form recipients set to `dev@example.com`.
* `yudl_groups` and `yudl_default_content` removed from `core.extension.yml`; the playbook enables them later, in a fixed order (see [Known issues](#front-page-depends-on-node-ids)).
* The `islandora_defaults_*` migrations read their CSVs from `../migrate/`.

The build then overrides production-specific values: the broker URL, Solr server, IIIF server, and Matomo (disabled in `settings.php`).

To refresh it from production, export production's config, apply the changes above, check for secrets (`grep -rniE 'pass|secret|token|key_value'`), and replace `files/drupal/config/sync/`.

### Taxonomy data

`files/drupal/migrate/` holds the CSVs for the York taxonomy migrations (tags, rights, languages, places, people, subjects, and so on), formerly in `yudl_defaults`. Edit them here.

### Workbench data

`files/workbench/` holds the CSVs Workbench loads: the nine `yudl-collections-NN.csv` files (all environments) and the sample objects (`single`, `paged`, `collection-image`, `contact_categories`; dev only). They replace the Google Sheets the build used to read.

So the files keep working however many terms and nodes exist when Workbench runs, they avoid hardcoded IDs:

* Parents (`field_member_of`, `node_id`) are given as PIDs, e.g. `yul:asc`.
* `field_model`, `field_display_hints`, and `field_resource_type` use term names, e.g. `Collection`, `Open Seadragon`.

Before each Workbench run, `files/scripts/workbench_resolve_pids.py` replaces those with node and term IDs and writes `<name>.resolved.csv`, which the configs in `templates/` read. It fails the build if a PID or term name isn't found. Parents must be created by an earlier file, or earlier in the same file. Media use and Page model settings in the sample configs are looked up at run time.

Tests for the resolver:

```bash
python3 -m unittest tests/test_workbench_resolve_pids.py
```

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

## Known issues

### Front page depends on node IDs

`york_drupal_theme` renders the front page from `page--node--1.html.twig` and links its featured collections by production node IDs (`path('entity.node.canonical', {'node': 59})`, and so on). Production's two front-page search blocks (`block.block.york_drupal_theme_exposedformsolr_search_contentpage_1` and `block.block.exposedformsolr_search_contentpage_1_2`) are limited to the path `/node/1`.

Production's config also references taxonomy terms by ID. For example, the `explore` view's collections display filters on Islandora model terms 11 and 19 (Collection and Newspaper).

To match, the dev build creates terms and nodes in production's order:

1. Taxonomy terms: a "Mirador" display term (term 1, as on production; the `islandora_mirador` module itself isn't installed), `islandora_tags`, FITS tags, then the York migration.
2. `yudl_groups` is enabled after the migrations: its groups become `islandora_access` terms via `islandora_group`, and its default content becomes node 1.
3. The Workbench collections import creates nodes 2-142 with production's IDs, and the front page is set to `/node/1`.

Anything that creates a term or node earlier in the build will shift those IDs and break the front page and any views filtering by term.

To fix it properly:

* Rename the theme's `page--node--1.html.twig` to `page--front.html.twig`.
* Link featured collections by path alias instead of node ID.
* Change the two search blocks' visibility from `/node/1` to `<front>` (on production, then re-export the config).

After that, the module ordering in the playbook and the `Set YUDL front page` task no longer need to care about node IDs.
