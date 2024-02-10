"""
CAN message wrapper class. CAN.data[''] fields are:

"Hex_ID": Hex identifier of the CAN message
"Source": Source board. Ex. 'MCU', 'BMS', etc.
"Class": Class of the CAN message. Ex. 'BMS Status', etc.
"Measurment": The specifc name of the measurment at a specifc bit range. Ex. BMS Self Test Fault
"Value": The value of the measurment
"ID": Field used to ID every type of message. For CAN: Hex_ID

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

        # Create dictionary for data and set the type
        self.data = self.extract_measurements(format_specifier)
        self.type = "CAN"


    """
    CREDIT: Mihir. N and Aarjav. J
    Will create a dictionary whose keys are the column headings to the pretty table
    and whose values are data in those columns. Dictionary is string to list.
    The list will be the same length as the number of rows in the pretty table.
    This is done to match list length to number of measurement in CAN message to list
    
    Parameters:
        format_specifier: object or file path 
        
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
        measurements = format_specifier.decode_message(int(self.message[8:12], 16), bytearray(map(lambda x: ord(x), self.message[12:20])))
        message = format_specifier.get_message_by_frame_id(int(self.message[8:12], 16))
        hex_id = "0x" + hex(self.message[8:12])[2:].upper()

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
            "ID": hex_id
        }

        # Now add each field to the list
        for name, data in measurements.items():
            display_data["Hex_ID"].append(hex_id)
            display_data["Source"].append(source)
            display_data["Class"].append(message.name)
            display_data["Measurement"].append(name)
            display_data["Value"].append(data)
        
        return display_data

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
