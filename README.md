# YUDL Playbook
[![LICENSE](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](./LICENSE)

## Introduction

This is a collection of Ansible playbooks to build York University Digital Library. It is based off of the [Islandora Foundation's Playbook](https://github.com/Islandora-Devops/islandora-playbook).

## Use

### System Resources

By default the virtual machine that is built uses 4GB of RAM. Your host machine will need to be able to support the additional memory use. You can override the CPU and RAM allocation by creating `ISLANDORA_VAGRANT_CPUS` and `ISLANDORA_VAGRANT_MEMORY` environment variables and setting the values. For example, on an Ubuntu host you could add to `~/.bashrc`:

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

#### DEV

The default Drupal login details are:

  * username: admin
  * password: islandora

### MySQL

  * username: drupal8
  * password: islandora

You can connect to the machine via the browser at [http://localhost:8000](http://localhost:8000).

#### PRODUCTION

You can connect to the machine via the browser at [https://gamma.library.yorku.ca](https://gamma.library.yorku.ca).

### Fedora

#### DEV

The Fedora 6 REST API can be accessed at [http://localhost:8080/fcrepo/rest](http://localhost:8080/fcrepo/rest).

Authentication is done via [Syn](https://github.com/Islandora-CLAW/Syn) using [JWT](https://jwt.io) tokens.

#### PRODUCTION

The Fedora 5 REST API can be accessed at [http://beta.library.yorku.ca:8080/fcrepo/rest](http://beta.library.yorku.ca:8080/fcrepo/rest).

Authentication is done via [Syn](https://github.com/Islandora-CLAW/Syn) using [JWT](https://jwt.io) tokens.

### Solr

#### DEV

You can access the Solr administration UI at http://localhost:8983/solr/

#### PRODUCTION

You can access the Solr administration UI at http://gamma.library.yorku.ca:8983/solr/

### ActiveMQ

#### DEV

The default ActiveMQ login details are:

  * username: admin
  * password: islandora

You can access the ActiveMQ administrative interface at: http://localhost:8161/admin

#### PRODUCTION

You can access the ActiveMQ administrative interface at: http://beta.library.yorku.ca:8161/admin

### Cantaloupe

#### DEV

You can access the Cantaloupe admin interface at: http://localhost:8080/cantaloupe/admin

  * username: admin
  * password: islandora

You can access the IIIF interface at: http://localhost:8080/cantaloupe/iiif/2/

#### PRODUCTION

You can access the Cantaloupe admin interface at: http://gamma.library.yorku.ca:8080/cantaloupe/admin

You can access the IIIF interface at: http://gamma.library.yorku.ca:8080/cantaloupe/iiif/2

### JWT

Islandora 8 uses JWT for authentication across the stack. Crayfish microservices, Fedora, and Drupal all use them. 
Crayfish and Fedora have been set up to use a default token of `islandora` to make testing easier. To use it, just set
the following header in HTTP requests:

  * `Authorization: Bearer islandora`
  
### FITS

#### DEV

You can access the FITS Web Service at http://localhost:8080/fits/

#### PRODUCTION

You can access the FITS Web Service at http://beta.library.yorku.ca:8080/fits/
