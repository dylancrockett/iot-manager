# default lib imports
import enum

# reserved bytes for connection signals
GET_DATA = b'\x01'
HEARTBEAT = b'\x02'
END_CONNECTION = b'\x03'
