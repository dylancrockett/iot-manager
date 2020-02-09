# default lib imports
import socket
import threading
import json

# module imports
from .ReservedBytes import ReservedBytes


# Client class
class Client:
    class Data:
        def __init__(self, client_uuid, client_type, client_data):
            # the uuid of the client
            self.uuid = client_uuid

            # the type of client the client is
            self.type = client_type

            # the bonus data which varies by client
            self.data = client_data

        def get(self):
            return {
                "uuid": self.uuid,
                "type": self.type,
                "data": self.data
            }

    # an exception raised when the client ends the connection, useful so the manager knows if a given client has
    # ended communications at any point
    class ConnectionEnd(Exception):
        pass

    # an exception raised when the client fails to get the client's info
    class InvalidInfo(Exception):
        pass

    def __init__(self, connection, address):
        # a lock preventing multiple threads from using the __connection at the same time
        self.connection_lock = threading.RLock()

        # socket object representing the connection between the client and the server
        self.__connection = connection

        # IP address of the client
        self.address = address

        # client client data such as uuid, type, and misc data
        self.data = None

    # end the connection with the client
    def end(self, raise_exception=False):
        try:
            # tell the client the connection is ending
            self.__connection.send(bytearray(ReservedBytes.END_CONNECTION.value)
                                   + bytearray(ReservedBytes.END_MESSAGE.value))

        finally:
            # shutdown the socket connection
            self.__connection.shutdown(socket.SHUT_RDWR)

            # close the socket connection
            self.__connection.close()

            if raise_exception:
                # raise a connection end error
                raise self.ConnectionEnd

    # send data to the client
    def send(self, data):
        # init the lock
        with self.connection_lock:
            try:
                # send the string to to the client
                return self.__connection.send(data)

            # in case of a socket error return None
            except socket.error:
                return None

    # receives data from a client (optional timeout)
    def recv(self, timeout=15):
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

    # send for strings
    def send_string(self, string):
        # encode and send the string
        return self.send(string.encode())

    # recv for strings
    def recv_string(self, timeout=15):
        # recv the data
        data = self.recv(timeout)

        # if the data is None return None
        if data is None:
            return None

        # if the data is not none return the data decoded as a string
        else:
            return data.decode()

    # gets the client's info (returns None if successful)
    def get_data(self, timeout=15):
        # init the lock
        with self.connection_lock:
            # ask the client for their data if the send fails then end the connection
            if self.send(bytearray(ReservedBytes.GET_DATA.value) + bytearray(ReservedBytes.END_MESSAGE.value)) is None:
                self.end(True)

            # await client response containing their info
            response = self.recv_string(timeout=timeout)

            # if the response returned None because of an error end the connection
            if response is None:
                self.end(True)

            # split the response using "##" as the delimiter
            response = response.split("##")

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
    def heartbeat(self, heartbeat_timeout=15):
        # init the lock
        with self.connection_lock:
            # send the heartbeat command if it fails end the connection
            if self.send(bytearray(ReservedBytes.HEARTBEAT.value) + bytearray(ReservedBytes.END_MESSAGE.value)) is None:
                self.end(True)

            # await a "beat" response or await timeout error
            beat = self.recv(timeout=heartbeat_timeout).decode()

            # if the recv fails then end the client connection
            if beat is None:
                self.end(True)

            # if the client's response is not beat then return a incorrect response
            if beat == "beat":
                # return the alive response
                return True
            else:
                # end the connection if the response is incorrect
                self.end(True)

    # client info as a dict
    def return_data(self):
        if self.data is not None:
            return self.data.get()
        else:
            return None
