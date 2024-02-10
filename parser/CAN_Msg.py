"""
Subclass CAN implements the extract_measurements and getter
methods from the interface Message. Data fields are:

"Hex_ID": The ID of the CAN message in hex
"Source": The board which the message came from
"Class": The class of the message (Ex. Voltage Sensors Data)
"Measurment": Specifc measurement name in this class (Ex. Volt Sensor 1, Volt Sensor 2)
"Value": The value of the associated measurement
"ID": Chosen to be the Hex_ID

self.type = "CAN"
"""
class CAN:
    """
    CREDIT: Mihir. N for his implementation
    CHANGES:
        data field is now 8 bytes (Before: FF is sent as 2 letter Fs, now it is sent as 1 byte char with value 255)
    """
    def __init__(self, message: str, format_specifier=None) -> None:    
        self.message = message  
        self.data2 = self.extract_measurements(format_specifier)
        self.type = "CAN"


    """
    CREDIT: Mihir. N and Aarjav. J
    Will create a dictionary whose keys are the column headings to the pretty table
    and whose values are data in those columns. Dictionary is string to list.
    The list will be the same length as the number of rows in the pretty table.
    This is done to match list length to number of measurement in CAN message to list
    
    Parameters:
        format_specifier: DBC object from cantools
        
    Returns:
        display_data dictionary with the following form
        {
            "Hex_ID": [hex id1, hex id1, hex id1, ...],
            "Source": [source1, source1, source1, ...],
            "Class": [class1, class1, class1, ...],
            "Measurment": [measurement1, measurement2, measurement3, ...],
            "Value": [value1, value2, value3, ...]
            "ID": hex id1
        }
    """
    def extract_measurements(self, format_specifier=None) -> dict:      
        timestamp: int = int(self.message[0:8], 16)
        id: str = self.message[8:12]
        data: str = self.message[12:20]

        identifier = int(id, 16)  
        data_bytes = bytearray(map(lambda x: ord(x), data))
        hex_id = "0x" + hex(identifier)[2:].upper()

        measurements = format_specifier.decode_message(identifier, data_bytes)
        message = format_specifier.get_message_by_frame_id(identifier)

        # where the data came from
        sources: list = message.senders

        source: str
        if len(sources) == 0:
            source = "UNKNOWN"
        else:
            source = sources[0]

        # Initilization
        display_data = {
            "Hex_ID": [],
            "Source": [],
            "Class": [],
            "Measurement": [],
            "Value": [],
            "Timestamp": [],
            "ID": hex_id
        }

        # Now add each field to the list
        for name, data in measurements.items():
            display_data["Hex_ID"].append(hex_id)
            display_data["Source"].append(source)
            display_data["Class"].append(message.name)
            display_data["Measurement"].append(name)
            display_data["Timestamp"].append(timestamp)
            display_data["Value"].append(data)
        
        return display_data

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
