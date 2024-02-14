# From Raw to Processed Data
This doc serves as a guide to how and where the data coming into `link_telemetry.py` is sent and parsed. Below is an image giving an overview of the data flow.

![Sunlink Dataflow](/images/sunlink_dataflow.png)

Now we will do a component by component breakdown of the data flow.

## Link Telemetry
This script is the one that runs locally on your computer. For example, if you wanted to run CAN, GPS, and IMU random messages to the debug bucket at a frequency of 10 Hz the following command would be used:
```./link_telemetry.py -r can -r gps -r imu --debug -f 10````
**You must ensure that your are in the python envrionment required by the set-up in the main README.md**. 

After this command is executed, a config table will appear which confirms the messages being sent, the target bucket, the frequency, and other details. After accepting these configurations, this specifc command will generate random messages based on the script in `randomizer.py` inside the `parser` folder.

### Data Class Overview
Inside the `parser` folder there are classes such as `CAN`, `GPS`, and `IMU` which are defined inside the `CAN_Msg.py`, `GPS_Msg.py`, and `IMU_Msg.py` files respectively. The constructor of these classes takes in a string of data (from the randomizer for example) and will parse the data and store it as a dictionary with a **standard format** in the `.data` field of the class. This is done in the `extract_measurements` method of the class.  

Note: The `data` dict has two parts: `REQUIRED FIELDS` and `DISPLAY FIELDS`. `REQUIRED FIELDS` are the fields that are required for the parser to recognize the message and send it to InfluxDB. The `DISPLAY FIELDS` are those which will be displayed as a pretty table in your terminal (more on **how** this happens in the **process response** section).

### Process Response
The `process_response` function in `link_telemetry.py` recieves the result of the HTTP request made to the parser. This function will print whether the HTTP request was successful (code 200) or not (some other code). In addition, this function will read the fields inside the `DISPLAY FIELDS` dictionary of the `data` dictionary (it is nested). Upon reading these fields, it will generate a table whose column headings are the keys of the display dictionary and the values the columns are the values of the keys (number of rows in the pretty table corresponds to the length of list which the key corresponds to). For example, lets say the dictionary looked like this (for an IMU message):
```
data = {
    "Source": ["IMU"],
    "Class": ['A'],
    "Measurment": ['X'],
    "Value": [69.420],
    "ID": "AX"
    "display_data": {
        "Type": ['IMU'],
        "Dimension": ['X'],
        "Value": [69.420],
        "Timestamp": [1774452798]
    }
}
```


