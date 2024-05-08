import random
import struct
import time

# Get format specifiers
from parser.parameters import CAR_DBC

"""
Class to provide random message generaters for testing purposes.
Currently creates random messages for CAN, GPS, and IMU.
"""
class RandomMessage:
    """
    Returns a random message of a random type (Currently CAN, GPS, or IMU).
    
    Parameters:
        message_types - list of message types to choose from (the randomList arg in parser)
        
    Returns:
        string - random message of a random type as a string with latin-1 decoding
    """
    def random_message_str(self, message_types) -> str:
        """
        Randomly selects a message type from the provided list and returns a random message of that type.
        """

        message_type = random.choice(message_types).upper()  # Convert to uppercase
        if message_type == 'CAN':
            return self.random_can_str()
        elif message_type == 'GPS':
            return self.random_gps_str()
        elif message_type == 'IMU':
            return self.random_imu_str()

    """
    CREDIT: Mihir .N taken from link_telemetry

    Parameters
        None

    Returns
        string - random CAN message as string with latin-1 decoding:
                 "TTTTTTTTIIIIDDDDDDDDL"
                    T - timestamp       = 8 bytes
                    I - identifier      = 4 bytes
                    D - data            = 8 bytes
                    L - data length     = 1 byte
    """
    def random_can_str(self) -> str:
        """
        Generates a random string (which represents a CAN message) that mimics
        the format sent over by the telemetry board over radio. This function
        is useful when debugging the telemetry system.
        """
        
        # collect CAN IDs
        can_ids = list()
        for message in CAR_DBC.messages:
            can_ids.append(message.frame_id)

        # Convert current time to a 32 bit unsigned integer to latin-1 string 
        # Convert current time to float bytes to latin-1 string 
        current_time = time.time()
        current_time_bytes = struct.pack('>d', current_time)
        current_time_str = current_time_bytes.decode('latin-1')

        # random identifier
        random_identifier = random.choice(can_ids)
        random_id_str = random_identifier.to_bytes(4, 'big').decode('latin-1')  # to encoded string

        # random data 8 bytes. Then 2 HEX to ASCII
        random_data = random.randint(0, pow(2, 64))
        random_data_str = "{0:0{1}x}".format(random_data, 16)
        hex_pairs = [random_data_str[i:i+2] for i in range(0, len(random_data_str), 2)] # split into pairs
        ascii_chars = [chr(int(h, 16)) for h in hex_pairs]  # convert to ASCII
        random_data_str = ''.join(ascii_chars)  # join into string

        # fixed data length
        data_length = "8"

        # collect into single string
        can_str = current_time_str + "#" + random_id_str + random_data_str \
             + data_length
        return can_str
    
    """
    Returns a random GPS message in NMEA format.
    Latitude: %.6f %c, Longitude: %.6f %c, Altitude: %.2f meters, HDOP: %.2f, Satellites: %d, Fix: %d, Time: %s
    
    Parameters:
        None
    
    Returns:
        string - random GPS message in NMEA format as a string with latin-1 decoding
    """
    def random_gps_str(self) -> str:
        latitude = random.uniform(-90, 90)
        latSide = 'S' if latitude < 0 else 'N'
        longitude = random.uniform(-180, 180)
        lonSide = 'W' if longitude < 0 else 'E'
        altitude = random.uniform(0, 10000)
        hdop = random.uniform(0, 50)
        satelliteCount = random.randint(0, 12)
        fix = random.randint(0, 1)
        lastMeasure = round(time.time(), 1)

        nmea_msg = "Latitude: {:.6f} {}, Longitude: {:.6f} {}, Altitude: {:.2f} meters, HDOP: {:.2f}, Satellites: {}, Fix: {}, Time: {}".format(
            abs(latitude), latSide,
            abs(longitude), lonSide,
            altitude, hdop,
            satelliteCount, fix,
            lastMeasure)

        return nmea_msg

    """
    Returns a random IMU message in the format:
    
    Parameters:
        None
    
    Returns:
        string - random IMU message in the format as a string with latin-1 decoding:
                 "TTTTTTTT@IIFFFF"
                    T - timestamp       = 8 bytes
                    I - identifier      = 2 bytes
                    F - data            = 4 bytes
    """
    def random_imu_str(self) -> str:
        # Convert current time to float bytes to latin-1 string 
        current_time = time.time()
        current_time_bytes = struct.pack('>d', current_time)
        current_time_str = current_time_bytes.decode('latin-1')


        # Generate a random identifier
        types = ['A', 'G']
        dimensions = ['X', 'Y', 'Z']
        identifier = random.choice(types) + random.choice(dimensions)

        # Generate a random value
        value = random.uniform(-1000, 1000)
        value_bytes = struct.pack('>f', value)

        # Combine all parts into a single bytes object
        imu_bytes = current_time_str + "@" + identifier + value_bytes.decode('latin-1')

        return imu_bytes
    