#!/bin/bash

# Check if a filename argument was provided
if [ -z "$1" ]; then
    echo "Usage: $0 <csv_filename>"
    exit 1
fi

# Define ANSI colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

COMPRESSED_CSV_FILE="DATA.csv.gz"
SSH_PASSWORD="elec2024"
REMOTE_USER="electrical"
REMOTE_HOST="elec-bay"
INFLUX_CONTAINER="influxdb"
LOG_BUCKET="CAN_test"


echo -e "${BOLD}Starting Influx CSV Upload${NC}"

# Check if sshpass is installed
if ! command -v sshpass &> /dev/null; then
    echo -e "${RED}sshpass is not installed. Installing sshpass...${NC}"
    sudo apt-get install -y sshpass
else
    echo -e "${GREEN}sshpass is already installed. Skipping installation.${NC}"
fi

# Compress the CSV file
echo -e "${YELLOW}Compressing the CSV file...${NC}"
gzip -k -c "$1" > "$COMPRESSED_CSV_FILE"
echo -e "${GREEN}Compressed the CSV file as ${COMPRESSED_CSV_FILE}${NC}"

# Transfer the compressed CSV file to the Elec bay computer
echo -e "${YELLOW}Using Elec-bay computer password:${NC} ${BOLD}'elec2024'${NC}"
sshpass -p "$SSH_PASSWORD" scp "$COMPRESSED_CSV_FILE" "$REMOTE_USER@$REMOTE_HOST:~/sunlink/$COMPRESSED_CSV_FILE"
echo -e "${GREEN}Transferred to elec-bay computer!${NC}"

# SSH into the Elec bay computer and transfer the file to the InfluxDB container
# Use -c in bash to execute commands as a string.
sshpass -p "$SSH_PASSWORD" ssh -q "$REMOTE_USER@$REMOTE_HOST" << EOF > /dev/null
cd ~/sunlink
docker cp $COMPRESSED_CSV_FILE influxdb:/$COMPRESSED_CSV_FILE
docker exec $INFLUX_CONTAINER bash -c "     
influx write -b $LOG_BUCKET -f $COMPRESSED_CSV_FILE --compression 'gzip'
rm $COMPRESSED_CSV_FILE
"
echo -e "${GREEN}Uploaded the compressed CSV file to InfluxDB!${NC}"
rm $COMPRESSED_CSV_FILE
EOF

# rm $COMPRESSED_CSV_FILE
echo -e "${BOLD}==================== DONE! ====================${NC}"

