# default lib imports
import enum


# a list of reserved bytes which the Manager needs
class ReservedBytes(enum.Enum):
    # tells the device
    GET_DATA = b'\x01'
    HEARTBEAT = b'\x02'
    END_CONNECTION = b'\x03'
    END_MESSAGE = b'\xFF'
