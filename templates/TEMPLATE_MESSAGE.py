"""
<MESSAGE_NAME> message wrapper class. <MESSAGE_NAME>.data[''] fields are:

'<FIELD_NAME>': <FIELD_TYPE> <DESCRIPTION>

self.type = "<MESSAGE_NAME>"
"""
class MESSAGE_NAME:
    def __init__(self, message: str) -> None:      
        """
        In general, the init should set the data dictionary 
        based on parsing the message string. The type should be set to the name of the message.
        
        See 'GPS_Msg.py' and 'IMU_Msg.py' for good working examples.
        """

        self.data = None
        self.type = "<MESSAGE_NAME>"
        pass


    """
    Will create a dictionary whose keys are the column headings to the pretty table
    and whose values are data in those columns. Table printed when processing response from parser
    in link_telemetry.py
    
    Parameters:
        format_specifier: file path to a file containing a format specifier
        
    Returns:
        display_data dictionary with the following form
        {
            "Hex ID": [hex id1, hex id1, hex id1, ...],
            "Source": [source1, source1, source1, ...],
            "Class": [class1, class1, class1, ...],
            "Measurment": [measurement1, measurement2, measurement3, ...],
            "Value": [value1, value2, value3, ...]
            "ID": hex id1
        }
    """
    def extract_measurements(self, format_specifier=None) -> dict:
        measurements = format_specifier.decode_message(self.data["identifier"], self.data["data_bytes"])
        message = format_specifier.get_message_by_frame_id(self.data["identifier"])

        # where the data came from
        sources: list = message.senders

        source: str
        if len(sources) == 0:
            source = "UNKNOWN"
        else:
            source = sources[0]

        # Initilization
        display_data = {
            "Hex ID": [],
            "Source": [],
            "Class": [],
            "Measurement": [],
            "Value": [],
            "ID": self.data["hex_identifier"]
        }

        # Now add each field to the list
        for name, data in measurements.items():
            display_data["Hex ID"].append(self.data["hex_identifier"])
            display_data["Source"].append(source)
            display_data["Class"].append(message.name)
            display_data["Measurement"].append(name)
            display_data["Value"].append(data)
        
        return display_data

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
