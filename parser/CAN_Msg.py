import cantools
from pathlib import Path
import sys

"""
Subclass CAN implements the extract_measurements and getter
methods from the interface Message. Data fields are:

REQUIRED FIELDS:
    "Source": (list) The board which the message came from
    "Class": (list) The class of the message (Ex. Voltage Sensors Data)
    "Measurment": (list) Specifc measurement name in this class (Ex. Volt Sensor 1, Volt Sensor 2)
    "Value": (list) The value of the associated measurement
    "ID": Chosen to be the Hex_ID

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
        # Load the DBC file   
        DBC_FILE = Path("./dbc/brightside.dbc")

        if not DBC_FILE.is_file():
            print(f"Unable to find expected existing DBC file: \"{DBC_FILE.absolute()}\"")
            sys.exit(1)
            
        self.CAR_DBC = cantools.database.load_file(DBC_FILE)

        self.message = message  
        self.data = self.extract_measurements()
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
        display_data dictionary with form outlined in the class description
    """
    def extract_measurements(self) -> dict:      
        timestamp: int = int(self.message[0:8], 16)
        id: str = self.message[8:12]
        data: str = self.message[12:20]

        identifier = int(id, 16)  
        data_bytes = bytearray(map(lambda x: ord(x), data))
        hex_id = "0x" + hex(identifier)[2:].upper()

        measurements = self.CAR_DBC.decode_message(identifier, data_bytes)
        message = self.CAR_DBC.get_message_by_frame_id(identifier)

        # where the data came from
        sources: list = message.senders

        source: str
        if len(sources) == 0:
            source = "UNKNOWN"
        else:
            source = sources[0]

        # Initilization
        display_data = {
            "Source": [],
            "Class": [],
            "Measurement": [],
            "Value": [],
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
        for name, data in measurements.items():
            # REQUIRED FIELDS
            display_data["Source"].append(source)
            display_data["Class"].append(message.name)
            display_data["Measurement"].append(name)
            display_data["Value"].append(data)
        
            # DISPLAY FIELDS
            display_data["display_data"]["Hex_ID"].append(hex_id)
            display_data["display_data"]["Source"].append(source)
            display_data["display_data"]["Class"].append(message.name)
            display_data["display_data"]["Measurement"].append(name)
            display_data["display_data"]["Timestamp"].append(timestamp)
            display_data["display_data"]["Value"].append(data)

        return display_data

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
