from abc import ABC, abstractmethod     # Enfore interface <-> subclass contract
from dataclasses import dataclass       # Dataclass - for measurements
from typing import Union



"""
CREDIT: Mihir. N
Encapsulates a single measurement parsed from a given CAN message.
A single CAN message can be parsed into multiple measurements.
"""
@dataclass
class Measurement:
    # the name of the value being measured
    name: str

    # category that the measurement falls under; often a single CAN ID maps to a single measurement category
    m_class: str

    # source CAN node of the message that contained the measurement
    source: str

    # value of the measurement
    value: Union[int, float, bool]


"""
Superclass Message (interface):
    Abstract representation of messages that come across the Radio Reciever.
    These messages must be UTF-8 encoded byte strings.
    Purpose is to provide a blueprint for the functionality each message type must have

    The a representation of a Message is based on a byte string
    from a UART message from the Radio Receiver (serial.readLine())
"""
class Message(ABC):
    """
    Constructor for the Message interface
    """
    @abstractmethod
    def __init__(self, message: str) -> None:
        pass

    """
    Extracts measurements from a Message based on a specified format

    Parameters:
        format_specifier: file path to a file containing a format specifier
    
    Returns:
        a list of Measurement objects containing fields formatted to the InfluxDB buckets 
    """
    @abstractmethod
    def extract_measurements(self, format_specifier=None) -> dict:
        pass

    """
    Returns:
        a dictionary containing the data fields of the Message
    """
    @abstractmethod
    def data(self) -> dict:
        pass

    """
    Returns:
        the type of the Message (e.g. CAN, GPS, IMU, etc.)
    """
    @abstractmethod
    def type(self) -> str:
        pass

