# From Raw to Processed Data

This doc serves as a guide to how and where the data coming into `link_telemetry.py` is sent and parsed. Below is an image giving an overview of the data flow.

![Sunlink Dataflow](/images/sunlink_dataflow.png)

Now we will do a component by component breakdown of the data flow.

## Link Telemetry

This script is the one that runs locally on your computer. For example, if you wanted to run CAN, GPS, and IMU random messages to the debug bucket at a frequency of 10 Hz the following command would be used:
```./link_telemetry.py -r can -r gps -r imu --debug -f 10````
**You must ensure that your are in the python envrionment required by the set-up in the main README.md**.

After this command is executed, a config table will appear which confirms the messages being sent, the target bucket, the frequency, and other details. After accepting these configurations, this specifc command will generate random messages based on the script in `randomizer.py` inside the `parser` folder. See the **Data Class Overview** section for more details on how the messages are formatted and parsed.

Finally, when every request to the parser is being made (in the `parser_request` function), each message is logged to a time-stamped file in the `logfiles` folder. The format of this message is a string of hex numbers. For example, if the message was `"AA"` then the corresponding line in the logfile would be `4141` where 41 is the hex value for the ASCII character `A`. This was done to avoid cases where if the last character was a newline character, the message would be split into two lines in the logfile.

### Data Class Overview

Inside the `parser` folder there are classes such as `CAN`, `GPS`, and `IMU` which are defined inside the `CAN_Msg.py`, `GPS_Msg.py`, and `IMU_Msg.py` files respectively. The constructor of these classes takes in a string of data (from the randomizer for example) and will parse the data and store it as a dictionary with a **standard format** in the `.data` field of the class. This is done in the `extract_measurements` method of the class.

Note: The `data` dict has two parts: `REQUIRED (INFLUX) FIELDS` and `DISPLAY FIELDS`. `REQUIRED (INFLUX) FIELDS` are the fields that are required for the parser to recognize the message and send it to InfluxDB. The `DISPLAY FIELDS` are those which will be displayed as a pretty table in your terminal (more on **how** this happens in the **process response** section).

Finally, the data class is connected to the rest of sunlink by importing it in the `create_message` factory method which returns an instance your data class to the parser. From here, the parser simply accesses the `data` field of your class.

## Parser (main.py)

This is where the majority of the processing and handling of data occurs. Here, 3 main things happen:

1. The JSON containing the raw message sent by `link_telemetry.py` is parsed by passing the message string to the `create_message` factory function which returns an instance of the appropriate data class (CAN, GPS, IMU, etc). This will be the stepping stone for any movement of data for a particualr message whether it be to InfluxDB or as the input to the `process_response` function in `link_telemetry.py`.
2. The data is sent to `InfluxDB` by first looping through each `"Source"`, "`Class"`,`"Measurement"`, and `"Value"` key `data` dictionary of the class. **This is why the REQUIRED (INFLUX) FIELDS of the data class were enforced**. Note that by enforcing the number of and names of these keys, we standardize the result of data processing and data handling while simultaneously allowing flexibility for the user to **put whatever data they want for those keys**. The importance of this is that a future data class implementers only need to worry about actually creating their data type rather than worrying about **if** their data will be processed correctly and debugging that whole process
3. After all the data handling is done, the parser will finally send a response back to `link_telemetry.py` in the form of a dictionary containing the result of the HTTP request, the data

### Process Response

The `process_response` function in `link_telemetry.py` recieves the result of the HTTP request made to the parser. This function will print whether the HTTP request was successful (code 200) or not (some other code). In addition, this function will read the fields inside the `DISPLAY FIELDS` dictionary of the `data` dictionary (it is nested). Upon reading these fields, it will generate a table whose column headings are the keys of the display dictionary and the values the columns are the values of the keys (number of rows in the pretty table corresponds to the length of list which the key corresponds to). For example, lets say the dictionary looked like this (for an IMU message):

```
data = {
    "Source": ["IMU"],
    "Class": ['A'],
    "Measurment": ['Y'],
    "Value": [-849.287415],
    "Timestamp": [1708401922.012]
    "display_data": {
        "Type": ['A'],
        "Dimension": ['Y'],
        "Value": [-849.287415],
        "Timestamp": [1708401922.012 ]
    }
}
```

Then the pretty table would look like this:

```
+-------------------------------------------------+
|                       IMU                       |
+-----------+----------------+------+-------------+
| Dimension |   Timestamp    | Type |    Value    |
+-----------+----------------+------+-------------+
|     Y     | 1708401922.012 |  A   | -849.287415 |
+-----------+----------------+------+-------------+
```

**Note that the column headings may not be in the same order as the dictionary keys**, However, the values will be matched to the correct headings.

## Logfiles

