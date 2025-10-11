# Ansible Role: Scyllaridae

An Ansible role that installs [Scyllaridae](https://github.com/Islandora/scyllaridae) microservices on:

* Ubuntu 18.04+
* Debian 10+
* CentOS/RHEL 8+

## Overview

This role installs the Scyllaridae binary and configures systemd services for derivative generation microservices that were migrated from the PHP-based Crayfish services. Scyllaridae provides Go-based microservices for:

* **Hypercube** - OCR text extraction service (port 8888)
* **Homarus** - Audio/video conversion service (port 8889) 
* **Houdini** - Image manipulation service (port 8890)
* **Crayfits** - FITS metadata extraction service (port 8891)

## Role Variables

Available variables are listed below, along with default values:

```yaml
# Scyllaridae version to install
scyllaridae_version: "5.1.0"

# Services to install and configure
scyllaridae_services:
  - Hypercube
  - Homarus
  - Houdini
  - Crayfits

# Installation directory
scyllaridae_install_dir: /opt/scyllaridae

# Log directory
scyllaridae_log_directory: /var/log/islandora

# Log level (debug, info, warn, error)
scyllaridae_log_level: info
```

**Service ports are defined in group_vars/all/scyllaridae.yml:**

```yaml
scyllaridae_services_config:
  Hypercube:
    port: 8888
    url: "http://localhost:8888"
  Homarus:
    port: 8889
    url: "http://localhost:8889"
  Houdini:
    port: 8890
    url: "http://localhost:8890"
  Crayfits:
    port: 8891
    url: "http://localhost:8891"
```

OS-dependent variables set in vars/* can be overridden if desired:

```yaml
# scyllaridae_user: scyllaridae
```

## Dependencies

This role installs the following system packages:

* tesseract-ocr (with language packs)
* ffmpeg
* poppler-utils

## Configuration

Each service gets its own:

* systemd service file (`scyllaridae-{service}.service`)
* configuration directory (`/opt/scyllaridae/{service}/`)
* YAML configuration file (`scyllaridae.yml`)
* command script (`cmd.sh`)
* log file (`/var/log/islandora/scyllaridae-{service}.log`)

## Environment Variables

Each service is configured with:

* `SCYLLARIDAE_PORT` - Service-specific port
* `SCYLLARIDAE_YML` - Path to service configuration file
* `SCYLLARIDAE_LOG_LEVEL` - Logging level

## Example Playbook

```yaml
- hosts: all
  roles:
    - Islandora-Devops.scyllaridae
```

## Integration with Other Roles

Service URLs are shared via group_vars and can be referenced by other roles (e.g., Alpaca):

```yaml
# In alpaca role
alpaca_houdini_base_url: "{{ scyllaridae_services_config.Houdini.url }}"
```

## License

MIT