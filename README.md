# IoT Manager
### Overview
This project aims to create a lightweight and intuitive system for connecting
IoT devices to a central server for small IoT system implementations and hobbyists.

The framework focuses on providing easy to use communication standard for the
end user without the need for worrying about the underlying implementation.

The format of the framework is somewhat reminiscent of [Socket.IO](https://socket.io/) 
where handlers functions are defined and executed and run as events are triggered.


### Quickstart Guide (Server)
This is an example of a simple IoT Manager instance which accepts a "PingClient"
and will print every message the client sends out to console.

```python
from iot_manager import Manager, DeviceType, Client, Message, Packet

# create an instance of the IoTManager
manager = Manager(host="0.0.0.0")

# define our PingClient device
class PingClient(DeviceType):
    def on_connect(self, client: Client):
        print("New Ping Client Connected! ID: " + client.uuid())

    def on_message(self, message: Message):
        print("Message from Ping Client:" + message.decode())

    def on_disconnect(self, client: Client):
        print("New Ping Client Connected! ID: " + client.uuid())

# add the device to the manager
manager.add_device(PingClient("ping"))

# run the manager
manager.run()
```

If you would like to see the matching quickstart guide for an example
client go [here](https://github.com/dylancrockett/iot-manager-client).

