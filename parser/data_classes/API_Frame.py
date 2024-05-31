# Parameter imports. ADD AND REMOVE AS NEEDED
from parser.parameters import *
import struct
from time import strftime, localtime
from datetime import datetime

FRAME_DATA_POSITION = 19

def split_api_packet(message, message_size, message_byte):
    return [message_byte + message[i: i + message_size] for i in range(FRAME_DATA_POSITION, len(message), message_size)]
    
def parse_api_packet(message):
    individual_messsages = []
    if message[3] == '10':
            if message[17] == CAN_BYTE:
                individual_messsages.extend(split_api_packet(message, CAN_MSG_LENGTH, CAN_BYTE))
            elif message[17] == IMU_BYTE:
                individual_messsages.extend(split_api_packet(message, IMU_MSG_LENGTH, IMU_BYTE))
            elif message[17] == GPS_BYTE:
                individual_messsages.extend(split_api_packet(message, GPS_MSG_LENGTH, GPS_BYTE))
        
    elif message[3] == '88':
        individual_messsages.extend(LOCAL_AT_BYTE + message)
    elif message[3] == '97':
        individual_messsages.extend(REMOTE_AT_BYTE + message)

    for message in individual_messsages:
        message = bytes.fromhex(message).decode('latin-1')
        create_message(message)