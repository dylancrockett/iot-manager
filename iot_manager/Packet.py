from __future__ import annotations


# define a packet class
class Packet:
    def __init__(self, *args: bytes, sending: bool = True):
        # byte array
        self.bytes = bytearray()

        # marks if the packet is being used for sending data
        self.__sending = sending

        # go through all of the args and add them
        for arg in args:
            self.bytes.extend(arg)

        # the size of the message in bytes
        self.size = len(self.bytes)

        # if the packet is going to be used for sending add the message size header
        if sending:
            try:
                size = self.size.to_bytes(2, 'big')
            # check if this raises an overflow error if so echo it with some info
            except OverflowError:
                raise OverflowError(" The size of Packet.bytes cannot exceed the size of a 16 bit integer.")

            # if no problems are raised then add the size of the message to the front of self.bytes
            self.bytes[:0] = size

    # used for removing the front two size bytes
    def remove_header(self) -> None:
        # remove first two bytes
        del self.bytes[2:]

    # return the value of sending
    def is_sending(self):
        return self.__sending

    # overload the equality operator in python
    def __eq__(self, other: Packet) -> bool:
        if self.bytes == other.bytes:
            return True
        else:
            return False
