#!/bin/bash
# Note: This script is to be run on a CLONED copy of sunlink

# FORMATTING CONSTANTS
ANSI_RED="\033[0;31m"
ANSI_GREEN="\033[0;32m"
ANSI_YELLOW="\033[1;33m"
ANSI_BOLD="\033[1m"
ANSI_RESET="\033[0m"


while true; do
    # Prompt the user without -e (to avoid issues)
    echo -ne "${ANSI_BOLD}Confirm Setup Sunlink: (y/n): ${ANSI_RESET}"
    read confirmation

    case $confirmation in
        [Yy]* ) break;;
        [Nn]* ) exit;;
        * ) echo -e "${ANSI_YELLOW}Please enter (y/n). ${ANSI_RESET}";;
    esac
done


echo -e "${ANSI_BOLD}Updating apt... $ANSI_RESET"                 # Update apt
sudo apt update
sudo apt-get update
echo -e "${ANSI_GREEN}DONE updating apt! $ANSI_RESET"                          

echo -e "${ANSI_BOLD}Installing gnome terminal... $ANSI_RESET"                
sudo apt install gnome-terminal                                        # install gnome terminal
echo -e "${ANSI_GREEN}DONE installing gnome terminal! $ANSI_RESET"                          

echo -e "${ANSI_BOLD}Checking for docker installation. $ANSI_RESET"              
doInstall=true 
if [ -x "$(command -v docker)" ]; then                                 # Check if Docker is installed. If it is remove it. otherwise install
    echo -e "${ANSI_YELLOW}Found Docker Installation. Do you want to REINSTALL (y/n)? $ANSI_RESET"
    read reinstall
    case $reinstall in
        [Yy]* ) 
            echo -e "${ANSI_YELLOW}Removing Docker Installation $ANSI_RESET"
            sudo apt-get purge docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras
            sudo rm -rf /var/lib/docker
            sudo rm -rf /var/lib/containerd
            echo -e "${ANSI_YELLOW}DONE removing docker. Installing... $ANSI_RESET"
            ;;
        [Nn]* ) 
            doInstall=false
            ;;
        * ) echo -e "${ANSI_YELLOW}Please enter (y/n). ${ANSI_RESET}";;
    esac
else
    echo -e "${ANSI_YELLOW}Docker not installed. Installing now... $ANSI_RESET"
fi

if [ $doInstall = true ]; then
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
    echo -e "${ANSI_GREEN}DONE installing docker! $ANSI_RESET "
fi


