# Parser API

This is the formal description of the HTTP API provided by the hosted parser. The `link_telemetry.py` script makes direct use of this API.

# Endpoints

## Welcome message

**URL:** `/`

**METHOD:** `GET`

**DESCRIPTION:** Returns a welcome message.

**SAMPLE RESPONSE:** `Welcome to UBC Solar's Telemetry Parser!`

## Health check

**URL:** `/api/v1/health`

**METHOD:** `GET`

**DESCRIPTION:** Returns information about the parser's connected services. These are usually just InfluxDB and Grafana.

**SAMPLE RESPONSE:** 

```json
{
    "services": [
        {
            "name": "influxdb",
            "status": "UP",
            "url": "http://influxdb:8086/"
        },
        {
            "name": "grafana",
            "status": "UP",
            "url": "http://grafana:3000/"
        },
    ]
}
```

**RESPONSE NOTES:** 

1. The `status` field can be one of `"UP"`, `"DOWN"`, or `"UNEXPECTED_STATUS_CODE"`.

- `"UP"` => The respective service is up and reachable.

- `"DOWN"` => The respective service is down and unreachable. It is not recommended to run telemetry in this case.

- `"UNEXPECTED_STATUS_CODE"` => The respective service is reachable but it returned an unexpected status code. It is not recommended to run telemetry in this case as well.

## Parse CAN message

**URL:** `/api/v1/parse`

**METHOD:** `GET`

**DESCRIPTION:** Parses the requested CAN message and sends back the parsed measurements.

**SAMPLE RESPONSES:** 

```json
{
    "id": 1025,
    "measurements": 
        [
            {
                "m_class": "drive_command",
                "name": "desired_velocity",
                "source": "speed_controller",
                "value": 56.31
            },
            {
                "m_class": "drive_command", 
                "name": "current_setpoint", 
                "source": "speed_controller",
                "value": 0.44
            }
        ],
    "result": "OK"
}
```

```json
{
    "id": 990,
    "measurements": [],
    "result": "PARSE_FAIL"
}
```

**RESPONSE NOTES:**

1. The `result` field can be one of `'OK'` or `'PARSE_FAIL'`.

- `'OK'` => parsing completed successfully

- `'PARSE_FAIL'` => parsing failed for some reason (usually because the CAN ID is not in the DBC file used by the parser)

2. The `measurements` field is a list of measurements extracted from the CAN message provided in the request. This field is only populated when the `result` field is `'OK'`.

3. The `id` field is simply the CAN ID of the message that was parsed.

## Parse CAN message + write to debug bucket

**URL:** `/api/v1/parse/write/debug`

**METHOD:** `GET`

**DESCRIPTION:** Parses the requested CAN message, writes the measurements to a debug bucket (usually called "Test") on InfluxDB, and sends back the parsed measurements.

**SAMPLE RESPONSES:** 

```json
{
    "id": 1025,
    "measurements": 
        [
            {
                "m_class": "drive_command",
                "name": "desired_velocity",
                "source": "speed_controller",
                "value": 56.31
            },
            {
                "m_class": "drive_command", 
                "name": "current_setpoint", 
                "source": "speed_controller",
                "value": 0.44
            }
        ],
    "result": "OK"
}
```

```json
{
    "id": 990,
    "measurements": [],
    "result": "PARSE_FAIL"
}
```

```json
{
    "id": 1282, 
    "measurements": 
        [
            {
                "m_class": "motor_bus",
                "name": "bus_voltage",
                "source": "daybreak_motor_controller",
                "value": 103.4
            },
            {
                "m_class": "motor_bus",
                "name": "bus_current",
                "source": "daybreak_motor_controller",
                "value": 34.2
            }
        ],
    "result": "INFLUX_WRITE_FAIL"
}
```

**RESPONSE NOTES:**

1. The `result` field can be one of `'OK'`, `'PARSE_FAIL'`, `'INFLUX_WRITE_FAIL'`.

- `'OK'` => parsing completed successfully

- `'PARSE_FAIL'` => parsing failed for some reason (usually because the CAN ID is not in the DBC file used by the parser)

- `'INFLUX_WRITE_FAIL'` => parsing succeeded but the parser was unable to write the measurements to the InfluxDB instance. In this case, check that the InfluxDB container is up and reachable. 

2. The `measurements` field is a list of measurements extracted from the CAN message provided in the request. This field is only populated when the `result` field is `'OK'`.

3. The `id` field is simply the CAN ID of the message that was parsed.

## Parse CAN message + write to production bucket

**URL:** `/api/v1/parse/write/production`

**METHOD:** `GET`

**DESCRIPTION:** Parses the requested CAN message, writes the measurements to a production bucket (usually called "Telemetry") on InfluxDB, and sends back the parsed measurements.

**SAMPLE RESPONSES:**

Identical to the `/api/v1/parse/write/debug` endpoint.

**SAMPLE NOTES:**

Identical to the `/api/v1/parse/write/debug` endpoint.
