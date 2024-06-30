from parser.parameters import*
import math

# Contains functions related to generating API Frames.

"""
    Returns a hex string of the most significant byte of an API Frame:
    
    Parameters:
        message_contents:
        hex string of the api frame exlcuding length and checksum
    
    Returns:
        hex string of the most significant byte

"""
def generate_msb(message_contents) -> str:

    total_bytes = bytes.fromhex(message_contents)
    msb_int = math.floor(len(total_bytes) /256)
    msb_byte = msb_int.to_bytes(1, 'big')
    msb = msb_byte.hex()

    return(msb)


"""
    Returns a hex string of the least significant byte of an API Frame:
    
    Parameters:
        message_contents:
        hex string of the api frame exlcuding length and checksum
    
    Returns:
        hex string of the least significant byte

"""
def generate_lsb(message_contents) -> str:
    total_bytes = bytes.fromhex(message_contents)
    lsb_int = len(total_bytes) % 256
    lsb_byte = lsb_int.to_bytes(1, 'big')
    lsb = lsb_byte.hex()
    return(lsb)



"""
    Returns a hex string of the checksum of an API Frame:
    
    Parameters:
        message_contents:
        hex string of the api frame exlcuding length and checksum
    
    Returns:
        hex string of the checksum

"""
def generate_checksum(message_contents) -> str:
    total_bytes = bytes.fromhex(message_contents)
    bytes_sum = int.from_bytes(total_bytes, 'big')
    checksum_int =  255 - (bytes_sum & 255)
    checksum_byte = checksum_int.to_bytes(1, 'big')
    checksum = checksum_byte.hex()

    return(checksum)

