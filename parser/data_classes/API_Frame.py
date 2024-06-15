# Parameter imports. ADD AND REMOVE AS NEEDED
from parser.parameters import *
import struct
from time import strftime, localtime
from datetime import datetime



##Breaks API Frames into individul messages, sends messages back to create_message as individual CAN, IMU, or GPS messages

FRAME_DATA_POSITION = 18 #Start of first message in API Frame
BYTE_POSITION = 16 #where Identifier byte in API frame is located
FRAME_TYPE = 3 #API Overhead frame type identifer (0x90 for receive frame, 0x88 for local AT return, 0x97 for remote at Return)

##Function used to split API packets. Starts at FRAME_DATA_POSITION, which is the first position in the API frame where we have data
##Loops frame until end, grabbing each individual message by looping through message_size characters.
def split_api_packet(message, message_size, message_byte):
    return [bytes.fromhex(message_byte).decode('latin-1') + message[i: i + message_size] for i in range(FRAME_DATA_POSITION, len(message), message_size)]
    
def parse_api_packet(message) -> list:
    individual_messsages = []
    if message[FRAME_TYPE] == '\x90':
            if message[BYTE_POSITION] == CAN_BYTE:
                individual_messsages.extend(split_api_packet(message, CAN_MSG_LENGTH, CAN_BYTE))
            elif message[BYTE_POSITION] == IMU_BYTE:
                individual_messsages.extend(split_api_packet(message, IMU_MSG_LENGTH, IMU_BYTE))
            elif message[BYTE_POSITION] == GPS_BYTE:
                individual_messsages.extend(split_api_packet(message, GPS_MSG_LENGTH, GPS_BYTE))
        
    elif message[FRAME_TYPE] == '\x88':
        individual_messsages.extend(bytes.fromhex(LOCAL_AT_BYTE).decode('latin-1') + message)
    elif message[FRAME_TYPE] == '\x97':
        individual_messsages.extend(bytes.fromhex(REMOTE_AT_BYTE).decode('latin-1') + message)

    return individual_messsages