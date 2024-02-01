import random
import struct
import time
import cantools
from pathlib import Path

import sys
sys.path.append('sunlink/parser')

# Test imports
from Message import Message
from create_message import create_message

"""
Class to provide random message generaters for testing purposes.
Currently creates random messages for CAN, GPS, and IMU.
"""
class RandomMessage:
    """
    CREDIT: Mihir .N taken from link_telemetry

    Parameters
        dbc - dbc object from cantools library

    Returns
        byte array - random CAN message as an encoded string with latin-1 encoding:
                 "TTTTTTTTIIIIDDDDDDDDL\n"
                    T - timestamp       = 8 bytes
                    I - identifier      = 4 bytes
                    D - data            = 8 bytes
                    L - data length     = 1 byte
    """
    def random_can_bytes(self, dbc) -> bytes:
        """
        Generates a random string (which represents a CAN message) that mimics
        the format sent over by the telemetry board over radio. This function
        is useful when debugging the telemetry system.
        """
        
        # collect CAN IDs
        can_ids = list()
        for message in dbc.messages:
            can_ids.append(message.frame_id)

        # 0 to 2^32
        random_timestamp = random.randint(0, pow(2, 32))
        random_timestamp_str = "{0:0{1}x}".format(random_timestamp, 8)

        # random identifier
        random_identifier = random.choice(can_ids)
        random_id_str = "{0:0{1}x}".format(random_identifier, 4)

        # random data 8 bytes. Then 2 HEX to ASCII
        random_data = random.randint(0, pow(2, 64))
        random_data_str = "{0:0{1}x}".format(random_data, 16)
        hex_pairs = [random_data_str[i:i+2] for i in range(0, len(random_data_str), 2)] # split into pairs
        ascii_chars = [chr(int(h, 16)) for h in hex_pairs]  # convert to ASCII
        random_data_str = ''.join(ascii_chars)  # join into string

        # fixed data length
        data_length = "8"

        # collect into single string
        can_str = random_timestamp_str + random_id_str + random_data_str \
             + data_length + "\n"

        return can_str.encode("latin-1")

    """
    Returns a random GPS message in NMEA format.
    Latitude: %.6f %c, Longitude: %.6f %c, Altitude: %.2f meters, HDOP: %.2f, Satellites: %d, Fix: %d, Time: %s
    
    Parameters:
        None
    
    Returns:
        byte array - random GPS message in NMEA format as a string encoded to bytes with latin-1 encoding
    """
    def random_gps_bytes(self) -> bytes:
        latitude = random.uniform(-90, 90)
        latSide = 'S' if latitude < 0 else 'N'
        longitude = random.uniform(-180, 180)
        lonSide = 'W' if longitude < 0 else 'E'
        altitude = random.uniform(0, 10000)
        hdop = random.uniform(0, 50)
        satelliteCount = random.randint(0, 12)
        fix = random.randint(0, 1)
        lastMeasure = "{:06.2f}".format(random.uniform(0, 60*60*24))  # seconds in a day

        nmea_msg = "Latitude: {:.6f} {}, Longitude: {:.6f} {}, Altitude: {:.2f} meters, HDOP: {:.2f}, Satellites: {}, Fix: {}, Time: {}".format(
            abs(latitude), latSide,
            abs(longitude), lonSide,
            altitude, hdop,
            satelliteCount, fix,
            lastMeasure)

        # Convert the NMEA message to hexadecimal
        nmea_msg = nmea_msg.encode("latin-1")

        return nmea_msg

    """
    Returns a random IMU message in the format:
    
    Parameters:
        None
    
    Returns:
        byte array - random IMU message in the format as a string encoded to bytes:
                 "TTTTTTTT@IIFFFF\n"
                    T - timestamp       = 8 bytes
                    I - identifier      = 2 bytes
                    F - data            = 4 bytes
    """
    def random_imu_bytes(self) -> bytes:
        # Generate a random timestamp
        timestamp = random.randint(0, pow(2, 32))
        timestamp = "{0:0{1}x}".format(timestamp, 8)

        # Generate a random identifier
        types = ['A', 'G']
        dimensions = ['X', 'Y', 'Z']
        identifier = random.choice(types) + random.choice(dimensions)

        # Generate a random value
        value = random.uniform(-1000, 1000)
        value_bytes = struct.pack('>f', value)

        # Combine all parts into a single bytes object
        imu_bytes = timestamp.encode('latin-1') + b"@" + identifier.encode('latin-1') + value_bytes

        return imu_bytes
