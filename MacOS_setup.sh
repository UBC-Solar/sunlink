#!/usr/bin/env bash
# Note: This script is intended to be run on macOS.
# It sets up Sunlink without Kvaser/linuxcan/kvlibsdk drivers.

set -e

# FORMATTING CONSTANTS
ANSI_RED="\033[0;31m"
ANSI_GREEN="\033[0;32m"
ANSI_YELLOW="\033[1;33m"
ANSI_BOLD="\033[1m"
ANSI_RESET="\033[0m"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo -e "${ANSI_BOLD}Checking macOS dependencies... $ANSI_RESET"

# Install Homebrew if missing
if ! command_exists brew; then
    echo -e "${ANSI_YELLOW}Homebrew not found. Installing Homebrew... $ANSI_RESET"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for Apple Silicon and Intel Macs
    if [ -x "/opt/homebrew/bin/brew" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x "/usr/local/bin/brew" ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
else
    echo -e "${ANSI_GREEN}Homebrew found! $ANSI_RESET"
fi

echo -e "${ANSI_BOLD}Updating Homebrew... $ANSI_RESET"
brew update
echo -e "${ANSI_GREEN}DONE updating Homebrew! $ANSI_RESET"

# Install basic dependencies
echo -e "${ANSI_BOLD}Installing required packages... $ANSI_RESET"
brew install git curl python docker docker-compose colima || true
echo -e "${ANSI_GREEN}DONE installing required packages! $ANSI_RESET"

# Start Docker engine through Colima if Docker is not currently running
echo -e "${ANSI_BOLD}Checking Docker... $ANSI_RESET"
if ! command_exists docker; then
    echo -e "${ANSI_RED}Docker CLI was not found after installation. Please check your Homebrew installation.$ANSI_RESET"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo -e "${ANSI_YELLOW}Docker daemon is not running. Starting Colima... $ANSI_RESET"
    colima start
else
    echo -e "${ANSI_GREEN}Docker is already running! $ANSI_RESET"
fi

# Check Docker Compose
if ! docker compose version >/dev/null 2>&1; then
    echo -e "${ANSI_YELLOW}Docker Compose plugin not found. Linking Homebrew docker-compose plugin... $ANSI_RESET"
    mkdir -p ~/.docker/cli-plugins
    ln -sf "$(brew --prefix)/opt/docker-compose/bin/docker-compose" ~/.docker/cli-plugins/docker-compose
fi

docker compose version
echo -e "${ANSI_GREEN}Docker and Docker Compose are ready! $ANSI_RESET"

# Clone Sunlink
echo -e "${ANSI_YELLOW}\nCloning Sunlink Repository\n $ANSI_RESET"
if [ -d "sunlink" ]; then
    echo -ne "${ANSI_YELLOW}A sunlink directory already exists. Use existing directory? (y/n): $ANSI_RESET"
    read useExisting
    case $useExisting in
        [Yy]* )
            cd sunlink
            ;;
        [Nn]* )
            echo -e "${ANSI_YELLOW}Removing existing sunlink directory and cloning fresh... $ANSI_RESET"
            rm -rf sunlink
            git clone https://github.com/UBC-Solar/sunlink.git sunlink
            cd sunlink
            ;;
        * )
            echo -e "${ANSI_RED}Please enter y or n. Exiting.$ANSI_RESET"
            exit 1
            ;;
    esac
else
    git clone https://github.com/UBC-Solar/sunlink.git sunlink
    cd sunlink
fi

echo -e "${ANSI_YELLOW}Setting up sunlink environment... $ANSI_RESET"

SUNLINK_DIR="$PWD"
GRAFANA_ADMIN_USERNAME=admin
GRAFANA_ADMIN_PASSWORD=new_password
INFLUX_ADMIN_USERNAME=admin
INFLUX_ADMIN_PASSWORD=new_password

# Secret key
SECRET_KEY="dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4"

# Populate everything in .env
echo -e "${ANSI_YELLOW}Creating new .env file... $ANSI_RESET"
rm -f .env
cat > .env <<EOF
# Grafana environment variables

GRAFANA_ADMIN_USERNAME="$GRAFANA_ADMIN_USERNAME"
GRAFANA_ADMIN_PASSWORD="$GRAFANA_ADMIN_PASSWORD"

# InfluxDB environment variables

INFLUX_ADMIN_USERNAME="$INFLUX_ADMIN_USERNAME"
INFLUX_ADMIN_PASSWORD="$INFLUX_ADMIN_PASSWORD"

