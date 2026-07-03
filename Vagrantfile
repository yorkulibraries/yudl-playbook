# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.require_version ">= 2.0.1"

$appleSilicon = RUBY_PLATFORM.include?("darwin") && RbConfig::CONFIG["host_cpu"] == "arm64"

$cpus   = ENV.fetch("ISLANDORA_VAGRANT_CPUS", "4")
$memory = ENV.fetch("ISLANDORA_VAGRANT_MEMORY", "6156")
$hostname = ENV.fetch("ISLANDORA_VAGRANT_HOSTNAME", "yudl-dev")
$virtualBoxDescription = ENV.fetch("ISLANDORA_VAGRANT_VIRTUALBOXDESCRIPTION", "YUDL DEV")

# Available boxes are 'islandora/8', 'ubuntu/jammy64', and 'centos/7'.
# Use an Ubuntu base box to build a dev environment from scratch.
# Use 'islandora/8' if you just want to download a ready to run VM.
$defaultVagrantBox = $appleSilicon ? "bento/ubuntu-22.04" : "ubuntu/jammy64"
$vagrantBox = ENV.fetch("ISLANDORA_DISTRO", $defaultVagrantBox)

# Build the base box, defaults to install a machine with the existing one.
$buildBaseBox=ENV.fetch("YUDL_BUILD_BASE", "false").to_s.downcase == "true"
$useLocalBox = ENV.fetch("YUDL_USE_LOCAL_BOX", "false").to_s.downcase == "true"
$buildAll = ENV.fetch("YUDL_BUILD_ALL", $appleSilicon ? "true" : "false").to_s.downcase == "true"
$askVaultPass = ENV.fetch("YUDL_ASK_VAULT_PASS", "false").to_s.downcase == "true"
$localBoxName = ENV.fetch("YUDL_LOCAL_BOX_NAME", "yudl-base-local")

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
  if $buildBaseBox or $buildAll
    config.vm.box = $vagrantBox
  elsif $useLocalBox
    config.vm.box = $localBoxName
  elsif $appleSilicon
    config.vm.box = $vagrantBox
  else
    config.vm.box = "yorkulibraries/yudl-base"
  end

  if $appleSilicon
    config.vm.box_architecture = "arm64"
  end

  # Configure home directory
  home_dir = "/home/" + $vagrantUser

  # Configure sync directory
  config.vm.synced_folder ".", home_dir + "/islandora"
  config.vm.synced_folder "../yudl_customizations", home_dir + "/yudl_customizations"
  config.vm.synced_folder "../islandora_rewrite_drupal_url", home_dir + "/islandora_rewrite_drupal_url"

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
      ansible.galaxy_command = "ansible-galaxy install --force --role-file=%{role_file}"
      ansible.limit = "all"
      ansible.raw_arguments = "--ask-vault-pass" if $askVaultPass
      ansible.inventory_path = "inventory/dev"
      ansible.host_vars = {
        "all" => { "ansible_ssh_user" => $vagrantUser }
      }
      ansible.extra_vars = {
        "islandora_distro" => $vagrantBox,
        "yudl_build_base_box" => $buildBaseBox,
        "yudl_build_all" => $buildAll,
        "env" => "dev"
      }
    end
  end

end
