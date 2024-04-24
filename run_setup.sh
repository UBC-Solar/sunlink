#!/bin/bash
# Note: This script is to be run
# on a server without Sunlink already existing.
# Get user confirmation to run setup
while true; do
    read -p "Confirm Setup Sunlink: (y/n): " confirmation
    case $confirmation in
        [Yy]* ) break;;
        [Nn]* ) exit;;
        * ) echo "Please enter (y/n).";;
    esac
done
# Update apt
echo "Updating apt..."
sudo apt update
sudo apt-get update
# install gnome terminal
sudo apt install gnome-terminal
# install docker
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
## install latest version of docker
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
# Clone Sunlink
echo -e "\nCloning Sunlink Repository\n"
git clone https://github.com/UBC-Solar/sunlink/tree/user/diegoarmstrong/nginx_configuration sunlink_test
# Change directory into sunlink
cd sunlink_test
echo -e "\nChanged directory to sunlink\n"
# Get user input for GRAFANA_ADMIN_USERNAME
read -p "Enter GRAFANA_ADMIN_USERNAME (empty for default): " GRAFANA_ADMIN_USERNAME
GRAFANA_ADMIN_USERNAME=${GRAFANA_ADMIN_USERNAME:-admin}
echo -e "GRAFANA_ADMIN_USERNAME set: $GRAFANA_ADMIN_USERNAME\n"
# Get user input for GRAFANA_ADMIN_PASSWORD
while true; do
    read -p "Enter GRAFANA_ADMIN_PASSWORD (minimum 8 characters) (empty for default): " GRAFANA_ADMIN_PASSWORD
    GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-new_password}
    length=${#GRAFANA_ADMIN_PASSWORD}
    if [[ $length -lt 8 ]]
    then
        echo -e "Enter a password with minimum 8 characters"
    else
        echo -e "GRAFANA_ADMIN_PASSWORD set: $GRAFANA_ADMIN_PASSWORD\n"
        break;
    fi
done
# Get user input for INFLUX_ADMIN_USERNAME
read -p "Enter INFLUX_ADMIN_USERNAME (empty for default): " INFLUX_ADMIN_USERNAME
INFLUX_ADMIN_USERNAME=${INFLUX_ADMIN_USERNAME:-admin}
echo -e "INFLUX_ADMIN_USERNAME set: $INFLUX_ADMIN_USERNAME\n"
# Get user input for INFLUX_ADMIN_PASSWORD
while true; do
    read -p "Enter INFLUX_ADMIN_PASSWORD (minimum 8 characters) (empty for default): " INFLUX_ADMIN_PASSWORD
    INFLUX_ADMIN_PASSWORD=${INFLUX_ADMIN_PASSWORD:-new_password}
    length=${#INFLUX_ADMIN_PASSWORD}
    if [[ $length -lt 8 ]]
    then
        echo -e "Enter a password with minimum 8 characters"
    else
        echo -e "INFLUX_ADMIN_PASSWORD set: $INFLUX_ADMIN_PASSWORD\n"
        break;
    fi
done
# Secret key
SECRET_KEY="dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4"
# Access tokens currently empty
# Populate everything in .env
touch .env
echo -e "# Grafana environment variables\n" >> .env
echo -e "GRAFANA_ADMIN_USERNAME=\"$GRAFANA_ADMIN_USERNAME\"" >> .env
echo -e "GRAFANA_ADMIN_PASSWORD=\"$GRAFANA_ADMIN_PASSWORD\"\n" >> .env
echo -e "# InfluxDB environment variables\n" >> .env
echo -e "INFLUX_ADMIN_USERNAME=\"$INFLUX_ADMIN_USERNAME\"" >> .env
echo -e "INFLUX_ADMIN_PASSWORD=\"$INFLUX_ADMIN_PASSWORD\"\n" >> .env
echo -e "INFLUX_ORG=\"UBC Solar\"\n" >> .env
echo -e "# used to store random data for debugging purposes" >> .env
echo -e "INFLUX_DEBUG_BUCKET=\"Debug\"\n" >> .env
echo -e "# used to store real data from the car" >> .env
echo -e "INFLUX_CAN_BUCKET=\"CAN\"\n" >> .env
echo -e "# Secret key\n" >> .env
echo -e "SECRET_KEY=\"dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4\"\n" >> .env
echo -e "# Access tokens\n" >> .env
echo -e "INFLUX_TOKEN=\"\"" >> .env
echo -e "GRAFANA_TOKEN=\"\"" >> .env
# Telemetry link configuration
touch telemetry.toml
echo -e "[parser]" >> telemetry.toml
echo -e "url = \"http://localhost:5000/\"\n" >> telemetry.toml
echo -e "[security]" >> telemetry.toml
echo -e "secret_key = \"$SECRET_KEY\"\n" >> telemetry.toml
echo -e "[offline]" >> telemetry.toml
echo -e "channel = \"can0\"" >> telemetry.toml
echo -e "channel = bitrate = \"500000\"" >> telemetry.toml
#sudo apt install nginx
# NGINX stuff
# sudo docker pull nginx:latest
# sudo docker run -v nginx/nginx.conf:/etc/nginx/nginx.conf:ro -d -p 80:80 nginx
# Starting the telemetry cluster
echo -e "\nStarting up docker containers. May take a few minutes...\n"
sudo docker compose up -d
# sudo ufw allow 'Nginx HTTP'
# sudo docker images # verify that pull worked
  #create, run, name, and specify ports for the container
# sudo ufw status
# systemctl status nginx # Checking if NGINX is up
sudo docker compose ps # Show all containers
# Update and install Certbot
# sudo apt update
# sudo apt install -y certbot python3-certbot-nginx
# # Setup SSL certificates for NGINX
# sudo certbot --nginx -d example.com -d www.example.com
# # Test automatic renewal
# sudo certbot renew --dry-run