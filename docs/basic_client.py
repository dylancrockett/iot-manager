import socket
import uuid

# the IP of the machine running the IoTManager
# ("localhost" if both the server can client are running on the same machine)
host = "localhost"

# the port the IoTManager is using to listen for devices
port = 8595

# device info (used for handshaking with the server, make sure the type is valid)
info = {
    "uuid": uuid.uuid1(),
    "type": "test",
    "data": '{ "name": "Test Client" }'
}

# formatted info so it can be sent to the IoTManager
formatted_info = (info["uuid"] + "##" + info["type"] + "##" + info["data"])

# the socket object that will be used to connect and communicate with the server
connection_socket = socket.socket()

# connect the to the IoTManager
connection_socket.connect((host, port))
print("Connected to IoTManager! Starting main loop...")

# main client loop
while True:
    # wait to receive a command from the server
    command = connection_socket.recv(4096).decode()

    # some debug output so we can see what command was received
    if command != "":
        print("Command Received: " + command)

    # respond to the 'getinfo' command with this clients info
    if command == "\x01":
        print("Sending Device Data: '" + formatted_info + "'")
        connection_socket.sendall(formatted_info.encode())
    # respond to the 'heart' command with the 'beat' response
    elif command == "\x02":
        connection_socket.sendall("beat".encode())
    # respond to the hello client command
    elif command == "hello client":
        connection_socket.sendall("hello server".encode())

    # go back to waiting for another command from the server
