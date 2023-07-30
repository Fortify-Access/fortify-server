#!/bin/bash

# Function to check if the OS is Ubuntu
is_ubuntu() {
    [[ -f /etc/lsb-release ]] && grep -qi "Ubuntu" /etc/lsb-release
}
# Function to check if the OS is CentOS
is_centos() {
    [[ -f /etc/centos-release ]] || grep -qi "CentOS" /etc/os-release
}
generate_token() {
    tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 64
}

# Install Docker on Ubuntu
install_docker_ubuntu() {
    sudo apt-get update
    sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo systemctl enable docker
}
# Install Docker on CentOS
install_docker_centos() {
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
}

# Install Docker and pull Redis image based on OS
install_docker_and_redis() {
    echo "Pre-installation: Installing docker and redis..."
    if is_ubuntu; then
        install_docker_ubuntu
    elif is_centos; then
        install_docker_centos
    else
        echo "Unsupported OS. Only Ubuntu and CentOS are supported."
        exit 1
    fi

    # Pull Redis image
    sudo docker pull redis
    # Run Redis container with port 4323 mapped to 6379
    sudo docker run -d -p 4323:6379 --name redis-container redis
}

# Function to install the project
install_project() {
  # Step 1: Clone project and install requirements
  echo "Step 1: Cloning project and installing requirements..."
  cd /opt
  git clone https://github.com/Fortify-Access/fortify-server.git fortify-server
  cd fortify-server

  # Step 2: Installing python virtual environment packeages
  echo "Step 2: Installing python virtual environment packeages..."
  if is_ubuntu; then
      apt install -y python3.10-venv
  elif is_centos; then
      yum install -y python3.10-venv
  else
      echo "Unsupported OS. Only Ubuntu and CentOS are supported."
      exit 1
  fi

  # Step 3: Installing requirements
  echo "Step 3: Installing requirements..."
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt

  auth_key=$(generate_token)
  env_content=$(cat << EOF
    AUTH_KEY=$auth_key
    FORTIFY_SERVER_VERSION=1.0.0
    SINGBOX_VERSION=1.3.0
    EOF
  )
  echo "$env_content" > .env

  # Step 4: Downlaod and extract sing-box binary
  echo "Step 4: Downloading sing-box..."
  if [[ "$(uname -m)" == "x86_64" ]]; then
      package_url="https://github.com/SagerNet/sing-box/releases/download/v1.3.0/sing-box-1.3.0-linux-amd64.tar.gz"
  elif [[ "$(uname -m)" == "aarch64" ]]; then
      package_url="https://github.com/SagerNet/sing-box/releases/download/v1.3.0/sing-box-1.3.0-linux-arm64.tar.gz"
  else
      echo "Unsupported system architecture."
      exit 1
  fi

  # Step 5: Configure and start Starlette service
  echo "Step 5: Configuring and starting Starlette service..."
  cp /opt/fortify-server/services/fortify-server.service /etc/systemd/system/
  systemctl enable fortify-server.service
  systemctl start fortify-server.service
  
  # Step 6: Configure and start sing-box service
  echo "Step 6: Configuring and starting sing-box service..."
  cp /opt/fortify-server/services/singbox.service /etc/systemd/system/
  systemctl enable singbox.service
  systemctl start singbox.service

  # Step 7: Prepare package names
  echo "Step 7: Prepare package names..."
  package_name="singbox"
  # Download the latest release package (.tar.gz) from GitHub
  curl -sLo "/opt/fortify-server/${package_name}.tar.gz" $package_url
  # Extract the package and move the binary to /root
  tar -xzf "/opt/fortify-server/${package_name}.tar.gz" -C /opt/fortify-server
  # Cleanup the package
  rm -r "/opt/fortify-server/${package_name}.tar.gz"
  # Copy the default sing-box configuration file
  cp /opt/fortify-server/services/default_config.json /opt/fortify-server/singbox/config.json
}

# Step 8: Initialize the project
install_docker_and_redis
install_project
echo "Installation completed successfully."
echo -e "IMPORTANT:\nHere is your generated auth key to access this server:\n$auth_key\nCopy this key and paste it to your Fortify Assess panel."
