# Ansible Role: Cantaloupe

An Ansible role that installs [Cantaloupe](https://github.com/medusa-project/cantaloupe).

## Role Variables

Available variables are listed below, along with default values:

```
# Cantaloupe version
cantaloupe_version: 4.1.7
# Where to extract the cantaloupe archive
cantaloupe_install_root: /opt
# Target of a symlink from the extracted cantaloupe archive 
cantaloupe_symlink: /opt/cantaloupe
# Path to cantaloupe logs
cantaloupe_log_path: /var/log/cantaloupe
# Cantaloupe user
cantaloupe_user: cantaloupe
# Cantaloupe group
cantaloupe_group: cantaloupe

# Create the filesystem cache directory automatically
cantaloupe_create_FilesystemCache_dir: no
```

There are many more options available and documented in the [defaults/main.yml](defaults/main.yml)

## Dependencies

* Java
  
## Example Playbook

    - hosts: webservers
      roles:
        - { role: islandora.cantaloupe }

## License

MIT
