import struct

# Superclass import

"""
Subclass IMU implements the extract_measurements and getter
methods from the interface Message. Assumes message parameter in 
constructor is a UART message from the Radio Receiver (serial.readLine())
Data fields are below:

'timestamp': (string) timestamp of the IMU message (All D's right now)
'identifier':        (string) ID of the IMU message
'value':     (float) value of the IMU message (rounded to 6 decimal places)
'type':      (string) type of the IMU message (A or G)
'dimension': (string) dimension of the IMU message (X, Y, or Z)

self.type = "IMU"
"""
class IMU:
    def __init__(self, message: str) -> None:   
        # Parse all data fields and set type
        self.data = self.parseIMU_str(message)
        self.type = "IMU"

    """
    Extracts measurements from a IMU message based on a specified format
    Keys of the dict are column headings. Values are data (as strings) in column.
    
    Parameters:
        format_specifier: None for IMU messages (as of now)
        
    Returns:
        display_data dictionary with the following form
        {
            "ID": [],
            "Dimension": [],
            "Value": []
        }
    """
    def extract_measurements(self, format_specifier=None) -> dict:
        display_data = {
            "ID": [self.data['type']],
            "Dimension": [self.data['dimension']],
            "Value": [str(self.data['value'])]
        }
        return display_data

    """
    Parses a IMU message string into a dictionary of fields
    
    Parameters:
        str_msg: the IMU message as a string
    
    Returns:
        a dictionary containing the data fields of the IMU message
    """
    def parseIMU_str(self, str_msg: str) -> dict:
        # Extract the parts of the message
        timestamp = str_msg[:8]
        id = str_msg[9:11]      # skip the @
        data = str_msg[11:]

        # Convert the data part to a 32-bit float
        value = struct.unpack('>f', bytearray(data.encode('latin1')))[0]

        # Create the output dictionary
        output = {
            'timestamp': timestamp,
            'identifier': id,
            'value': round(value, 6),
            'type': id[0],
            'dimension': id[1]
        }
        return output

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
        