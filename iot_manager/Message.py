from .Client import Client
from .Packet import Packet


# message class
class Message:
    # message containing a client and packet
    def __init__(self, client: Client, packet: Packet):
        self.client = client
        self.packet = packet

    # quick decode function
    def decode(self):
        """
        Shorthand for Message.packet.bytes.decode().

        :return: str
        """
        return
