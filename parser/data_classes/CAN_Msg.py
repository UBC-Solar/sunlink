import struct
from parser.parameters import CAR_DBC

"""
CAN Message data class. Data fields are:

REQUIRED (INFLUX) FIELDS:
    "Source": (list) The board which the message came from
    "Class": (list) The class of the message (Ex. Voltage Sensors Data)
    "Measurment": (list) Specifc measurement name in this class (Ex. Volt Sensor 1, Volt Sensor 2)
    "Value": (list) The value of the associated measurement
    "Timestamp": (list) The time the message was sent

DISPLAY FIELDS:
    "display_data" : {
        "Hex_ID": (list) The ID of the CAN message in hex
        "Source": (list) The board which the message came from
        "Class": (list) The class of the message (Ex. Voltage Sensors Data)
        "Measurment": (list) Specifc measurement name in this class (Ex. Volt Sensor 1, Volt Sensor 2)
        "Value": (list) The value of the associated measurement
    }

self.type = "CAN"
"""
class CAN:
    """
    CREDIT: Mihir. N for his implementation
    CHANGES:
        data field is now 8 bytes (Before: FF is sent as 2 letter Fs, now it is sent as 1 byte char with value 255)
    """
    def __init__(self, message: str) -> None: 
        self.message = message  
        self.data = self.extract_measurements()
        self.type = "CAN"


    """
    CREDIT: Mihir. N and Aarjav. J
    Will create a dictionary whose display_dict key is another dictionary.
    This nested dictionary contains are the column headings to the pretty table
    and whose values are data in those columns. 
    The list will be the same length as the number of rows in the pretty table.
    This is done to match list length to number of measurement in CAN message to list
    
    Parameters:
        None
        
    Returns:
        display_data dictionary with form outlined in the class description
    """
    def extract_measurements(self) -> dict:      
        timestamp = struct.unpack('>d', self.message[:8].encode('latin-1'))[0]

        id = None
        raw_data = None
        # Non extended ID check
        if (len(self.message) < 24):
            id: str = self.message[8:12]
            raw_data: str = self.message[12:20]
        else:
            id: str = self.message[8:16]
            raw_data: str = self.message[16:24]

        # convert back latin-1 string to bytes to float
        timestamp = float(timestamp)

        identifier = int(id, 16)  
        data_bytes = bytearray(map(lambda x: ord(x), raw_data))
        hex_id = "0x" + hex(identifier)[2:].upper()

        measurements = CAR_DBC.decode_message(identifier, data_bytes)
        message = CAR_DBC.get_message_by_frame_id(identifier)

        # where the data came from
        sources: list = message.senders

        source: str
        if len(sources) == 0:
            source = "UNKNOWN"
        else:
            source = sources[0]

        # Initilization
        data = {
            "Source": [],
            "Class": [],
            "Measurement": [],
            "Value": [],
            "Timestamp": [],
            "ID": hex_id,
            "display_data": {   
                "Hex_ID": [],
                "Source": [],
                "Class": [],
                "Measurement": [],
                "Value": [],
                "Timestamp": []
            }
        }

        # Now add each field to the list
        for name, dbc_data in measurements.items():
            # REQUIRED FIELDS
            data["Source"].append(source)
            data["Class"].append(message.name)
            data["Measurement"].append(name)
            data["Value"].append(dbc_data)
            data["Timestamp"].append(round(timestamp, 3))
        
            # DISPLAY FIELDS
            data["display_data"]["Hex_ID"].append(hex_id)
            data["display_data"]["Source"].append(source)
            data["display_data"]["Class"].append(message.name)
            data["display_data"]["Measurement"].append(name)
            data["display_data"]["Timestamp"].append(round(timestamp, 3))
            data["display_data"]["Value"].append(dbc_data)

        return data
    