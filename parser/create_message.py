# Types of messages
from parser.data_classes.CAN_Msg import CAN      # CAN message
from parser.data_classes.IMU_Msg import IMU      # IMU message
from parser.data_classes.GPS_Msg import GPS      # GPS message
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
        if CAN_LENGTH_MIN <= len(message) <= CAN_LENGTH_MAX:
            return CAN(message)
        elif GPS_LENGTH_MIN <= len(message) <= GPS_LENGTH_MAX:
            return GPS(message)
        elif IMU_LENGTH_MIN <= len(message) <= IMU_LENGTH_MAX:
            return IMU(message)
        else:
            raise Exception(
                f"Message length of {len(message)} is not a valid length for any message type\n"
                f"      Message: {message}\n"
                f"      Hex Message: {message.encode('latin-1').hex()}"
            )
        
            raise Exception(f"Message length of {len(message)} is not a valid length for any message type")
    except Exception as e:
        return "NOPE"
        raise Exception(
            f"{ANSI_BOLD}Failed in create_message{ANSI_ESCAPE}:\n"
            f"      {e}"
        )
    