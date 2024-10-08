#!/bin/bash

# FORMATTING CONSTANTS
ANSI_RED="\033[0;31m"
ANSI_GREEN="\033[0;32m"
ANSI_YELLOW="\033[1;33m"
ANSI_BOLD="\033[1m"
ANSI_RESET="\033[0m"

# Define constants
REMOTE_USER="electrical"
REMOTE_HOST="elec-bay"
REMOTE_DIR="~/sunlink"
INFLUX_CONTAINER="influxdb"
OUTPUT_FILE="DATA.csv"
OUTPUT_FILE_ZIP="DATA.csv.gz"
COMPRESSED_FILE="$OUTPUT_FILE.gz"
SSH_PASSWORD="elec2024"


# Prompt for Influx Query
echo -e "${ANSI_GREEN}NOTE: $REMOTE_USER@$REMOTE_HOST's password is "$SSH_PASSWORD".${ANSI_RESET}"
echo -e "${ANSI_YELLOW}Paste the Influx Query and hit enter TWICE after:${ANSI_RESET}"

# Handle multiline Query
INFLUX_QUERY=""

# Read until they enter 1 more time at the end
while IFS= read -r line; do
  if [[ "$line" == "" ]]; then
    break
  fi
  INFLUX_QUERY+="$line"$'\n'
done

# Escape double quotes in the INFLUX_QUERY
ESCAPED_INFLUX_QUERY=$(echo "$INFLUX_QUERY" | sed 's/"/\\"/g')

# Step 1: Enter the bay computer shell and execute commands
echo -e "${ANSI_YELLOW}Enter the InfluxDB token for the bay computer:${ANSI_RESET}"
read INFLUX_TOKEN
sshpass -p "$SSH_PASSWORD" ssh -q $REMOTE_USER@$REMOTE_HOST << EOF > /dev/null

cd $REMOTE_DIR

echo -e "${ANSI_YELLOW}Executing InfluxDB query and compressing the output...${ANSI_RESET}"
docker exec $INFLUX_CONTAINER bash -c "
rm -f $OUTPUT_FILE*
influx query '$ESCAPED_INFLUX_QUERY' --raw --token $INFLUX_TOKEN > $OUTPUT_FILE
gzip $OUTPUT_FILE
"

echo -e "${ANSI_YELLOW}Copying the compressed file from the container to the remote directory...${ANSI_RESET}"
docker cp $INFLUX_CONTAINER:/$COMPRESSED_FILE $REMOTE_DIR/
docker exec $INFLUX_CONTAINER bash -c "
rm $OUTPUT_FILE_ZIP
"
EOF

# Uncomment the following line if you want to transfer the file to your personal computer
echo -e "${ANSI_RED}Need password to transfer the compressed file to your personal computer...${ANSI_RESET}"
scp $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/$COMPRESSED_FILE .
echo -e "${ANSI_YELLOW}Transfer Complete.${ANSI_RESET}"

# Delete the file after transfer
echo -e "${ANSI_YELLOW}Deleting the compressed file from the remote directory...${ANSI_RESET}"
sshpass -p "$SSH_PASSWORD" ssh -q $REMOTE_USER@$REMOTE_HOST << EOF > /dev/null
cd $REMOTE_DIR
rm $COMPRESSED_FILE
EOF

echo -e "${ANSI_GREEN}InfluxDB Data Obtained!${ANSI_RESET}"
