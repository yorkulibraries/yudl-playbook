# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.require_version ">= 2.0.1"

$cpus   = ENV.fetch("ISLANDORA_VAGRANT_CPUS", "4")
$memory = ENV.fetch("ISLANDORA_VAGRANT_MEMORY", "6156")
$hostname = ENV.fetch("ISLANDORA_VAGRANT_HOSTNAME", "yudl-dev")
$virtualBoxDescription = ENV.fetch("ISLANDORA_VAGRANT_VIRTUALBOXDESCRIPTION", "YUDL DEV")

# Available boxes are 'islandora/8', ubuntu/bionic64' and 'centos/7'
# Use 'ubuntu/bionic64' or 'centos/7' to build a dev environment from scratch.
# Use 'islandora/8' if you just want to download a ready to run VM.
$vagrantBox = ENV.fetch("ISLANDORA_DISTRO", "cloud-image/ubuntu-24.04")

# Build the base box, defaults to install a machine with the existing one.
$buildBaseBox=ENV.fetch("YUDL_BUILD_BASE", "false").to_s.downcase == "true"
$useLocalBox = ENV.fetch("YUDL_USE_LOCAL_BOX", "false").to_s.downcase == "true"
$localBoxName = ENV.fetch("YUDL_LOCAL_BOX_NAME", "yudl-base-local")

# Use local box for testing.
$localBaseBox = ENV.fetch("YUDL_LOCAL_BASE_BOX", "")

# vagrant is the main user
$vagrantUser = "vagrant"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.provider "virtualbox" do |v|
    if $buildBaseBox
      v.name = "YUDL Base Box"
    else
      v.name = "YUDL Dev Sandbox"
    end
  end

  config.vm.hostname = $hostname

  # Every Vagrant virtual environment requires a box to build off of.
  if $buildBaseBox
    config.vm.box = $vagrantBox
  elsif $useLocalBox
    config.vm.box = $localBoxName
  else
    if !$localBaseBox.empty?
      # Use local box file.
      config.vm.box = "yudl-base-local"
      config.vm.box_url = "file://#{$localBaseBox}"
    else
      config.vm.box = "yorkulibraries/yudl-base"
    end
  end

  # Configure home directory
  home_dir = "/home/" + $vagrantUser

  # Configure sync directory
  config.vm.synced_folder ".", home_dir + "/islandora"

  config.vm.network :forwarded_port, guest: 8000, host: 8000 # Apache
  config.vm.network :forwarded_port, guest: 8080, host: 8080 # Tomcat
  config.vm.network :forwarded_port, guest: 3306, host: 3306 # MySQL
  config.vm.network :forwarded_port, guest: 5432, host: 5432 # PostgreSQL
  config.vm.network :forwarded_port, guest: 8983, host: 8983 # Solr
  config.vm.network :forwarded_port, guest: 8161, host: 8161 # Activemq
  config.vm.network :forwarded_port, guest: 8081, host: 8081 # API-X
  config.vm.network :forwarded_port, guest: 8888, host: 8888 # scyllaridae (Hypercube)
  config.vm.network :forwarded_port, guest: 8889, host: 8889 # scyllaridae (Homarus)
  config.vm.network :forwarded_port, guest: 8890, host: 8890 # scyllaridae (Houdini)
  config.vm.network :forwarded_port, guest: 8891, host: 8891 # scyllaridae (Crayfits)

  config.vm.provider "virtualbox" do |vb|
    vb.customize ["modifyvm", :id, "--memory", $memory]
    vb.customize ["modifyvm", :id, "--cpus", $cpus]
    vb.customize ["modifyvm", :id, "--description", $virtualBoxDescription]
    vb.customize ["modifyvm", :id, "--audio", "none"]
    vb.customize ["modifyvm", :id, "--uart1", "0x3F8", "4"]
    vb.customize ["modifyvm", :id, "--uartmode1", "disconnected" ]
  end

  if $vagrantBox != "islandora/8" then
    config.vm.provision :ansible do |ansible|
      ansible.compatibility_mode = "auto"
      ansible.playbook = "playbook.yml"
      ansible.galaxy_role_file = "requirements.yml"
      ansible.galaxy_command = "ansible-galaxy install --role-file=%{role_file}"
      ansible.limit = "all"
      ansible.raw_arguments = "--ask-vault-pass"
      ansible.inventory_path = "inventory/dev"
      ansible.host_vars = {
        "all" => { "ansible_ssh_user" => $vagrantUser }
      }
      ansible.extra_vars = {
        "islandora_distro" => $vagrantBox,
        "yudl_build_base_box" => $buildBaseBox,
        "env" => "dev"
      }
    end
  end

end
