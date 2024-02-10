"""
<MESSAGE_NAME> message wrapper class. <MESSAGE_NAME>.data[''] fields are:

"<FIELD_NAME>": <DESCRIPTION>
"ID": ID of <MESSAGE_NAME> messages chosen to be ______

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
        self.data = self.extract_measurements(format_specifier=None)
        self.type = "<MESSAGE_NAME>"


    """
    Will create a dictionary whose keys are the column headings to the pretty table
    and whose values are data in those columns. Table printed when processing response from parser
    in link_telemetry.py
    
    Parameters:
        format_specifier: object that can be used to decode the message (DEPENDS ON YOUR MESSAGE)
        
    Returns:
        dictionary with the following form
        {
            "<FIELD_NAME>": [val1, val2, val3, ...],
            "ID": ID of <MESSAGE_NAME> messages chosen to be ______
        }
    """
    def extract_measurements(self, format_specifier=None) -> dict:
        data = {}
        return data

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
