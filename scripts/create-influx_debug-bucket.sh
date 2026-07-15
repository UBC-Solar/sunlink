#!/bin/bash
set -e

# creates the debug bucket after InfluxDB initialization
influx bucket create --name "${INFLUX_DEBUG_BUCKET}" --org "${DOCKER_INFLUXDB_INIT_ORG}"

# Create test and prod buckets
IFS=',' read -ra TYPES <<< "${MESSAGE_TYPES}"

for TYPE in "${TYPES[@]}"; do
    # Create the debug bucket
    influx bucket create --name "${TYPE}_test" --org "${DOCKER_INFLUXDB_INIT_ORG}"
    
    # Create the prod bucket
    influx bucket create --name "${TYPE}_prod" --org "${DOCKER_INFLUXDB_INIT_ORG}"
done