INFLUX_ORG="UBC Solar"

MESSAGE_TYPES="CAN,GPS,IMU"

# Needed to Initialize InfluxDB
INFLUX_INIT_BUCKET="Init_test"
INFLUX_DEBUG_BUCKET="Debug"

DS_INFLUXDB="P951FEA4DE68E13C5"

# Parser Secret key

SECRET_KEY="$SECRET_KEY"

# Access tokens

INFLUX_TOKEN=""
GRAFANA_TOKEN=""

# gRPC cellular parser environment variables

USE_NOW_TIME="true"
POINT_BATCH_SIZE="1000"
FLUSH_INTERVAL_MS="1000"
GRPC_COMPRESSION="gzip"
INFLUX_URL="http://influxdb:8086"
GRPC_BIND="0.0.0.0:50051"
EOF
echo -e "${ANSI_GREEN}DONE creating .env file! $ANSI_RESET"

# Telemetry link configuration
echo -e "${ANSI_YELLOW}Creating new telemetry.toml file... $ANSI_RESET"
rm -f telemetry.toml
cat > telemetry.toml <<EOF
[parser]
url = "http://localhost:5000/"

[security]
secret_key = "$SECRET_KEY"

[offline]
channel = "can0"
bitrate = "500000"
EOF
echo -e "${ANSI_GREEN}DONE creating telemetry.toml file! $ANSI_RESET"

# Starting the telemetry cluster
echo -e "$ANSI_GREEN \nStarting up docker containers. This may take a few minutes...\n $ANSI_RESET"
docker compose up -d
docker compose ps

# Get API Token for Grafana
echo -e "\n\n"
echo -e "${ANSI_YELLOW}<--- READ THESE INSTRUCTIONS CAREFULLY FOR ${ANSI_GREEN} Grafana$ANSI_RESET TOKEN --->$ANSI_RESET"
echo -e "${ANSI_BOLD}    1. Open a browser and go to 'http://localhost:3000' $ANSI_RESET"
echo -e "${ANSI_BOLD}    2. Log in with the credentials: Username: '$GRAFANA_ADMIN_USERNAME' and Password: '$GRAFANA_ADMIN_PASSWORD' $ANSI_RESET"
echo -e "${ANSI_BOLD}    3. Click on the 3 horizontal bar icon on the top left of the screen. $ANSI_RESET"
echo -e "${ANSI_BOLD}    4. Open 'Administration'. $ANSI_RESET"
echo -e "${ANSI_BOLD}    5. Click on 'Service accounts'. $ANSI_RESET"
echo -e "${ANSI_BOLD}    6. Click on 'Add service account'. $ANSI_RESET"
echo -e "${ANSI_BOLD}    7. Enter a display name and make role 'Admin'. Then click 'Create'. $ANSI_RESET"
echo -e "${ANSI_BOLD}    8. Click 'Add service account token' and enter a display name. Set No Expiration. Click 'Generate Token'.$ANSI_RESET"
echo -ne "${ANSI_BOLD}    9. Copy the token and ENTER THE GRAFANA API TOKEN HERE: $ANSI_RESET"
read GRAFANA_TOKEN

# Get API Token for InfluxDB
echo -e "\n\n"
echo -e "${ANSI_YELLOW}<--- READ THESE INSTRUCTIONS CAREFULLY FOR ${ANSI_GREEN} InfluxDB$ANSI_RESET TOKEN --->$ANSI_RESET"
echo -e "${ANSI_BOLD}    1. Open a browser and go to 'http://localhost:8086' $ANSI_RESET"
echo -e "${ANSI_BOLD}    2. Click 'GET STARTED' $ANSI_RESET"
echo -e "${ANSI_BOLD}    3. Make account with the credentials:\n        Username: '$INFLUX_ADMIN_USERNAME'\n        Password: '$INFLUX_ADMIN_PASSWORD'\n        Initial Organization name is UBC Solar\n        Initial Bucket Name is Init${ANSI_RESET}"
echo -e "${ANSI_BOLD}    4. Copy the INFLUXDB API TOKEN at the top. $ANSI_RESET"
echo -ne "${ANSI_BOLD}    5. Paste your token here: $ANSI_RESET"
read INFLUX_TOKEN

# Enter API tokens into .env file
echo -e "${ANSI_YELLOW}Updating .env file with API tokens... $ANSI_RESET"
python3 - <<PY
from pathlib import Path

