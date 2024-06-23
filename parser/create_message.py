# Types of messages
from parser.data_classes.CAN_Msg import CAN      # CAN message
from parser.data_classes.IMU_Msg import IMU      # IMU message
from parser.data_classes.GPS_Msg import GPS      # GPS message
from parser.data_classes.Local_AT_Command_Return import ATL
from parser.data_classes.Remote_AT_Command_Return import ATR
from parser.parameters import *     # For mins and maxes of messages
from parser.data_classes.API_Frame import parse_api_packet

"""
Factory method for creating a Message object based on the message type
To add new message types simply add a new message byte to parameters, and make sure to append this byte in the approriate locations.
------------------------------------------------------
elif message[0] == MessageTypeByte:
    return <Message Subclass>(message)
------------------------------------------------------

Decision based on MessageTypeByte of the message (see parser/parameters.py): 

Parameters:
    message: the message to be parsed
    
Returns:
    a message object (CAN, GPS, IMU, etc.)
"""
def create_message(message: str):
    try:
        if message[0]  == bytes.fromhex(CAN_BYTE).decode('latin-1'):
            return CAN(message[0:])
        elif message[0] == bytes.fromhex(GPS_BYTE).decode('latin-1'):
            return GPS(message[1:])
        elif message[0] == bytes.fromhex(IMU_BYTE).decode('latin-1'):
            return IMU(message[1:])
        elif message[0] == bytes.fromhex(LOCAL_AT_BYTE).decode('latin-1'):
            return ATL(message[1:])
        elif message[0] == bytes.fromhex(REMOTE_AT_BYTE).decode('latin-1'):
            return ATR(message[1:])
        else:
            raise Exception(
            f"Message byte of {message[0]} is not a valid byte for any message type\n"
            f"      Message: {message}\n"
            f"      Hex Message: {message.encode('latin-1').hex()}"
        )
        
    except Exception as e:
        raise Exception(
            f"{ANSI_BOLD}Failed in create_message{ANSI_ESCAPE}:\n"
            f"      {e}"
            f"Message byte of {message[0]} is not a valid byte for any message type\n"
        )
