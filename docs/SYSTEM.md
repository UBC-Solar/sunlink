# Complete system description 

The telemetry system pipeline has many multiple components distributed over numerous systems. 

A mostly high-level description of the movement of data from the car's CAN bus to the final Grafana visualization will be given here.

## The telemetry board (TEL)

The telemetry system could not exist without the telemetry board (TEL). This board houses the radio and cellular modules which are used in-tandem to wirelessly transmit data.

At its simplest, the telemetry board is responsible for reading CAN messages from the car's CAN bus, encoding it in a serial format, and transmitting it over radio and cellular.

The radio and cellular modules, while exactly the same in their overall function, have notable differences that influence the architecture of the telemetry system.

First, we will go through how the radio module communicates with the off-board telemetry system.

## Radio module

The radio module communicates directly to a radio receiver. The radio module transmits a serial stream (i.e., simply a stream of bytes) and the radio receiver receives the serial stream. The radio receiver connects to a laptop via USB and is registered as a USB serial device. It is possible to use any serial console (e.g., PuTTY, minicom) to read the raw encoded serial stream.

## Serial stream structure

When opening the radio receiver serial port, you will see something like the following:

```
TODO: add serial stream
```

## The `link_telemetry.py` script

This script is responsible for reading the serial stream from the radio receiver, formatting each message into a JSON object, and making HTTP requests to the parser server.

## The docker services

Before diving into the parser server, it is important to take some time to understand the Docker ccontainer structure.

The Flask parser is deployed as a Docker container along with two other services: InfluxDB and Grafana. InfluxDB is the time-series database that stores the incoming telemetry data and Grafana is the visualization platform used to graph the data.

Together, these three services are known as the **telemetry cluster**. They are all spun up using Docker Compose. They are configured to be connected to the same bridge network and so are able to easily communicate with each other.

## The parser

The parser is responsible for parsing CAN messages (which are usually sent by `link_telemetry.py` but realistically could be sent by any application able to make HTTP requests), writing the parsed measurements to the Influx container, and optionally streaming the parsed measurements directly to the Grafana container.

The parser is implemented as a Flask application and exposes an HTTP API. The `link_telemetry.py` script makes direct use of this API. Detailed API documentation can be found [here](/docs/API.md). 

Note that most of the endpoints exposed by the parser require bearer token authentication. More details about this are given in the setup section.

## Influx and Grafana

Influx is the database for the telemetry system and stores all parsed telemetry data. It is configured with two buckets: a debug bucket and a production bucket.

The debug bucket is usually used when writing randomly generated data. It is intended to be a test bucket for use while working on the telemetry system itself.

The production bucket is used when receiving actual data from the car. 

Grafana is the visualization platform that allows for user-friendly presentation of the parsed telemetry data. 

The main data presentation structure on Grafana is the dashboard. The Grafana instance is provisioned with two dashboards: "Daybreak Test Telemetry" and "Daybreak Telemetry". The first dashboard reads its data from the Influx debug bucket and the second dashboard reads its data from the Influx production bucket.

Both Influx and Grafana implement intuitive web GUIs available on ports 8086 and 3000 respectively.

## Cellular module

As we have seen, the radio module produces a serial stream. This serial stream needs to be sent to the parser which necessitates the `link_telemetry.py` script.

The cellular module does **not** require the `link_telemetry.py` script since it runs MicroPython and is itself able to make HTTP requests. This means it can bypass the `link_telemetry.py` script and talk to the parser directly.

It is this discrepancy between the radio and cellular modules that required the parser to be implemented as an HTTP server since it provides a single interface to both modules.

