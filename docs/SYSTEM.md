# System description

Sunlink's data pipeline consists of multiple components distributed over numerous systems.

![Sunlink high-level architecture](/images/sunlink-arch.png)

A detailed look at each of the components shown in the diagram will be given here.

## Table of contents

- [Telemetry board (TEL)](#telemetry-board-tel)
- [Radio module](#radio-module)
- [Cellular module](#radio-module)
- [Telemetry link](#telemetry-link)
- [Telemetry cluster](#telemetry-cluster)
    - [Parser server](#parser-server)
    - [InfluxDB](#influxdb)
    - [Grafana](#grafana)

## Telemetry board (TEL)

Sunlink would be effectively useless without the telemetry board. This board houses the radio and cellular modules which are used in-tandem to wirelessly transmit data. The two transmission modes of radio and cellular improve the overall reliability of the system.

At its simplest, the telemetry board is responsible for reading CAN messages from the car's CAN bus, encoding it in a serial format, and transmitting it over radio and cellular.

Future versions of the telemetry board will support reading IMU and GPS data in addition to CAN messages.

The radio and cellular modules, while exactly the same in their overall function, have notable differences that influence Sunlink's system architecture.

## Radio module

The radio module communicates directly to a radio receiver. The radio module transmits a serial stream (i.e., simply a stream of bytes) and the radio receiver receives the serial stream. The radio receiver connects to a laptop via USB and is registered as a USB serial device. It is possible to use any serial console (e.g., PuTTY, minicom) to read the raw encoded serial stream.

### Serial stream structure

When opening the radio receiver serial port, you will see something like the following:

```
...
34AE233006260333AA01420012BF8
34AE2400050104A8BED283CD81848
34AE24AB050248D8215700DAA3298
...
```

In the serial stream above, each line is a CAN message represented as ASCII characters. Each line is split up by the telemetry link into the following fields: timestamp, ID, payload, and payload length. The specific structure of the serial stream is defined in the documentation for the telemetry board firmware.

When the telemetry board sends a serialized CAN message over **radio**, the message takes the following path through Sunlink:

```
Radio module ----> Radio receiver ----> Telemetry link (`link_telemetry.py`) ----> Parser ----> InfluxDB
                                                                                          |
                                                                                          \---> Grafana
```

## Cellular module

As we have seen, the radio module transmits a serial stream which is received by a radio receiver. This serial stream needs to be sent to the parser which necessitates the `link_telemetry.py` script.

The cellular module does **not** require the `link_telemetry.py` script since it runs MicroPython and is itself able to make HTTP requests. This means it can bypass the `link_telemetry.py` script and talk to the parser directly.

It is this discrepancy between the radio and cellular modules that requires the parser to be implemented as an HTTP server since it provides a single unified interface to both modules.

When the telemetry board sends a serialized CAN message over **cellular**, the message takes the following path through Sunlink:

```
Cellular module ----> Parser ----> InfluxDB
                             |
                             \---> Grafana
```

## Telemetry link 

The telemetry link is the name for the single stand-alone Python script `link_telemetry.py`. Its main job is to link the radio receiver to the telemetry cluster.

More specifically, it is responsible for reading the serial stream from the radio receiver, formatting each message into a JSON object, and making HTTP requests to the parser server. 

Due to potentially long round-trip times (~200ms) for HTTP requests made to a remote telemetry cluster, the telemetry link uses a thread pool to initiate multiple HTTP requests concurrently which results in multiple in-flight requests and a much higher data throughput.

The script also provides other minor features like generating random CAN messages for debugging and checking the health of the telemetry cluster.

## Telemetry cluster

The telemetry cluster is the name given to the collection of three services each running in their own Docker containers. These three services are:

1) Parser
2) InfluxDB
3) Grafana

The parser is deployed as a Docker container along with two other services: InfluxDB and Grafana. InfluxDB is the time-series database that stores the incoming telemetry data and Grafana is the visualization platform used to graph the data.

Together, these three services form the **telemetry cluster**. They are all spun up using Docker Compose and are configured to be connected to the same bridge network allowing for easy inter-container communication over HTTP.

## Parser server

The parser is responsible for taking parse requests (which are usually sent by `link_telemetry.py` but realistically could be sent by any application able to make HTTP requests such as the cellular module), parsing the data in the requests into measurements, writing the measurements to the Influx container, and optionally streaming the parsed measurements directly to the Grafana container.

The parser uses DBC files to parse CAN messages. A detailed look into DBC files and the Python `cantools` package can be found [here](https://wiki.ubcsolar.com/en/subteams/software/cantools-and-dbc).

The parser is implemented as a Flask application and exposes an HTTP API which the `link_telemetry.py` script makes direct use of. Detailed API documentation can be found [here](/docs/API.md). 

Most of the HTTP endpoints exposed by the parser require bearer token authentication. When the parser is initially set up, a secret key is generated by the user and provided to the server. The server then checks for this secret key in the HTTP authorization headers of any HTTP request it receives. This allows for a simple form of access control and dissuades malicious use of the parser. This is especially important since the telemetry cluster (if deployed remotely) is accessible over the Internet.

From the perspective of the data sources (radio, cellular, etc.), the parser is the only entrypoint into the telemetry cluster. This means it is not possible to directly write data to the InfluxDB container or stream data to the Grafana container. **All requests must go through the parser first.**

## InfluxDB

![InfluxDB homepage](/images/influxdb.png)

InfluxDB is used as Sunlink's internal time-series database and stores all parsed telemetry data. It is configured with two buckets: a _debug bucket_ and a _production bucket_.

The debug bucket is usually used when writing randomly generated data. It is intended to be a test bucket for use while developing Sunlink. The production bucket is used when receiving actual data from the car. 

Once the InfluxDB container is spun up, it makes available a convenient GUI that is served on port 8086 by default.

Data is written to InfluxDB _only_ by the parser.

## Grafana

![Grafana homepage](/images/grafana.png)

Grafana is the visualization platform that allows for user-friendly presentation of parsed telemetry data.

The Grafana instance is provisioned (pre-configured) to connect to the InfluxDB instance automatically.

The main data presentation element Grafana provides is the dashboard. Currently, the Grafana instance is provisioned with two dashboards: "Daybreak Test Telemetry" and "Daybreak Telemetry". The first dashboard reads its data from the Influx debug bucket and the second dashboard reads its data from the Influx production bucket.

Like the InfluxDB container, the Grafana container makes available a GUI that is served on port 3000 by default.

### Livestreaming

Most of the data in the dashboards is queried by Grafana from the InfluxDB buckets but this is sometimes too slow for more time-sensitive telemetry applications. This is why the parser, in addition to writing to the InfluxDB buckets, streams all parsed data directly to the Grafana dashboard frontend. This results in a much lower total latency between the initial CAN message generation and the final data visualization on Grafana.

The parser streams data to Grafana in a background thread so it does not interfere with the main task of writing to Influx.