This is simply another pathway the raw messages in `link_telemetry.py` can take. Everytime `link_telemetry.py` is run, a new logfile is created inside the `logfiles` folder timestamped to when `link_telemetry.py` was run. Each message (be it CAN, GPS, IMU) is stored on **one line** as its original raw message which `link_telemetry.py` recieved.

## InfluxDB

In the parser, an **InfluxDB Point** is created using the `"Source"`, `"Class"`, `"Measurement"`, and `"Value"` keys of the `data` dictionary. Additionally, the `"Timestamp"` field will post the data to InfluxDB with this field as the post date (You may have to check data within a larger time frame to see this work). The reason why a timestamp is included in the point is that it gives the exact time of the CAN message generation as opposed to the time when data went to Influx. This point corresponds to the different ways to filter the data from different messages. Specifcally, here is the current breakdown of the fields and tags of each message type. Note that the standard for testing/debugging and production buckets has changed to the format `<MESSAGE_NAME>_test` and `<MESSAGE_NAME>_prod` respectively. A recommendation for user's wanting to view the data on Influx is to use the `last` keyword for the aggregate function (bottom right of screen). This will help you match data you see printing to the terminal to the data coming into InfluxDB. The following is the breakdown of the fields and tags for each message type.

### CAN

The new buckets are **CAN_test** and **CAN_prod** The fields and tags are unchanged from the original implementation. Note, the keys are the `REQUIRED (INFLUX) FIELDS` from the data dict.

-   `"Source"`: Corresponds to `_measurement` on InfluxDB. This is the origin board of the message.
-   `"Class"`: Corresponds to the `class` tag on InfluxDB. This is the name that the ID of the message corresponds to (Think of it as a class of multiple types of measurements).
-   `"Measurement"`: Corresponds to the `_field` tag on InfluxDB. This is the name of the measurement that is associated with that specifc class.
-   `"Value"`: Corresponds to the value of the measurement.

### GPS

The new buckets are **GPS_test** and **GPS_prod**.

-   `"Source"`: Corresponds to `_measurement` on InfluxDB. **This is always "GPS".**
-   `"Class"`: Corresponds to the `class` tag on InfluxDB. These include the following:
    -   `"Latitudes"`
    -   `"Latsides"`
    -   `"Longitudes"`
    -   `"Longsides"`
    -   `"Altitudes"`
    -   `"Satellites_Counts"`
    -   `"Fixs"`
    -   `"HDOPs"`
    -   `"Timestamp"`
-   `"Measurement"`: Corresponds to the `_field` tag on InfluxDB. These are the non-plural version of the class tags. Note that the reason for this is that if other data associated with a class is added it can be added to the same class tag.
-   `"Value"`: Corresponds to the value of the measurement.
-  `"Timestamp"`: Corresponds to the time the message was generated.

### IMU

The new buckets are **IMU_test** and **IMU_prod**.

-   `"Source"`: Corresponds to `_measurement` on InfluxDB. **This is always "IMU".**
-   `"Class"`: Corresponds to the `class` tag on InfluxDB. These include the following:
    -   `"A"` (For accelerometer)
    -   `"G"` (For gyroscope)
-   `"Measurement"`: Corresponds to the `_field` tag on InfluxDB. These include the x, y, z dimensions of the accelerometer and gyroscope.
    -   `"X"`
    -   `"Y"`
    -   `"Z"`
-   `"Value"`: Corresponds to the value of the measurement.
-   `"Timestamp"`: Corresponds to the time the message was generated.

## Grafana

The last stop the data goes to is Grafana. This is done by first creating a dashboard on Grafana and then adding a panel/visualization. From here, To access the various buckets on InfluxDB to graph the data you have two options.

1. Copy the query from InfluxDB and just paste it in the query section of the Grafana panel. To do this, navigate to InfluxDB and use the query builder mode (the nice UI) to build your query (Ex. IMU, A, X). Then click the "SCRIPT EDITOR" button to the left of "SUBMIT" to toggle to the raw query. **This is the query you want to copy paste into Grafana**.
2. You can take a look at some example queries below:

### CAN: Query for TempSensor 1

```sql
from(bucket: "CAN_test")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "AMB")
  |> filter(fn: (r) => r["_field"] == "TempSensors1")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")
```

### GPS: Query for Latitude

```sql
from(bucket: "GPS_test")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "GPS")
  |> filter(fn: (r) => r["_field"] == "Latitude")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")
```

### IMU: Query for Accelerometer X (AX)

```sql
from(bucket: "IMU_test")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "IMU")
  |> filter(fn: (r) => r["class"] == "A")
  |> filter(fn: (r) => r["_field"] == "X")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")
```

### Example Dashboard

![Grafana CAN, GPS, IMU Dashboard Example](/images/grafana_random_test.png)
