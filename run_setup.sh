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
# sudo apt update
# sudo apt-get update


# Clone Sunlink
echo -e "\nCloning Sunlink Repository\n"
# git clone https://github.com/UBC-Solar/sunlink.git


# Change directory into sunlink
cd sunlink
echo -e "\nChanged directory to sunlink\n"


# Set up .env
touch .env

# Get user input for GRAFANA_ADMIN_USERNAME
read -p "Enter GRAFANA_ADMIN_USERNAME (empty for default): " GRAFANA_ADMIN_USERNAME
GRAFANA_ADMIN_USERNAME=${GRAFANA_ADMIN_USERNAME:-admin}
echo -e "GRAFANA_ADMIN_USERNAME set: $GRAFANA_ADMIN_USERNAME\n"

# Get user input for GRAFANA_ADMIN_PASSWORD


# Get user input for INFLUX_ADMIN_USERNAME


# Get user input for INFLUX_ADMIN_PASSWORD


# Secret key
SECRET_KEY="dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4"


# Access tokens currently empty


# Populate everything else in .env



