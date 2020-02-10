from .ReservedBytes import ReservedBytes


# define a packet class
class Packet:
    def __init__(self, *args: bytearray, sending: bool = True):
        # byte array
        self.bytes = bytearray()

        # go through all of the args and add them
        for arg in args:
            self.bytes.extend(arg)

        # if the packet is going to be used for sending add the end message byte
        if sending:
            # add the end message char if it is a sending packet
            self.bytes.extend(ReservedBytes.END_MESSAGE.value)
