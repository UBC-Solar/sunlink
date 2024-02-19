import struct

"""
IMU Message data class. Assumes message parameter in constructor is a latin-1 decoded string.
Data fields are below:

REQUIRED (INFLUX) FIELDS:
    "Source": (list) "IMU"
    "Class": (list) A or G (for Accelerometer or Gyroscope)
    "Measurment": (list) X, Y, or Z (for the axis of the IMU)
    "Value": (list) value of the IMU message (rounded to 6 decimal places)
    "Timestamp": (list) timestamp of the IMU message 

DISPLAY FIELDS DICT:
    "display_data" : {
        "Type": (list) type of the IMU message (A or G),
        "Dimension": (list) dimension of the IMU message (X, Y, or Z),
        "Value": (list) value of the IMU message (rounded to 6 decimal places),
        "Timestamp": (list) timestamp of the IMU message
    }

self.type = "IMU"
"""
class IMU:
    def __init__(self, message: str) -> None:   
        # Parse all data fields and set type
        self.message = message
        self.data = self.extract_measurements()
        self.type = "IMU"

    """
    Extracts measurements from a IMU message based on a specified format
    Keys of the display_dict inside data dict are column headings.
    Values are data in columns.
    
    Parameters:
        None
                
    Returns:
        display_data dictionary with the form outlined in the class description
    """
    def extract_measurements(self,) -> dict:
        # Extract the parts of the message
        timestamp = self.message[:8]
        id = self.message[9:11]      # skip the @
        val = self.message[11:]

        # Convert the val part to a 32-bit float
        value = struct.unpack('>f', bytearray(val.encode('latin-1')))[0]

        data = {}
        
        # REQUIRED FIELDS
        data["Source"] = ["IMU"]
        data["Class"] = [id[0]]
        data["Measurement"] = [id[1]]
        data["Value"] = [round(value, 6)]
        data["Timestamp"] = [int(timestamp, 16)]

        # DISPLAY FIELDS
        data["display_data"] = {
            "Type": [id[0]],
            "Dimension": [id[1]],
            "Value": [round(value, 6)],
            "Timestamp": [int(timestamp, 16)],
        }
        
        return data

