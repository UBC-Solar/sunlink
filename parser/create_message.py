# Types of messages
from parser.CAN_Msg import CAN      # CAN message
from parser.IMU_Msg import IMU      # IMU message
from parser.GPS_Msg import GPS      # GPS message

# Lengths of messages for differentiating message types
CAN_LENGTH_MIN      = 21
CAN_LENGTH_MAX      = 23
GPS_LENGTH_MIN      = 117
GPS_LENGTH_MAX      = 128
IMU_LENGTH_MIN      = 15
IMU_LENGTH_MAX      = 17


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
    a message object (CAN, GPS, IMU, etc.)
"""
def create_message(message: str):
    if CAN_LENGTH_MIN <= len(message) <= CAN_LENGTH_MAX:
        return CAN(message)
    elif GPS_LENGTH_MIN <= len(message) <= GPS_LENGTH_MAX:
        return GPS(message)
    elif IMU_LENGTH_MIN <= len(message) <= IMU_LENGTH_MAX:
        return IMU(message)
    else:
        raise Exception("Message length is not a valid length for any message type")
    