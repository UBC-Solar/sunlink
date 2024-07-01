import random
import struct
import time
from datetime import timedelta

# Get format specifiers
from parser.parameters import CAR_DBC
from parser.parameters import *
from parser.radio import*

# Constants
SECONDS_IN_DAY = 86400

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
        elif message_type == 'ATL':
            return self.random_at_local_str()
        elif message_type == 'ATR':
            return self.random_at_remote_str()
        elif message_type == 'API':
            return self.random_api_frame_str()

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
        can_str = bytes.fromhex(CAN_BYTE).decode('latin1') + current_time_str + "#" + random_id_str + random_data_str \
             + data_length + bytes.fromhex("0a0d").decode('latin-1')
    
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
        current_time = time.time() % SECONDS_IN_DAY
        hours = int(current_time // 3600)
        minutes = int(current_time // 60) % 60
        seconds = int(current_time % 60)
        lastMeasure = "{:02d}{:02d}{:02d}".format(hours, minutes, seconds)

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
        imu_bytes = bytes.fromhex(IMU_BYTE).decode('latin-1') + current_time_str + "@" + identifier + value_bytes.decode('latin-1') + bytes.fromhex("0d0a").decode('latin-1')
        return imu_bytes
    



    """
    Returns a random AT Local Return message in the 0x88 frame Type:
    
    Parameters:
        None
    
    Returns:
        string - random AT local return message in the format as a string with latin-1 decoding (each 1 byte):
                 1. 7E - start delimiter
                 2. LSB
                 3. MSB
                 4. Frame Type
                 5. Frame Id
                 6 - 7: AT Command
                 8: Command Status
                 9 -> n-1: Command Data
                 n: Checksum
    """
    def random_at_local_str(self) -> str:

        start_delimiter = '7E'
        frame_type = '88'
        frame_id = '01'
        at_command =   random.choice(['4442','4744', '4552',])
        command_status = random.choice(['00','01','02','03','00','00'])

        #if command is unsuccesful, there will be no data field
        if command_status == '00':
            
            command_data = hex(random.randint(16,255))[2:]
            message_contents = frame_type + frame_id + at_command + command_status + command_data
            msb = generate_msb(message_contents)
            lsb = generate_lsb(message_contents)
            checksum = generate_checksum(message_contents)
            api_frame = start_delimiter + msb + lsb + frame_type + frame_id  + at_command + command_status + command_data + checksum
        
        else:

            message_contents = frame_type + frame_id  + at_command + command_status
            msb = generate_msb(message_contents)
            lsb = generate_lsb(message_contents)
            checksum = generate_checksum(message_contents)
            api_frame = start_delimiter + msb + lsb + frame_type + frame_id + at_command + command_status + checksum
        
        return bytes.fromhex(api_frame).decode('latin-1')



        

    """
    Returns a random AT Remote Return message in the 0x97 frame Type:
    
    Parameters:
        None
    
    Returns:
        string - random AT remote return message in the format as a string with latin-1 decoding (each 1 byte):
                 1. 7E - start delimiter
                 2. LSB
                 3. MSB
                 4. Frame Type
                 5. Frame Id
                 6 - 13: 64 bit address
                 14-15: 16 bit address
                 16-17: AT Command
                 18 -> n-1: Command Data
                 n: Checksum
    """
    def random_at_remote_str(self) -> str:

        start_delimiter = '7E'
        frame_type = '88'
        frame_id = '01'
        dest_address_long = '0000000000000000'
        dest_address_short = 'FeFe'
        at_command =   random.choice(hex_commandlist)
        command_status = random.choice(['00','01','02','03','00','00'])

        #if command is unsuccesful, there will be no data field
        if command_status == '00':
            
            command_data = hex(random.randint(16,255))[2:]
            message_contents = frame_type + frame_id + dest_address_long + dest_address_short + at_command + command_status + command_data
            msb = generate_msb(message_contents)
            lsb = generate_lsb(message_contents)
            checksum = generate_checksum(message_contents)
            api_frame = start_delimiter + msb + lsb + frame_type + frame_id  + dest_address_long + dest_address_short + at_command + command_status + command_data + checksum
        
        else:

            message_contents = frame_type + frame_id + dest_address_long + dest_address_short  + at_command + command_status
            msb = generate_msb(message_contents)
            lsb = generate_lsb(message_contents)
            checksum = generate_checksum(message_contents)
            api_frame = start_delimiter + msb + lsb + frame_type + frame_id + dest_address_long + dest_address_short + at_command + command_status + checksum
        
        return bytes.fromhex(api_frame).decode('latin-1')



    """
    Returns a random API FRAME in the 0x90 Receive Packet Format:
    
    Parameters:
        None
    
    Returns:
        API FRAME with following format in bytes:
                 1. Start Delimiter
                 2 -3: Length (MSB, LSB)
                 4: Frame TypE
                 5-12:  64 Bit Source Address
                 13-14: 16 Bit Source Address
                 15: Receive Options
                 16-n: RF Data
                 N: Checksum

    """
    def random_api_frame_str(self) -> str:
        
        #set up constant API Overhead parameters
        start_delimiter = '7E'
        frame_type = '90'
        source_address_long = '0000000000000000'
        source_address_short = 'fefe'
        recieve_options = '00'

        
        message_count =  16 

        message_type = random.choice([CAN_BYTE]) #Other messages are supported, just not relevant for now. 
        messages = ""

       
        if message_type == CAN_BYTE:    
            for i in range(20):
                messages = messages +  self.random_can_str()[1:]
        elif message_type == GPS_BYTE:
            for i in range(1):
                messages = messages +  self.random_gps_str()
        elif message_type == IMU_BYTE:
            for i in range(20):
                messages = messages + self.random_imu_str()[1:]

        #turn messages into hex
        message = messages.encode('latin-1')
        message_hex = message.hex()
        
        #collect all information between length and checksum to help calculate length and checksum
        message_contents = source_address_long + source_address_short + recieve_options + frame_type  + message_hex + hex(message_count)[2:] + message_type
        
        #get checksum, lsb, and msb fields for frame
        msb = generate_msb(message_contents)
        lsb = generate_lsb(message_contents)
        checksum = generate_checksum(message_contents)
       
        api_frame = start_delimiter + msb + lsb + frame_type + source_address_long + source_address_short + recieve_options + message_type + hex(message_count)[2:] + message_hex + checksum
        

        return bytes.fromhex(api_frame).decode('latin-1')
    