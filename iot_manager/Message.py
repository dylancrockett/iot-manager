from .Client import Client
from .Packet import Packet


# message class
class Message:
    # message containing a client and packet
    def __init__(self, client: Client, packet: Packet):
        self.client = client
        self.packet = packet
