# Ansible Role: Tomcat

An Ansible role that installs Tomcat 8 on:

* Ubuntu Xenial

## Role Variables

Available variables are listed below, along with default values:

Tomcat packages to install
```
tomcat_packages:
  - tomcat
```

Tomcat admin packages to install
```
tomcat_admin_packages:
  - tomcat-admin
```

Directory to install Tomcat into
```
tomcat_home: /var/lib/tomcat
```

Whether to install the Tomcat administrative interface
```
tomcat_admin_install: yes
```

Tomcat roles
```
tomcat_roles: []
```

Tomcat users
```
tomcat_users: []
```

User and group to run Tomcat as
```
tomcat_server_user: tomcat
tomcat_server_group: tomcat
```

Some OS-specific variables are set in vars/* but can be overridden
```
tomcat_home: /opt/tomcat
```

## Dependencies

  None

## Example Playbook

    - hosts: webservers
      roles:
        - { role: islandora.tomcat }

## License

MIT
