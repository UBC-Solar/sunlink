# Parser API

This is the formal description of the HTTP API provided by the hosted parser. The `link_telemetry.py` script makes direct use of this API.

# Endpoints

## Welcome message

**URL:** `/`

**METHOD:** `[GET]`

**DESCRIPTION:** Returns a welcome message.

**AUTHENTICATION:** Not required.

**SAMPLE RESPONSE:** `Welcome to UBC Solar's Telemetry Parser!`

## Health check

**URL:** `/api/v1/health`

**METHOD:** `[GET]`

**DESCRIPTION:** Returns information about the parser's connected services. These are usually just InfluxDB and Grafana.

**AUTHENTICATION:** Required.

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
        }
    ]
}
```

**RESPONSE NOTES:**

1. The `status` field can be one of `"UP"`, `"DOWN"`, or `"UNEXPECTED_STATUS_CODE"`.

    - `"UP"` => The respective service is up and reachable.

    - `"DOWN"` => The respective service is down and unreachable. It is not recommended to run telemetry in this case.

    - `"UNAUTHORIZED"` => The respective service is reachable but the parser is not authorized to access its resources. This is usually because an API token has not been configured correctly in the `.env` file.

    - `"UNEXPECTED_STATUS_CODE"` => The respective service is reachable but it returned an unexpected status code. It is not recommended to run telemetry in this case as well.

## Parse message

**URL:** `/api/v1/parse`

**METHOD:** `[POST]`

**REQUEST CONTENT TYPE:** `application/json`

**DESCRIPTION:** Parses the requested CAN message and sends back the parsed measurements.

**AUTHENTICATION:** Required.

**SAMPLE REQUEST: (CAN RAW DATA. Shown as hex string but MUST convert and send hex string to encoded to bytes then latin-1 string)**

```json
{
    "message": "41d99749c232e14823000006280000000000000000080d41d99749c232e1482300000401000000000000000008"
}
```

**SAMPLE RESPONSE: (PARSED CAN MESSAGE FROM ABOVE)**

```json
{
    "all_responses" : [
        {
            "result": "OK",
            "message": {
                "ROW": {
                    "Raw Hex": "41d99749c232e1482300000628000000000000000008"
                },
                "COL": {
                    "Hex_ID": "0x628",
                    "Source": "BMS",
                    "Class": "Module Statuses",
                    "Measurement": "Multiplexing bits",
                    "Value": "0.0",
                    "Timestamp": "2024-06-03 02:17:39.224"
                }
            },
            "logMessage": "True",
            "type": "CAN",
        },
        {
            "result": "OK",
            "message": {
                "ROW": {
                    "Raw Hex": "41d99749c232e1482300000401000000000000000008"
                },
                "COL": {
                    "Hex_ID": "0x401",
                    "Source": "MCB",
                    "Class": "PercentageOfMaxCurrent",
                    "Measurement": "MotorCurrent",
                    "Value": "0.0",
                    "Timestamp": "2024-06-03 02:17:39.224"
                }
            },
            "logMessage": "True",
            "type": "CAN",
        },
    ]
}
```

**RESPONSE NOTES:**

1. The `all_responses` field is a list of dictionaries which contain information about the parsing result of each valid message in the chunk that was sent to the parser. This chunk is typically received from `serial.Serial.read(CHUNK_SIZE).decode('latin-1)` (Note that .hex() was only applied for visual aid in these docs otherwise you must send a latin-1 encoded string).
2. The `result` field can be one of `'OK'` or `'PARSE_FAIL'`.

    - `'OK'` => parsing completed successfully

    - `'PARSE_FAIL'` => parsing failed for some reason (usually because the CAN ID is not in the DBC file used by the parser)

3. The `message` field is the display dictionary of one of the valid messages from the total chunk that came into the parser. This field is only populated when the `result` field is `'OK'`.
4. The `logMessage` field is a boolean that indicates whether the message was logged into a local file in the `logfiles` directory. This field is only populated when the `result` field is `'OK'`.
5. The `type` field is the type of message (CAN, GPS, or IMU currently).

## Parse message + write to debug bucket

**URL:** `/api/v1/parse/write/debug`

**METHOD:** `[POST]`

**REQUEST CONTENT TYPE:** `application/json`

**DESCRIPTION:** Parses the requested message, writes the measurements to an "<MESSAGE_NAME>_test" bucket on InfluxDB, and sends back the parsed measurements.

**AUTHENTICATION:** Required.

**SAMPLE REQUEST: (CAN RAW DATA. Shown as hex string but MUST convert and send hex string to encoded to bytes then latin-1 string)**

```json
{
    "message": "41d99749c232e1482300000401000000000000000008"
}
```

```json
{
    "message": "41d997abfa06a7f02300000628030041d997abfa0800002300000401000000000000000008"
}
```

**SAMPLE RESPONSES: (PARSED CAN MESSAGE FROM ABOVE)**

```json
{
    "all_responses" : [
        {
            "result": "OK",
            "message": {
                "ROW": {
                    "Raw Hex": "41d99749c232e1482300000401000000000000000008"
                },
                "COL": {
                    "Hex_ID": "0x401",
                    "Source": "MCB",
                    "Class": "PercentageOfMaxCurrent",
                    "Measurement": "MotorCurrent",
                    "Value": "0.0",
                    "Timestamp": "2024-06-03 02:17:39.224"
                }
            },
            "logMessage": "True",
            "type": "CAN",
        },
    ]
}
```

```json
{
    "all_responses" : [
        {
            "result": "PARSE_FAIL",
            "message": "41d997abfa06a7f02300000628030041d997abfa0800002300000401000000000000000008",
            "error": "PARSE_FAIL: 
                        Failed in create_message:
                            Message length of 37 is not a valid length for any message type
                            Message: 
                            Hex Message: 41d997abfa06a7f02300000628030041d997abfa0800002300000401000000000000000008",
        },
    ]
}
```

```json
{
    "all_responses" : [
        {
            "result": "INFLUX_WRITE_FAIL",
            "message": "41d99749c232e1482300000401000000000000000008",
            "error": "<class 'influxdb.exceptions.InfluxDBClientError'>: 400: {\"error\":\"partial write: field type conflict: input field \"Value\" on measurement \"MotorCurrent\" is type float, already exists as type integer\"}",
            "type": "CAN",
        },
    ]
}
```

**RESPONSE NOTES:**

1. The `all_responses` field is a list of dictionaries which contain information about the parsing result of each valid message in the chunk that was sent to the parser. This chunk is typically received from `serial.Serial.read(CHUNK_SIZE).decode('latin-1)` (Note that .hex() was only applied for visual aid in these docs otherwise you must send a latin-1 encoded string).
2. The `result` field can be one of `'OK'`, `'PARSE_FAIL'`, `'INFLUX_WRITE_FAIL'`.

    - `'OK'` => parsing completed successfully.

    - `'PARSE_FAIL'` => parsing failed for some reason (could be because the CAN ID is not in the DBC file used by the parser or any data formatting error/inconsistency).

    - `'INFLUX_WRITE_FAIL'` => parsing succeeded but the parser was unable to write the measurements to the InfluxDB instance. In this case, check that the InfluxDB container is up and reachable. Another problem could be interference of different types in the same Influx bucket (Ex. adding ints to a bucket already containing floats)

3. The `message` field is a dictionary of the parsed message that came into the parser. This field is  populated with the data dictionary when the `result` field is `'OK'`. However, if the `result` field is `'PARSE_FAIL'` or `'INFLUX_WRITE_FAIL'` then the `message` field is a string of the raw message payload. This is to allow offline logging of failed messages for later debugging.
4. The `logMessage` field is a boolean that indicates whether the message was logged into a local file in the `logfiles` directory. This field is only populated when the `result` field is `'OK'`.
5. The `error` field (in `PARSE_FAIL` responses) is a pretty printed description of the file, line, and what error occurred. This also traces back to the function at which this error occurred and the data that caused it. Note that it uses ANSI sequences to do the pretty printing.
6. The `type` field is the type of message (CAN, GPS, or IMU currently).


## Parse message + write to production bucket

**URL:** `/api/v1/parse/write/production`

**METHOD:** `[POST]`

**REQUEST CONTENT TYPE:** `application/json`

**DESCRIPTION:** Parses the requested message, writes the measurements to a production bucket (usually called "<MESSAGE_NAME>_prod") on InfluxDB, and sends back the parsed measurements.

**AUTHENTICATION:** Required.

**SAMPLE RESPONSES:**

Identical to the `/api/v1/parse/write/debug` endpoint.

**SAMPLE NOTES:**

Identical to the `/api/v1/parse/write/debug` endpoint.