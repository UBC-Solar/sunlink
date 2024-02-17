"""
<MESSAGE_NAME> message wrapper class. <MESSAGE_NAME>.data[''] fields are:

(See 'CAN_Msg.py', 'GPS_Msg.py', or 'IMU_Msg.py' for example)

REQUIRED FILEDS
    "Source": (list) <DESCRIPTION> 
    "Class": (list) <DESCRIPTION> 
    "Measurment": (list) <DESCRIPTION> 
    "Value": (list) <DESCRIPTION> 
    "ID": ID of <MESSAGE_NAME> messages chosen to be ______

DIPSLAY FIELDS
    "display_data" : {
        "<FIELD_NAME>": (list) <DESCRIPTION>
    }

self.type = "<MESSAGE_NAME>"
"""
class MESSAGE_NAME:
    def __init__(self, message: str) -> None:      
        """
        In general, the init should set the data dictionary 
        based on parsing the message string. The type should be set to the name of the message.
        
        See 'CAN_Msg.py', 'GPS_Msg.py' and 'IMU_Msg.py' for good working examples.
        """

        self.message = message
        self.data = self.extract_measurements()
        self.type = "<MESSAGE_NAME>"


    """
    Will create a dictionary whose keys are the column headings to the pretty table
    and whose values are data in those columns. Table printed when processing response from parser
    in link_telemetry.py
    
    Parameters:
        None
        
    Returns:
        dictionary with the form outlined in the class description above
    """
    def extract_measurements(self) -> dict:
        data = {}

        # REQUIRED FIELDS

        # DISPLAY FIELDS

        return data

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
