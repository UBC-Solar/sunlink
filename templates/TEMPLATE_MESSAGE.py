# Parameter imports. ADD AND REMOVE AS NEEDED
from parser.parameters import *


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
    <REPLACE_THIS> Gets example data
    
    Parameters:
        <REPLACE_THIS> None
    
    Returns:
        <REPLACE_THIS> None
    """
    def get_example_data(self):
        try:
            return 0
        except Exception as e:
            generate_exception(e, "get_example_data")


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
        # Set all fields to None initially
        example_data = None

        try:
            example_data = self.get_example_data()
        except Exception as e:
            raise Exception(
                f"Could not extract {ANSI_BOLD}<MESSAGE_NAME>{ANSI_ESCAPE} message with properties: \n"
                f"      Message Length = {len(self.message)} \n"
                f"      Message Hex Data = {self.message.encode().hex()} \n\n"
                f"      {ANSI_RED}Error{ANSI_ESCAPE}: \n"
                f"      {e} \n"
                f"      {ANSI_GREEN}Function Call Details (self.message[] bytes -> hex numbers):{ANSI_ESCAPE} \n"
                f"        {ANSI_BOLD}get_example_data(){ANSI_ESCAPE}, \n"
                f"          - gets the example data \n"
            )
        

        data = {}

        # SET REQUIRED FIELDS

        # SET DISPLAY FIELDS

        return data
    