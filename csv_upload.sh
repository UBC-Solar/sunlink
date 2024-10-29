#!/bin/bash

# Echo message to indicate upload start
echo "CSV upload to InfluxDB started..."

# Define variables
CSV_NAME=$(grep 'CSV_NAME' LINK_CONSTANTS.py | sed -E "s/CSV_NAME = \"([^\"]+)\"/\1/") # Extract CSV_NAME from LINK_CONSTANTS.py
timestamp=$(date +'%Y-%m-%d_%H-%M-%S') 
CSV_FILE="${CSV_NAME}${timestamp}.csv"
COMPRESSED_CSV_FILE="${CSV_FILE}.gz"

gzip -k "$CSV_FILE"

# transfer the compressed CSV file to the Elec bay computer
scp "$COMPRESSED_CSV_FILE" electrical@elec-bay:~/sunlink/"$COMPRESSED_CSV_FILE"

# SSH into the Elec bay computer and transfering the file to the InfluxDB container
ssh electrical@elec-bay << EOF
    sudo docker cp ~/sunlink/"$COMPRESSED_CSV_FILE" influxdb:/"$COMPRESSED_CSV_FILE"
EOF

# Entering the InfluxDB container and uploading the data to InfluxDB
ssh electrical@elec-bay << EOF
    sudo docker exec -it influxdb bash -c "influx write -b CAN_log -f /$COMPRESSED_CSV_FILE --compression 'gzip'"
EOF