# Ansible Role: Riprap

An Ansible role that installs [Riprap](https://github.com/mjordan/riprap).

* Ubuntu Xenial

## Role Variables

Available variables are listed below, along with default values:

```
# defaults file for IslandoraDevops.riprap
riprap_home: /var/www/html
settings_dir: /var/www/html/drupal/web/sites/default
private_file_dir: /var/www/html/private
default_data_type: islandora_object
apache_restart_state: restarted
riprap_content_type: islandora_object
riprap_rest_endpoint:  'http://localhost:8000/api/fixity'
```

## Example Playbook

    - hosts: webservers
      roles:
        - { role: Islandora-Devops.riprap }

## License

MIT
