# default lib imports
import enum


# a list of reserved bytes which the Manager needs
class ReservedBytes(enum.Enum):
    # tells the device
    GET_DATA = bytearray(b'\x01')
    HEARTBEAT = bytearray('\x02')
    END_CONNECTION = bytearray('\x03')
    END_MESSAGE = bytearray('\xFF')
