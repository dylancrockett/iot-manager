from .Client import Client
from .Message import Message


# defines a device type
class DeviceType:
    def __init__(self, device_type):
        self.type = device_type

    def on_connect(self, client: Client):
        pass

    def on_message(self, message: Message):
        pass

    def on_disconnect(self, client: Client):
        pass
