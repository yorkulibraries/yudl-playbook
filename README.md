# YUDL Playbook
[![LICENSE](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](./LICENSE)

## Introduction

This is a collection of [Ansible](https://github.com/ansible/ansible) playbooks to build York University Digital Library. It is based off of the [Islandora Foundation's Playbook](https://github.com/Islandora-Devops/islandora-playbook).

This repository contains a collection of [Ansible](https://github.com/ansible/ansible) playbooks used to build York University Digital Library. It is based on the [Islandora Foundation's Playbook](https://github.com/Islandora-Devops/islandora-playbook).

## Use

### System Resources

By default, the virtual machine is allocated **4GB of RAM**. Ensure your host machine has enough available memory to support this.

You can override the **CPU** and **RAM** allocation by setting the `ISLANDORA_VAGRANT_CPUS` and `ISLANDORA_VAGRANT_MEMORY` environment variables.

For example, on an **Ubuntu host**, you can add the following lines to `~/.bashrc`:

```bash
export ISLANDORA_VAGRANT_CPUS=4
export ISLANDORA_VAGRANT_MEMORY=5040
```

### DEV

1. `ansible-galaxy install -r requirements.yml`
2. `vagrant up`

### PRODUCTION

1. `ansible-galaxy install -r requirements.yml`
2. `ansible-playbook --ask-vault-pass -i inventory/production playbook.yml -e "islandora_distro=ubuntu/focal64" --extra-vars "env=production"`

## Connect

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

## Base Box

### Building the base box:

```bash
YUDL_BUILD_BASE=true; vagrant up                  # Create a yudl base box off an Ubuntu base box.
vagrant package --output yudl-base.box            # Shut down the base box VM and export it.
```

The base box can be versioned and released via [HashiCorp](https://portal.cloud.hashicorp.com/vagrant/discover/yorkulibraries/yudl-base).
