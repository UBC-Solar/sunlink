#!/bin/bash
set -e

# creates the debug bucket after InfluxDB initialization
influx bucket create --name "${INFLUX_DEBUG_BUCKET}" --org "${DOCKER_INFLUXDB_INIT_ORG}"

# Creates the CAN_test bucket
influx bucket create --name "CAN_test" --org "${DOCKER_INFLUXDB_INIT_ORG}"

# Creates the GPS_test bucket
influx bucket create --name "GPS_test" --org "${DOCKER_INFLUXDB_INIT_ORG}"

# Creates the IMU_test bucket
influx bucket create --name "IMU_test" --org "${DOCKER_INFLUXDB_INIT_ORG}"
