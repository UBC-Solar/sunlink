#!/bin/bash
set -e

# creates the debug bucket after InfluxDB initialization
influx bucket create --name "${INFLUX_DEBUG_BUCKET}" --org "${DOCKER_INFLUXDB_INIT_ORG}"
