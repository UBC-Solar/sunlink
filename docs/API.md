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

**SAMPLE REQUEST: (IMU RAW DATA)**

```json
{
    "message": "7f0ebf09@AYÄZÃ."
}
```

**SAMPLE RESPONSE: (PARSED IMU MESSAGE FROM ABOVE)**

```json
{
    "result": "OK",
    "message": {
        "Type": ["A"],
        "Dimension": ["Y"],
        "Value": [-875.049683],
        "Timestamp": [2131672841]
    },
    "id": "AY",
    "type": "IMU"
}
```

**RESPONSE NOTES:**

1. The `result` field can be one of `'OK'` or `'PARSE_FAIL'`.

    - `'OK'` => parsing completed successfully

    - `'PARSE_FAIL'` => parsing failed for some reason (usually because the CAN ID is not in the DBC file used by the parser)

2. The `message` field is a dictionary of the parsed message that came into the parser. This field is only populated when the `result` field is `'OK'`.

3. The `id` field is the `"ID"` field of the `data` dictionary of the data class. For CAN this is the hex ID, for GPS messages this is the timestamp of the message, and for IMU it is the type + dimension of the message.

4. The `type` field is the type of message (CAN, GPS, or IMU currently).

## Parse message + write to debug bucket

**URL:** `/api/v1/parse/write/debug`

**METHOD:** `[POST]`

**REQUEST CONTENT TYPE:** `application/json`

**DESCRIPTION:** Parses the requested message, writes the measurements to an "<MESSAGE_NAME>_test" bucket on InfluxDB, and sends back the parsed measurements.

**AUTHENTICATION:** Required.

**SAMPLE REQUEST: (CAN RAW DATA)**

```json
{
    "message": "28eb942c0628¶nÌWùjs8"
}
```

**SAMPLE RESPONSES: (PARSED CAN MESSAGE FROM ABOVE)**

```json
{
    "result": "OK",
    "message": {
        "Hex_ID": ["0x628", "0x628", "0x628", "0x628", "0x628"], 
        "Source": ["BMS", "BMS", "BMS", "BMS", "BMS"], 
        "Class": ["ModuleStatuses", "ModuleStatuses", "ModuleStatuses", "ModuleStatuses", "ModuleStatuses"], 
        "Measurement": ["MultiplexingBits", "Module25", "Module26", "Module27", "Module28"], 
        "Value": [6, 110, 204, 87, 249], 
        "Timestamp": [686527532, 686527532, 686527532, 686527532, 686527532]
    },
    "id": "0x628",
    "type": "CAN"
}
```

```json
{
    "result": "PARSE_FAIL",
    "message": {},
    "id": "0x628",
    "type": "CAN"
}
```

```json
{
    "result": "INFLUX_WRITE_FAIL",
    "message": {
        "Hex_ID": ["0x628", "0x628", "0x628", "0x628", "0x628"], 
        "Source": ["BMS", "BMS", "BMS", "BMS", "BMS"], 
        "Class": ["ModuleStatuses", "ModuleStatuses", "ModuleStatuses", "ModuleStatuses", "ModuleStatuses"], 
        "Measurement": ["MultiplexingBits", "Module25", "Module26", "Module27", "Module28"], 
        "Value": [6, 110, 204, 87, 249], 
        "Timestamp": [686527532, 686527532, 686527532, 686527532, 686527532]
    },
    "error": str(Exception as e),
    "id": "0x628",
    "type": "CAN"      
}
```

**RESPONSE NOTES:**

1. The `result` field can be one of `'OK'`, `'PARSE_FAIL'`, `'INFLUX_WRITE_FAIL'`.

    - `'OK'` => parsing completed successfully.

    - `'PARSE_FAIL'` => parsing failed for some reason (could be because the CAN ID is not in the DBC file used by the parser or any data formatting error/inconsistency).

    - `'INFLUX_WRITE_FAIL'` => parsing succeeded but the parser was unable to write the measurements to the InfluxDB instance. In this case, check that the InfluxDB container is up and reachable. Another problem could be interfernce of different types in the same Influx bucket (Ex. adding ints to a bucket already containing floats)

2. The `message` field is a dictionary of the parsed message that came into the parser. This field is only populated when the `result` field is `'OK'` or `'INFLUX_WRITE_FAIL'`. This is to allow offline logging of failed messages for later debugging.

3. The `id` field is the `"ID"` field of the `data` dictionary of the data class. For CAN this is the hex ID, for GPS messages this is the timestamp of the message, and for IMU it is the type + dimension of the message.

4. The `type` field is the type of message (CAN, GPS, or IMU currently).


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
