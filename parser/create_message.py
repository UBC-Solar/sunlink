# Types of messages
from parser.CAN_Msg import CAN      # CAN message
from parser.IMU_Msg import IMU      # IMU message
from parser.GPS_Msg import GPS      # GPS message

# Lengths of messages for differentiating message types
CAN_LENGTH_MIN      = 20
CAN_LENGTH_MAX      = 23
GPS_LENGTH_MIN      = 117
GPS_LENGTH_MAX      = 128
IMU_LENGTH_MIN      = 15
IMU_LENGTH_MAX      = 17

# Indexing for format specifier list
CAN_INDEX           = 0


"""
Factory method for creating a Message object based on the message type
To add new message types simply add a new elif statement:
------------------------------------------------------
elif len(message) == <length of message>:
    return <Message Subclass>(message)
------------------------------------------------------

Decision based on LENGTH of the message:

CAN message: 22 bytes
GPS message: 200 bytes
IMU message: 17 bytes

Parameters:
    message: the message to be parsed
    format_specifer_list: list of format specifiers for each message type
                          [DBC Object, None, None, ...]
                          When other specifiers are added, the index will be used to select the correct one
    
Returns:
    a message object (CAN, GPS, IMU, etc.)
"""
def create_message(message: str, format_specifier_list: list):
    if CAN_LENGTH_MIN <= len(message) <= CAN_LENGTH_MAX:
        return CAN(message, format_specifier_list[CAN_INDEX])
    elif GPS_LENGTH_MIN <= len(message) <= GPS_LENGTH_MAX:
        return GPS(message)
    elif IMU_LENGTH_MIN <= len(message) <= IMU_LENGTH_MAX:
        return IMU(message)
    else:
        raise Exception("Message length is not a valid length for any message type")
    