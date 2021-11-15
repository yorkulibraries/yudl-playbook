# Ansible Role: Fedora

An Ansible role that installs Fedora 5 in a Tomcat 8 servlet container on:

* Centos/RHEL 7.x
* Ubuntu Xenial

This role has been tested with Fedora 4.7.* and 5.*.*.

## Role Variables

Available variables are listed below, along with default values:

Version of Fedora to install
```
fcrepo_version: 6.0.0
```

User with permissions to install:
```
fcrepo_user: {{ tomcat8_server_user }}
```

A home directory for Fedora
```
fcrepo_home_dir: /opt/fcrepo
```

Where to put the Fedora war file
```
fcrepo_war_path: "{{ tomcat8_home }}/webapps/fcrepo.war"
```

The activemq configuration file template name
```
fcrepo_activemq_template: activemq.xml.j2
```

If either 'jdbc-mysql' or 'jdbc-postgres' are used for object persistence, the database settings
```
fcrepo_db_name: fcrepo
fcrepo_db_user: fcrepo
fcrepo_db_password: fcrepo
fcrepo_db_host: "127.0.0.1"
fcrepo_db_port: "3306"
```

Islandora uses the HeaderProvider to pass the users roles into Fedora. To use this you will need to set the below variable.

Header name to acquire roles from
```
fcrepo_auth_header_name:
```

Islandora takes advantage of fcrepo's external content feature.  To enable redirects / proxying, you need to configure:

Where the config file gets stored:
```
fcrepo_allowed_external_content_file: "{{ fcrepo_home_dir }}/allowed-external-content.txt"
```

What paths/urls to expose:
```
fcrepo_allowed_external_content:
  - http://localhost:8000/
```


## Dependencies

* islandora.tomcat8
 
## Example Playbook

    - hosts: webservers
      roles:
        - { role: islandora.fcrepo }

## License

MIT
