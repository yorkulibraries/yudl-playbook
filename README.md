# Islandora Playbook
[![LICENSE](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](./LICENSE)

## Introduction

This is an Ansible playbook for Islandora 8 for York University Libraries. It is based off of the [Islandora Foundation's Playbook](https://github.com/Islandora-Devops/islandora-playbook).

## Use

### DEV

1. `ansible-galaxy install -r requirements.yml`
2. `vagrant up` (`--ask-vault-pass` will be triggered, and the password is required)

## STAGING

1. `ansible-galaxy install -r requirements.yml`
2. `ansible-playbook --ask-vault-pass -i inventory/staging playbook.yml -e "islandora_distro=ubuntu/bionic64" --extra-vars "ansible_sudo_pass=somepassword"`

### PRODUCTION

Detailed installation and usage instructions can be found on the [official installation documentation for Islandora 8](https://islandora.github.io/documentation/installation/playbook/).

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

#### STAGING

You can connect to the machine via the browser at [http://omega.library.yorku.ca](http://omega.library.yorku.ca).

#### PRODUCTION

### Fedora

#### DEV

The Fedora 5 REST API can be accessed at [http://localhost:8080/fcrepo/rest](http://localhost:8080/fcrepo/rest).

Authentication is done via [Syn](https://github.com/Islandora-CLAW/Syn) using [JWT](https://jwt.io) tokens.

#### STAGING
The Fedora 5 REST API can be accessed at [http://omega.library.yorku.ca:8080/fcrepo/rest](http://localhost:8080/fcrepo/rest). 

Authentication is done via [Syn](https://github.com/Islandora-CLAW/Syn) using [JWT](https://jwt.io) tokens.

### Solr

#### DEV

You can access the Solr administration UI at http://localhost:8983/solr/

#### STAGING

You can access the Solr administration UI at http://omega.library.yorku.ca:8983/solr/

#### PRODUCTION

### ActiveMQ

#### DEV

The default ActiveMQ login details are:

  * username: admin
  * password: islandora

You can access the ActiveMQ administrative interface at: http://localhost:8161/admin

#### STAGING

You can access the ActiveMQ administrative interface at: http://omega.library.yorku.ca:8161/admin

#### PRODUCTION

### Cantaloupe

#### DEV

You can access the Cantaloupe admin interface at: http://localhost:8080/cantaloupe/admin

  * username: admin
  * password: islandora

You can access the IIIF interface at: http://localhost:8080/cantaloupe/iiif/2/

#### STAGING

You can access the Cantaloupe admin interface at: http://omega.library.yorku.ca:8080/cantaloupe/admin

You can access the IIIF interface at: http://omega.library.yorku.ca:8080/cantaloupe/iiif/2

#### PRODUCTION

### JWT

Islandora 8 uses JWT for authentication across the stack. Crayfish microservices, Fedora, and Drupal all use them. 
Crayfish and Fedora have been set up to use a default token of `islandora` to make testing easier. To use it, just set
the following header in HTTP requests:

  * `Authorization: Bearer islandora`
  
### BlazeGraph (Bigdata)

#### DEV

You can access the BlazeGraph interface at: http://localhost:8080/bigdata/

You have to select the islandora namespace in the [namespaces tab](http://localhost:8080/bigdata/#namespaces) before you can execute queries.

#### STAGING

You can access the BlazeGraph interface at: http://omega.library.yorku.ca:8080/bigdata/

You have to select the islandora namespace in the [namespaces tab](http://localhost:8080/bigdata/#namespaces) before you can execute queries.

#### PRODUCTION

### FITS

#### DEV

You can access the FITS Web Service at http://localhost:8080/fits/

#### STAGING

You can access the FITS Web Service at http://omega.library.yorku.ca:8080/fits/

#### PRODUCTION
