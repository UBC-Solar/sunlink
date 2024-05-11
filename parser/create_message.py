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
# def split_api_packet(message, message_size, message_byte):
#     return [message_byte + message[i: i + message_size] for i in range(19, len(message), message_size)]
#     try:
#         individual_messsages = []
#         if message[3] == '10':
#                 if message[17] == CAN_BYTE:
#                     individual_messsages.extend(split_api_packet(message, CAN_MSG_LENGTH, CAN_BYTE))
#                 elif message[17] == IMU_BYTE:
#                     individual_messsages.extend(split_api_packet(message, IMU_MSG_LENGTH, IMU_BYTE))
#                 elif message[17] == GPS_BYTE:
#                     individual_messsages.extend(split_api_packet(message, GPS_MSG_LENGTH, GPS_BYTE))
            
#         elif message[3] == '88':
#             individual_messsages.extend(LOCAL_AT_BYTE + message)
#         elif message[3] == '97':
#             individual_messsages.extend(REMOTE_AT_BYTE + message)
    
#     ## [bytes.fromhex(part).decode('latin-1') for part in smaller_parts] 

#         for part in individual_messsages:
#             part = bytes.fromhex(part).decode('latin-1')
def create_message(message: str):
    if message[0] == "7E" and (message[4] == ("88" or "97")):
        parse_api_packet(message)
    else:
        try:
            if part[0] == CAN_BYTE:
                return CAN(part[1:])
            elif part[0] == GPS_BYTE:
                return GPS(part[1:])
            elif message[0] == IMU_BYTE:
                return IMU(part[1:])
            elif message[0] == LOCAL_AT_BYTE:
                return AT_LOCAL(part[1:])
            elif message[0] == REMOTE_AT_BYTE:
                return AT_REMOTE(part[1:])
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
        )
    