env_path = Path(".env")
text = env_path.read_text()
text = text.replace('INFLUX_TOKEN=""', 'INFLUX_TOKEN="$INFLUX_TOKEN"')
text = text.replace('GRAFANA_TOKEN=""', 'GRAFANA_TOKEN="$GRAFANA_TOKEN"')
env_path.write_text(text)
PY
echo -e "${ANSI_GREEN}DONE updating .env file with API tokens! $ANSI_RESET"

# Restart docker
echo -e "${ANSI_YELLOW}Restarting docker containers... $ANSI_RESET"
docker compose down
docker compose up -d

# Creating a python virtual environment
echo -e "${ANSI_YELLOW}Changing directory to $SUNLINK_DIR $ANSI_RESET"
cd "$SUNLINK_DIR"

echo -e "${ANSI_YELLOW}Setting up virtual environment... $ANSI_RESET"
python3 -m venv environment
chmod -R u+rwX environment
echo -e "${ANSI_GREEN}DONE creating virtual environment! $ANSI_RESET"

echo -e "$ANSI_YELLOW Creating Influx Buckets... ${ANSI_RESET}"
docker exec influxdb influx bucket create --name "CAN_test" --org "UBC Solar" --token "${INFLUX_TOKEN}" || true
echo -e "${ANSI_GREEN}BUCKET: 'CAN_test' created, or already exists.$ANSI_RESET"

docker exec influxdb influx bucket create --name "CAN_prod" --org "UBC Solar" --token "${INFLUX_TOKEN}" || true
echo -e "${ANSI_GREEN}BUCKET: 'CAN_prod' created, or already exists.$ANSI_RESET"

docker exec influxdb influx bucket create --name "CAN_log" --org "UBC Solar" --token "${INFLUX_TOKEN}" || true
echo -e "${ANSI_GREEN}BUCKET: 'CAN_log' created, or already exists.$ANSI_RESET"

# Restarting docker
echo -e "${ANSI_YELLOW}Restarting docker containers one last time... $ANSI_RESET"
docker compose down
docker compose up -d

# Setting up Tailscale
echo -ne "${ANSI_YELLOW}Do you already have Tailscale setup (y/n)?: $ANSI_RESET"
read setupTailscale
if [ "$setupTailscale" = "n" ] || [ "$setupTailscale" = "N" ]; then
    echo -ne "${ANSI_YELLOW}ENTER your Tailscale auth key here. You may need to ask your lead for this: $ANSI_RESET"
    read tailscaleAuthKey
    echo -e "${ANSI_BOLD}Setting up Tailscale... $ANSI_RESET"

    if ! command_exists tailscale; then
        brew install --cask tailscale
    fi

    echo -e "${ANSI_YELLOW}Opening Tailscale. Finish any macOS permission prompts if they appear.$ANSI_RESET"
    open -a Tailscale || true

    if command_exists tailscale; then
        sudo tailscale up --auth-key "$tailscaleAuthKey" || true
    else
        echo -e "${ANSI_YELLOW}Tailscale was installed as a macOS app. Open it and sign in using your team instructions.$ANSI_RESET"
    fi

    echo -e "${ANSI_GREEN}DONE setting up Tailscale, or Tailscale app is ready for login! $ANSI_RESET"
else
    echo -e "${ANSI_BOLD}Skipping Tailscale setup... $ANSI_RESET"
fi

# Make everything in the scripts directory executable
echo -e "${ANSI_YELLOW}Making all scripts executable... $ANSI_RESET"
chmod +x scripts/CSV_Download_script.sh 2>/dev/null || true

echo -e "\n\n"
echo -e "${ANSI_YELLOW}<--- ALMOST COMPLETED SETTING UP SUNLINK. YOU NEED TO RUN THE FOLLOWING --->$ANSI_RESET"
echo -e "${ANSI_BOLD}    1. Run 'cd sunlink/' to enter the sunlink directory $ANSI_RESET"
echo -e "${ANSI_BOLD}    2. Run 'source environment/bin/activate' to activate the virtual environment $ANSI_RESET"
echo -e "${ANSI_BOLD}    3. Run 'pip install -r requirements_MacOS.txt' to install all dependencies in environment $ANSI_RESET"
echo -e "${ANSI_BOLD}    4. Run 'docker compose restart' to ensure up-to-date installation $ANSI_RESET"
echo -e "\n\n"

# Removing script
echo -e "${ANSI_BOLD}Removing setup script from parent directory if present... $ANSI_RESET"
rm -f ../setup.sh
echo -e "${ANSI_GREEN}Mac setup script complete! $ANSI_RESET"