echo -e "${ANSI_YELLOW}Setting up sunlink environment... $ANSI_RESET"                # Set up influx and grafana
SUNLINK_DIR=$PWD
# Get user input for GRAFANA_ADMIN_USERNAME
echo -ne "${ANSI_BOLD}Enter GRAFANA_ADMIN_USERNAME (empty for default): $ANSI_RESET" 
read GRAFANA_ADMIN_USERNAME
GRAFANA_ADMIN_USERNAME=${GRAFANA_ADMIN_USERNAME:-admin}
echo -e "${ANSI_GREEN}GRAFANA_ADMIN_USERNAME set: $GRAFANA_ADMIN_USERNAME $ANSI_RESET\n"
# Get user input for GRAFANA_ADMIN_PASSWORD
while true; do
    echo -ne "${ANSI_BOLD}Enter GRAFANA_ADMIN_PASSWORD (minimum 8 characters) (empty for default): $ANSI_RESET"
    read GRAFANA_ADMIN_PASSWORD
    GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-new_password}
    length=${#GRAFANA_ADMIN_PASSWORD}
    if [[ $length -lt 8 ]]
    then
        echo -e "${ANSI_YELLOW}Enter a password with minimum 8 characters $ANSI_RESET"
    else
        echo -e "${ANSI_GREEN}GRAFANA_ADMIN_PASSWORD set: $GRAFANA_ADMIN_PASSWORD\n $ANSI_RESET"
        break;
    fi
done

# Get user input for INFLUX_ADMIN_USERNAME
echo -ne "${ANSI_BOLD}Enter INFLUX_ADMIN_USERNAME (empty for default): $ANSI_RESET" 
read INFLUX_ADMIN_USERNAME
INFLUX_ADMIN_USERNAME=${INFLUX_ADMIN_USERNAME:-admin}
echo -e "${ANSI_GREEN}INFLUX_ADMIN_USERNAME set: $INFLUX_ADMIN_USERNAME\n $ANSI_RESET"
# Get user input for INFLUX_ADMIN_PASSWORD
while true; do
    echo -ne "${ANSI_BOLD}Enter INFLUX_ADMIN_PASSWORD (minimum 8 characters) (empty for default): $ANSI_RESET" 
    read INFLUX_ADMIN_PASSWORD
    INFLUX_ADMIN_PASSWORD=${INFLUX_ADMIN_PASSWORD:-new_password}
    length=${#INFLUX_ADMIN_PASSWORD}
    if [[ $length -lt 8 ]]
    then
        echo -e "${ANSI_YELLOW}Enter a password with minimum 8 characters $ANSI_RESET"
    else
        echo -e "${ANSI_GREEN}INFLUX_ADMIN_PASSWORD set: $INFLUX_ADMIN_PASSWORD\n $ANSI_RESET"
        break;
    fi
done

# Secret key
SECRET_KEY="dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4"
# Access tokens currently empty
# Populate everything in .env

echo -e "${ANSI_YELLOW}Creating new .env file... $ANSI_RESET"
touch .env
sudo rm -f .env
echo -e "# Grafana environment variables\n" >> .env
echo -e "GRAFANA_ADMIN_USERNAME=\"$GRAFANA_ADMIN_USERNAME\"" >> .env
echo -e "GRAFANA_ADMIN_PASSWORD=\"$GRAFANA_ADMIN_PASSWORD\"\n" >> .env
echo -e "# InfluxDB environment variables\n" >> .env
echo -e "INFLUX_ADMIN_USERNAME=\"$INFLUX_ADMIN_USERNAME\"" >> .env
echo -e "INFLUX_ADMIN_PASSWORD=\"$INFLUX_ADMIN_PASSWORD\"\n" >> .env
echo -e "INFLUX_ORG=\"UBC Solar\"\n" >> .env
echo -e "MESSAGE_TYPES=\"CAN,GPS,IMU\"\n" >> .env
echo -e "# Needed to Initialize InfluxDB" >> .env
echo -e "INFLUX_INIT_BUCKET=\"Init_test\"" >> .env
echo -e "INFLUX_DEBUG_BUCKET=\"Debug\"\n" >> .env
echo -e "DS_INFLUXDB=\"P951FEA4DE68E13C5\"\n" >> .env
echo -e "# Parser Secret key\n" >> .env
echo -e "SECRET_KEY=\"dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4\"\n" >> .env
echo -e "# Access tokens\n" >> .env
echo -e "INFLUX_TOKEN=\"\"" >> .env
echo -e "GRAFANA_TOKEN=\"\"" >> .env
echo -e "${ANSI_GREEN}DONE creating .env file! $ANSI_RESET"

# Telemetry link configuration
echo -e "${ANSI_YELLOW}Creating new telemetry.toml file... $ANSI_RESET"
touch telemetry.toml
sudo rm -f telemetry.toml
echo -e "[parser]" >> telemetry.toml
echo -e "url = \"http://localhost:5000/\"\n" >> telemetry.toml
echo -e "[security]" >> telemetry.toml
echo -e "secret_key = \"$SECRET_KEY\"\n" >> telemetry.toml
echo -e "[offline]" >> telemetry.toml
echo -e "channel = \"can0\"" >> telemetry.toml
echo -e "bitrate = \"500000\"" >> telemetry.toml
echo -e "${ANSI_GREEN}DONE creating telemetry.toml file! $ANSI_RESET"

#sudo apt install nginx
# NGINX stuff
# sudo docker pull nginx:latest
# sudo docker run -v nginx/nginx.conf:/etc/nginx/nginx.conf:ro -d -p 80:80 nginx
# Starting the telemetry cluster
echo -e "$ANSI_GREEN \nStarting up docker containers. May take a few minutes...\n $ANSI_RESET"
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


# Get API Token for Grafana
echo -e "\n\n"
echo -e "${ANSI_YELLOW}<--- INSTRUCTIONS FOR GETTING API TOKEN:${ANSI_GREEN} Grafana$ANSI_RESET --->$ANSI_RESET"
echo -e "${ANSI_BOLD}    1. Open a browser and go to 'http://localhost:3000' $ANSI_RESET"
echo -e "${ANSI_BOLD}    2. Log in with the credentials: Username: '$GRAFANA_ADMIN_USERNAME' and Password: '$GRAFANA_ADMIN_PASSWORD' $ANSI_RESET"
echo -e "${ANSI_BOLD}    3. Click on the 3 horizontal bar icon on the top left of the screen. $ANSI_RESET"
echo -e "${ANSI_BOLD}    4. Open 'Administration'. $ANSI_RESET"
echo -e "${ANSI_BOLD}    5. Click on 'Service accounts'. $ANSI_RESET"
echo -e "${ANSI_BOLD}    6. Click on 'Add service account'. $ANSI_RESET"
echo -e "${ANSI_BOLD}    7. Enter a display name and make role 'Admin'. Then click 'Create'. $ANSI_RESET"
echo -e "${ANSI_BOLD}    8. Click 'Add service account token' and enter a display name. Set No Expiration. Click 'Generate Token'.$ANSI_RESET"
echo -ne "${ANSI_BOLD}    9. Copy the token and ENTER THE GRAFANA API TOKEN HERE (Ctrl+Shift+V): $ANSI_RESET"
read GRAFANA_TOKEN

# Get API Token for InfluxDB
echo -e "\n\n"
echo -e "${ANSI_YELLOW}<--- INSTRUCTIONS FOR GETTING API TOKEN:${ANSI_GREEN} InfluxDB$ANSI_RESET --->$ANSI_RESET"
echo -e "${ANSI_BOLD}    1. Open a browser and go to 'http://localhost:8086' $ANSI_RESET"
echo -e "${ANSI_BOLD}    2. Log in with the credentials: Username: '$INFLUX_ADMIN_USERNAME' and Password: '$INFLUX_ADMIN_PASSWORD' $ANSI_RESET"
echo -e "${ANSI_BOLD}    3. Click on the up-arrow icon (under the 'U' icon) on the left side bar and select 'API Tokens'. $ANSI_RESET"
echo -e "${ANSI_BOLD}    4. Click on 'GENERATE API TOKEN' and select 'All Access API Token'. $ANSI_RESET"
echo -e "${ANSI_BOLD}    5. Enter a description and click 'Save'. $ANSI_RESET"
echo -ne "${ANSI_BOLD}    6. Copy the token and ENTER THE INFLUXDB API TOKEN HERE (Ctrl+Shift+V): $ANSI_RESET"
read INFLUX_TOKEN

# Enter API tokens into .env file
echo -e "${ANSI_YELLOW}Updating .env file with API tokens... $ANSI_RESET"
sed -i "s/INFLUX_TOKEN=\"\"/INFLUX_TOKEN=\"$INFLUX_TOKEN\"/g" .env
sed -i "s/GRAFANA_TOKEN=\"\"/GRAFANA_TOKEN=\"$GRAFANA_TOKEN\"/g" .env
echo -e "${ANSI_GREEN}DONE updating .env file with API tokens! $ANSI_RESET"


# Restart docker
echo -e "${ANSI_YELLOW}Restarting docker containers... $ANSI_RESET"
sudo docker compose down
sudo docker compose up -d

# Installing Kvaser linuxcan and kvlibsdk drivers
echo -ne "${ANSI_YELLOW}Do you want to install linuxcan and kvlibsdk (y/n)?: $ANSI_RESET"
read installKvaserLibs

case $installKvaserLibs in
    [Yy]* ) 
        echo -e "${ANSI_YELLOW}Installing Kvaser linuxcan and kvlibsdk drivers in ~/ directory... $ANSI_RESET"

        echo -e "${ANSI_bold}Installing LINUXCAN... $ANSI_RESET"
        sudo apt-get install pkg-config                                                         # Linuxcan first
        sudo apt-get install linux-headers-`uname -r` 
        sudo apt-get install build-essential 
        sudo wget -P ~ --content-disposition "https://www.kvaser.com/download/?utm_source=software&utm_ean=7330130980754&utm_status=latest"
        sudo tar -xzvf ~/linuxcan_*.tar.gz -C ~                                                  # not version dependent
        sudo rm -rfd ~/linuxcan_*.tar.gz
        echo -e "${ANSI_YELLOW}Changing directory to ~/linuxcan... $ANSI_RESET"
        cd ~/linuxcan
        sudo apt install --reinstall gcc-12
        sudo apt-get install zlib1g
        sudo apt-get install zlib1g-dev
        sudo apt-get install libxml2
        sudo apt-get install libxml2-dev
        make
        sudo make uninstall
        sudo make install  
        echo -e "${ANSI_GREEN}DONE installing  LINUXCAN! $ANSI_RESET"

        echo -e "${ANSI_BOLD}Installing KVLIBSDK... $ANSI_RESET"                                 # KVLIBSDK
        sudo wget -P ~ --content-disposition "https://resources.kvaser.com/PreProductionAssets/Product_Resources/kvlibsdk_5_45_724.tar.gz"
        sudo tar -xzvf ~/kvlibsdk_*.tar.gz -C ~                                                  # not version dependent
        sudo rm -rfd ~/kvlibsdk_*.tar.gz
        echo -e "${ANSI_YELLOW}Changing directory to ~/kvlibsdk... $ANSI_RESET"
        cd ~/kvlibsdk
        make
        sudo make install  
        echo -e "${ANSI_GREEN}DONE installing KVLIBSDK and LINUXCAN! $ANSI_RESET"
        echo -e "${ANSI_YELLOW}To uninstall. run 'sudo make uninstall' in both directories $ANSI_RESET"
        ;;
    [Nn]* ) 
        echo -e "${ANSI_YELLOW}Skipping Kvaser linuxcan and kvlibsdk drivers installation... $ANSI_RESET"
        ;;
    * ) echo -e "${ANSI_YELLOW}Please enter (y/n). ${ANSI_RESET}";;
