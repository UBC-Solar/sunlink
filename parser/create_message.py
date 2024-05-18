# Types of messages
from parser.data_classes.CAN_Msg import CAN      # CAN message
from parser.data_classes.IMU_Msg import IMU      # IMU message
from parser.data_classes.GPS_Msg import GPS      # GPS message
from parser.data_classes.Local_AT_Command_Return import AT as AT_LOCAL
from parser.data_classes.Remote_AT_Command_Return import AT as AT_REMOTE
from parser.parameters import *     # For mins and maxes of messages



"""
Factory method for creating a Message object based on the message type
To add new message types simply add a new elif statement:
------------------------------------------------------
elif len(message) == <length of message>:
    return <Message Subclass>(message)
------------------------------------------------------

Decision based on LENGTH of the message (see parser/parameters.py): 

Parameters:
    message: the message to be parsed
    
Returns:
    a message object (CAN, GPS, IMU, etc.)
"""
def create_message(message: str):
    try:
        if message[0] == CAN_BYTE:
            return CAN(message[1:])
        elif message[0] == GPS_BYTE:
            return GPS(message[1:])
        elif message[0] == IMU_BYTE:
            return IMU(message[1:])
        elif message[0] == LOCAL_AT_BYTE:
            return AT_LOCAL(message[1:])
        elif message[0] == REMOTE_AT_BYTE:
            return AT_REMOTE(message[1:])
        else:
            raise Exception(
                f"Message byte of {message[0]} is not a valid byte for any message type\n"
                f"      Message: {message}\n"
                f"      Hex Message: {message.encode('latin-1').hex()}"
            )
        
            raise Exception(f"Message length of {len(message)} is not a valid length for any message type")
    except Exception as e:
        raise Exception(
            f"{ANSI_BOLD}Failed in create_message{ANSI_ESCAPE}:\n"
            f"      {e}"
        )
    