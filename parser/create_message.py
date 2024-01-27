from parser.Message import Message      # Interface 

# Types of messages
from parser.CAN_Msg import CAN      # CAN message
from parser.IMU_Msg import IMU      # IMU message
from parser.GPS_Msg import GPS      # GPS message

# Lengths of messages for differentiating message types
CAN_LENGTH = 28
GPS_LENGTH = 200
IMU_LENGTH = 17


# TODO: Figure out length of GPS message
# TODO: Figure out length of IMU message


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
    
Returns:
    a Message object (CAN, GPS, IMU, etc.) and the type of the message as a tuple
"""
def create_message(message: bytes) -> tuple[Message, str]:
    if len(message) == CAN_LENGTH:
        return CAN(message), "CAN"
    elif len(message) == GPS_LENGTH:
        return GPS(message), "GPS"
    elif len(message) == IMU_LENGTH:
        return IMU(message), "IMU"
    else:
        raise Exception("Message length is not a valid length for any message type")
    