esac

# Creating a python virtual environment. First check if venv is installed
echo -e "${ANSI_YELLOW}Changing directory to $SUNLINK_DIR $ANSI_RESET"
cd $SUNLINK_DIR

echo -e "${ANSI_YELLOW}Setting up virtual environment... $ANSI_RESET"
sudo apt-get install python3-venv
sudo python3 -m venv environment
sudo chmod -R a+rwx environment
echo -e "${ANSI_GREEN}DONE creating virtual environment! $ANSI_RESET"

echo -e "$ANSI_YELLOW Creating Influx Buckets... ${ANSI_RESET}"
sudo docker exec -it influxdb influx bucket create --name "CAN_test" --org "${DOCKER_INFLUXDB_INIT_ORG}"
echo -e "${ANSI_GREEN}BUCEKT: 'CAN_test' created$ANSI_RESET"
sudo docker exec -it influxdb influx bucket create --name "CAN_prod" --org "${DOCKER_INFLUXDB_INIT_ORG}"
echo -e "${ANSI_GREEN}BUCEKT: 'CAN_prod' created$ANSI_RESET"
sudo docker exec -it influxdb influx bucket create --name "CAN_log" --org "${DOCKER_INFLUXDB_INIT_ORG}"
echo -e "${ANSI_GREEN}BUCEKT: 'CAN_log' created$ANSI_RESET"

# Restarting docker
echo -e "${ANSI_YELLOW}Restarting docker containers one last time... $ANSI_RESET"
sudo docker compose down
sudo docker compose up -d

echo -e "\n\n"
echo -e "${ANSI_YELLOW}<---ALMOST COMPLETED SETTING UP SUNLINK. YOU NEED TO RUN THE FOLLOWING (Ctrl+Shift+C to copy) --->$ANSI_RESET"
echo -e "${ANSI_BOLD}    1. Run 'source environment/bin/activate' to activate the virtual environment $ANSI_RESET"
echo -e "${ANSI_BOLD}    2. Run 'pip install -r requirements.txt' to install all dependencies in environment $ANSI_RESET"
echo -e "${ANSI_BOLD}    3. Run 'sudo docker compose restart' to ensure up-to-date installation $ANSI_RESET"
echo -e "\n\n"
