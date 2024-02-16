#!/bin/bash
set -e

source ./.env

# creates the debug bucket after InfluxDB initialization
# influx bucket create --name "${INFLUX_DEBUG_BUCKET}" --org "${DOCKER_INFLUXDB_INIT_ORG}"

# Convert the message types to an array
echo "Creating buckets for message types: ${MESSAGE_TYPES}"
IFS=',' read -ra TYPES <<< "$MESSAGE_TYPES"

# Loop over each message type and create the buckets
for TYPE in "${TYPES[@]}"; do
    # Print and create the debug bucket
    echo "Creating debug bucket: ${TYPE}${INFLUX_DEBUG_BUCKET}"
    echo influx bucket create --name "${TYPE}${INFLUX_DEBUG_BUCKET}" --org "${DOCKER_INFLUXDB_INIT_ORG}"
    
    # Print and create the prod bucket
    echo "Creating prod bucket: ${TYPE}${INFLUX_PROD_BUCKET}"
    echo influx bucket create --name "${TYPE}${INFLUX_PROD_BUCKET}" --org "${DOCKER_INFLUXDB_INIT_ORG}"
done

# # Create test and prod buckets
# IFS=',' read -ra TYPES <<< "${MESSAGE_TYPES}"

# for TYPE in "${TYPES[@]}"; do
#     # Create the debug bucket
#     influx bucket create --name "${TYPE}${INFLUX_DEBUG_BUCKET}" --org "${DOCKER_INFLUXDB_INIT_ORG}"
    
#     # Create the prod bucket
#     influx bucket create --name "${TYPE}${INFLUX_PROD_BUCKET}" --org "${DOCKER_INFLUXDB_INIT_ORG}"
# done


