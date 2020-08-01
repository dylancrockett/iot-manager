# default lib imports
import threading
import json
import logging
from typing import Union
from queue import Queue
from uuid import uuid4

# external lib import
from gevent import socket

# module imports
from .ReservedBytes import GET_DATA, HEARTBEAT, END_CONNECTION
from .Packet import Packet


# Client class
class Client:
    # an exception raised when the client ends the connection, useful so the manager knows if a given client has
    # ended communications at any point
    class ConnectionEnd(Exception):
        pass

    # an exception raised when the client fails to get the client's info
    class InvalidInfo(Exception):
        pass

    def __init__(self, connection: socket, address: tuple, logging_level: int):
        # client logger
        self.logger = logging.getLogger("[Client](ID: UNKNOWN | IP: " + str(address[0]) + ")")
        self.logger_level = logging_level
        self.logger.setLevel(self.logger_level)

        # a lock preventing multiple threads from using the __connection at the same time
        self.connection_lock = threading.RLock()

        # socket object representing the connection between the client and the server
        self.__connection = connection

        # IP address of the client
        self.address = address

        # message buffer when irrelevant messages are received during a heartbeat
        self.buffer = Queue()

        # instance id of client (used to differentiate between multiple connections between the same client)
        self.instance_id = str(uuid4())

        # the uuid of the client
        self.__uuid = None

        # the type of client the client is
        self.__type = None

        # the bonus data which varies by client
        self.data = None

    # return the client's uuid
    def uuid(self):
        """
        Return the client's UUID.
        :return: str
        """
        return self.__uuid

    # return the client's type
    def type(self):
        """
        Return the client's type.
        :return: str
        """
        return self.__type

    # end the connection with the client
    def end(self, raise_exception: bool = False):
        """
        End the socket connection with the client.

        :param raise_exception: If a Client.ConnectionEnd exception should be raised when the connection is ended. True
                                will raise the exception False will end the connection quietly.

        :return: None
        """

        # logging output
        self.logger.warning("(end) Ending connection.")

        try:
            # tell the client the connection is ending
            self.send(Packet(END_CONNECTION))

        finally:
            # shutdown the socket connection
            self.__connection.shutdown(socket.SHUT_RDWR)

            # close the socket connection
            self.__connection.close()

            if raise_exception:
                # raise a connection end error
                raise self.ConnectionEnd

    # send data to the client
    def send(self, packet: Packet) -> bool:
        """
        Attempt to send a packet to the client.

        :param packet: Packet object containing the data to send to the client, should be a Packet in sending mode.

        :return: True if the packet was send, false if the packet could not be sent.
        """

        self.logger.debug("(send) Attempting to send a Packet.")

        # check if the packet object is a Packet in sending mode
        if not packet.is_sending():
            self.logger.warning("(send) Unable to send Packet, Packet object must be a sending Packet.")
            return False

        # init the lock
        with self.connection_lock:
            try:
                # send the string to to the client
                self.__connection.sendall(packet.bytes)

                self.logger.debug("(send) Packet sent successfully.")

                return True

            # in case of a socket error return None
            except socket.error:
                self.logger.debug("(send) Packet was unable to be sent.")
                return False

    # recv using the protocol of [2B - Message Size][Message] -> ignore rest of buffer
    def __smart_recv(self, timeout: int) -> Union[bytes, None]:
        """
        'Smartly' check the client socket's buffer.
        Read the first two bytes of the buffer (message header), this will give the size of the message.
        Read the # of bytes the message header specified and return those bytes.

        :param timeout: The time allowed for a response before the server assumes the client is dead and
                        ends the connection via the end() function.

        :return: Either None or a bytes object.
        """

        # init the lock
        with self.connection_lock:
            # if a timeout is specified then set the timeout
            if timeout is not None:
                self.__connection.settimeout(timeout)

            # read the first two bytes to get the size of the message
            message_size_bytes = self.__connection.recv(2)

            # if the buffer is empty return none
            if message_size_bytes is None:
                return None

            # if it has a value convert it into an integer
            message_size = int.from_bytes(message_size_bytes, 'big', signed=False)

            # log message header info
            self.logger.debug("(recv) Read message size header as: " + str(message_size_bytes) + " or int(" +
                              str(message_size) + ")")

            # recv up to the number of bytes we should recv
            message = self.__connection.recv(message_size)

            # log message body
            self.logger.debug("(recv) Read message body as: " + str(message))

            # check if the message len in bytes matches the length given, if it did not give a warning
            if message_size != len(message):
                # warn if the message length doesn't match the length given by the header
                self.logger.warning("(recv) Message length did not match the length specified in the message header.")

            return message

    # receives data from a client (optional timeout)
    def recv(self, timeout: int = 15) -> Union[Packet, None]:
        """
        Receives data from the client and returns either None if no new data has been received or a Packet
        object if the client has received some data.

        :param timeout: The time allowed for a response before the server assumes the client is dead and
                        ends the connection via the end() function.

        :return: None or a receiving Packet object.
        """

        # if there is a buffered message
        if self.buffer.qsize() > 0:
            return self.buffer.get()

        # blank response
        response = None

        # put the recv in a try catch to check for a timeout
        try:
            # read data from buffer
            response = self.__smart_recv(timeout)

        # in case of socket timeout
        except socket.timeout:
            return None

        # in case of another socket error
        except socket.error:
            return None

        finally:
            # if response is non return None
            if response is None:
                return None

            self.logger.debug("(recv) Returning received packet.")

            # return data as a packet object
            return Packet(response, sending=False)

    # gets the client's info (returns None if successful)
    def get_data(self, timeout: int = 15):
        """
        Get's the connected client's data when the client first connects to the manager. Will throw
        a Client.InvalidInfo exception if the client fails to provide a valid response or a Client.ConnectionEnd
        exception if the client fails to respond at all. (is called by the manager when the Client object is
        initialized but can be used to update the client if for some reason the Client's info changes in real
        time and must be updated on the server)

        :param timeout: The time allowed for a response before the server assumes the client is dead and
                        ends the connection via the end() function.

        :return: True if the connection is alive and False if the connection is now dead.
        """

        # logging output
        self.logger.info("(getinfo) Sending getinfo request.")

        # init the lock
        with self.connection_lock:
            # logging output
            self.logger.debug("(getinfo) Sending getinfo packet.")

            # ask the client for their data if the send fails then end the connection
            if not self.send(Packet(GET_DATA)):
                self.end(True)

            # logging output
            self.logger.debug("(getinfo) Receiving getinfo response")

            # await client response containing their info
            packet = self.recv(timeout=timeout)

            # if the response returned None because of an error end the connection
            if packet is None:
                self.end(True)

            # output the response
            self.logger.debug("(getinfo) Got data from client: '" + packet.bytes.decode() + "'.")

            # split the response using "##" as the delimiter
            response = packet.bytes.decode().split("##")

            # if the response is not 3 pieces of data raise an error
            if len(response) != 3:
                # logging output
                self.logger.error("(getinfo) Response invalid formatting, must be 3 values separated by delimiter '##'"
                                  + ". Formatted like: 'UUID##DEVICE_TYPE##JSON'.")

                raise self.InvalidInfo

            # get the clients UUID
            client_uuid = response[0]

            # update the client's logger info
            self.logger = logging.getLogger("[Client](ID: " + client_uuid + ")")
            self.logger.setLevel(self.logger_level)

            # check if the UUID is 36 char long to only allow proper UUIDs
            if len(client_uuid) != 36:
                # logging output
                self.logger.error("(getinfo) UUID invalid length, should be 36 characters. Data received: "
                                  + str(response) + ".")

                raise self.InvalidInfo

            # get the client's type
            client_type = response[1]

            # convert the data from a JSON string to a python dict
            try:
                # get the clients JSON data and convert it to a dict
                client_data = json.loads(response[2])
            except json.JSONDecodeError:
                # logging output
                self.logger.error("(getinfo) Failed to parse JSON.")

                # in case the JSON data provided is formatted incorrectly
                raise self.InvalidInfo

            # store the retrieved data
            self.__uuid = client_uuid
            self.__type = client_type
            self.data = client_data
            return None

    # check the heartbeat of the client returns None if client has a heartbeat
    def heartbeat(self, heartbeat_timeout: int) -> bool:
        """
        Checks the if the client socket is still alive by sending it a heartbeat packet, then waits for a response.
        If no response is received then the client is assumed to be dead and the socket is closed and the manager
        will remove the client and run the appropriate handler. (automatically done on a given interval by the manager
        but is available to users if they would like to manually initiate a heartbeat check)

        :param heartbeat_timeout: The time allowed for a response before the server assumes the client is dead and
                                  ends the connection via the end() function.

        :return: True if the connection is alive and False if the connection is now dead.
        """

        # logging output
        self.logger.info("(heartbeat) Sending heartbeat request.")

        # init the lock
        with self.connection_lock:
            # logging output
            self.logger.debug("(heartbeat) Sending heartbeat packet.")

            # send the heartbeat command if it fails end the connection
            if not self.send(Packet(HEARTBEAT)):
                self.end(True)

            # logging output
            self.logger.debug("(heartbeat) Receiving heartbeat response.")

            response = b''
            # loop until heartbeat or None is returned from recv
            while response is not None:
                # await a "beat" response or await timeout error
                response = self.recv(timeout=heartbeat_timeout)

                # if response is non exit the loop
                if response is None:
                    continue

                # log the bytes
                self.logger.debug("(heartbeat) Heartbeat response: " + str(response.bytes))

                # if the client's response is not beat then return a incorrect response
                if response.bytes == HEARTBEAT:
                    # logging output
                    self.logger.info("(heartbeat) Passed heartbeat check.")

                    # return the alive response
                    return True
                else:
                    self.logger.debug("(heartbeat) Response was not a heartbeat, adding response to buffer and " +
                                      "waiting again for heartbeat")

                    # put the received message into the message buffer
                    self.buffer.put(response)

            # if the recv fails then end the client connection and log a warning
            self.logger.warning("(heartbeat) Failed heartbeat check.")
            self.end(True)
            return False

    # client info as a dict
    def return_data(self) -> Union[dict, None]:
        """
        Returns the client's information as a JSON serializable dictionary. More reliable than dict() because it will
        return None if the client has not yet connected.

        :return: A dict object containing the client's data which is JSON serializable or None if the client's data
                 has not been retrieved yet.
        """

        # check if the data has not been returned
        if self.data is not None:
            return {
                "instance_id": self.instance_id,
                "uuid": self.__uuid,
                "type": self.__type,
                "data": self.data
            }
        else:
            return None

    # use dict(client) to get client info
    def __iter__(self):
        yield "instance_id", self.instance_id
        yield "uuid", self.__uuid
        yield "type", self.__type
        yield "data", self.data
