# default lib imports
import socket
import threading
import json

# module imports
from .ReservedBytes import ReservedBytes
from .Packet import Packet


# Client class
class Client:
    # Data class
    class Data:
        def __init__(self, client_uuid: str, client_type: str, client_data: dict):
            # the uuid of the client
            self.uuid = client_uuid

            # the type of client the client is
            self.type = client_type

            # the bonus data which varies by client
            self.data = client_data

        # data class iter def
        def __iter__(self):
            yield ("uuid", self.uuid)
            yield ("type", self.type)
            yield ("data", self.data)

    # an exception raised when the client ends the connection, useful so the manager knows if a given client has
    # ended communications at any point
    class ConnectionEnd(Exception):
        pass

    # an exception raised when the client fails to get the client's info
    class InvalidInfo(Exception):
        pass

    def __init__(self, connection: socket, address: tuple):
        # a lock preventing multiple threads from using the __connection at the same time
        self.connection_lock = threading.RLock()

        # socket object representing the connection between the client and the server
        self.__connection = connection

        # IP address of the client
        self.address = address

        # client client data such as uuid, type, and misc data
        self.data = None

    # end the connection with the client
    def end(self, raise_exception: bool = False):
        try:
            # tell the client the connection is ending
            self.__connection.send(ReservedBytes.END_CONNECTION.value + ReservedBytes.END_MESSAGE.value)

        finally:
            # shutdown the socket connection
            self.__connection.shutdown(socket.SHUT_RDWR)

            # close the socket connection
            self.__connection.close()

            if raise_exception:
                # raise a connection end error
                raise self.ConnectionEnd

    # send data to the client
    def send(self, packet: Packet):
        # init the lock
        with self.connection_lock:
            try:
                # send the string to to the client
                return self.__connection.send(packet.bytes)

            # in case of a socket error return None
            except socket.error:
                return None

    # receives data from a client (optional timeout)
    def recv(self, timeout: int = 15):
        # init the lock
        with self.connection_lock:
            # if a timeout is specified then set the timeout
            if timeout is not None:
                self.__connection.settimeout(timeout)

            # blank response
            response = None

            # put the recv in a try catch to check for a timeout
            try:
                # read data from buffer
                response = self.__connection.recv(4096)

            # in case of socket timeout
            except socket.timeout:
                return None

            # in case of another socket error
            except socket.error:
                return None

            finally:
                # return data
                return response

    # gets the client's info (returns None if successful)
    def get_data(self, timeout: int = 15):
        # init the lock
        with self.connection_lock:
            # ask the client for their data if the send fails then end the connection
            if self.send(ReservedBytes.GET_DATA.value + ReservedBytes.END_MESSAGE.value) is None:
                self.end(True)

            # await client response containing their info
            response = self.recv(timeout=timeout)

            # if the response returned None because of an error end the connection
            if response is None:
                self.end(True)

            # split the response using "##" as the delimiter
            response = response.decode().split("##")

            # if the response is not 3 pieces of data raise an error
            if len(response) != 3:
                raise self.InvalidInfo

            # get the clients UUID
            client_uuid = response[0]

            # check if the UUID is 36 char long to only allow proper UUIDs
            if len(client_uuid) != 36:
                raise self.InvalidInfo

            # get the client's type
            client_type = response[1]

            # convert the data from a JSON string to a python dict
            try:
                # get the clients JSON data and convert it to a dict
                client_data = json.loads(response[2])
            except json.JSONDecodeError:
                # in case the JSON data provided is formatted incorrectly
                raise self.InvalidInfo

            # store the retrieved data
            self.data = self.Data(client_uuid, client_type, client_data)
            return None

    # check the heartbeat of the client returns None if client has a heartbeat
    def heartbeat(self, heartbeat_timeout: int = 15):
        # init the lock
        with self.connection_lock:
            # send the heartbeat command if it fails end the connection
            if self.send(ReservedBytes.HEARTBEAT.value + ReservedBytes.END_MESSAGE.value) is None:
                self.end(True)

            # await a "beat" response or await timeout error
            beat = self.recv(timeout=heartbeat_timeout).decode()

            # if the recv fails then end the client connection
            if beat is None:
                self.end(True)

            # if the client's response is not beat then return a incorrect response
            if beat == ReservedBytes.HEARTBEAT.value:
                # return the alive response
                return True
            else:
                # end the connection if the response is incorrect
                self.end(True)

    # client info as a dict
    def return_data(self):
        if self.data is not None:
            return dict(self.data)
        else:
            return None
