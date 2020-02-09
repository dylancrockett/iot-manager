# default lib imports
import logging
import socket
import threading
import ssl
import time
from concurrent.futures import ThreadPoolExecutor

# module imports
from .Client import Client


# Manager class
class Manager:
    def __init__(self, valid_types, ssl_context=None, host="127.0.0.1", connection_port=8595, max_workers=8,
                 heartbeat_rate=60, backlogged_connections=10, logging_id="[Manager]", logging_level=logging.INFO):

        # <> Instantiate Public Class Variables <>
        # the host is the computer running this program
        self.host = host

        # port that the manager will listen on for devices that want to connect
        self.port = connection_port

        # the delay between heartbeat messages
        self.heartbeat_rate = heartbeat_rate

        # <> Instantiate Private Class Variables <>
        # socket that will be used for accepting new clients
        self.__connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # a pool of connected clients
        self.__client_pool = []

        # ensure valid_types is a list
        if isinstance(valid_types, list):
            # valid types for the client to say it is
            self.__valid_types = valid_types

        # raise an error if invalid type
        else:
            raise TypeError("valid_types must be of type list")

        # logger object and setup
        if isinstance(logging_id, str):
            # logger object
            self.logger = logging.getLogger(logging_id)
        else:
            raise TypeError("logging_id must be of type str")

        if isinstance(logging_level, int):
            self.logger.setLevel(logging_level)
        else:
            raise TypeError("logging_level must resolve to an integer value")

        # <> Server Socket Setup <>
        # true if the socket is using SSL
        self.__ssl_enabled = False

        # attempt to bind the socket to the provided host and port
        try:
            # try binding
            self.__connection_socket.bind((self.host, self.port))

        # in the case a socket error is raised
        except socket.error:
            raise Exception("Unable to bind server socket to the provided host and port")

        # attempt to set the socket as a listening socket
        try:
            # if the backlogged_connections is not type int then raise an exception
            if not isinstance(backlogged_connections, int):
                raise TypeError("backlogged_connections must be type int")

            # set the socket as a listening socket
            self.__connection_socket.listen(backlogged_connections)

        # in the case a socket error is raised
        except socket.error:
            raise Exception("Unable to set the socket as ")

        # if a SSL context is provided then try and wrap the socket
        if ssl_context is not None and isinstance(ssl_context, ssl.SSLContext):
            # try to use the SSL context provided
            try:
                # create a SSLSocket using the provided ssl_context
                self.__connection_socket = \
                    ssl_context.wrap_socket(self.__connection_socket, server_side=True)

                # set __ssl_enabled as true
                self.__ssl_enabled = True

                # logging output
                self.logger.info("(Constructor) Provided SSL context used to wrap socket successfully.")

            # in the case of a SSLError
            except ssl.SSLError as error:
                # logging output
                self.logger.error("(Constructor)  Unable to create SSL socket using the provided SSL context due to the"
                                  + " following SSLError: " + str(error) + ". Defaulting to the depreciated"
                                  + " ssl.wrap_socket() method. Do not use this in a production application.")

                # use the default ssl.wrap_socket method
                self.__connection_socket = ssl.wrap_socket(self.__connection_socket)

                # set __ssl_enabled as true
                self.__ssl_enabled = True

        # if the ssl_context provided
        elif ssl_context is not None and not isinstance(ssl_context, ssl.SSLContext):
            # logging output
            self.logger.error("(Constructor) ssl_context is not the proper type, please provide a sll.SSLContext."
                              + " Defaulting to the depreciated ssl.wrap_socket() method. Do not use this in a"
                              + " production application.")

            # use the default ssl.wrap_socket method
            self.__connection_socket = ssl.wrap_socket(self.__connection_socket)

            # set __ssl_enabled as true
            self.__ssl_enabled = True

        # <> Device Specific Handler Dicts <>
        # handlers for on_connect events for specific devices
        self.__on_connect_handlers = {}

        # handlers for on_message events for specific devices
        self.__on_message_handlers = {}

        # <> Threading Setup and Initialization <>
        # a ThreadPoolExecutor which will be used when the manager needs to create temporary threads
        self.__executor = ThreadPoolExecutor(max_workers=max_workers)

        # a list used to store threads which last the lifetime of the program
        self.__thread_pool = []

        # start all of the main threads the class uses to run
        self.__thread_handler()
        return

    # run on a thread and is what connects new devices to the manager
    def __connection_listener(self):
        while True:
            try:
                # await a connection to the socket waiting for clients
                client_connection, client_address = self.__connection_socket.accept()

                # logging output
                self.logger.info("(Connection Listener) New Client Connection Established. Client IP Address: '"
                                 + str(client_address[0]) + "'")

                # hand over the client connection and address to a temporary thread which will get the data of the new
                # client
                self.__executor.submit(self.__register_client, client_connection, client_address)

            # catch any SSL errors and let the user know about them so they can fix them on the client end
            except ssl.SSLError as exception:
                self.logger.error("(Connection Listener) Error occurred in the connection_listener thread. Exception: "
                                  + str(exception))

    # takes a client socket and address and awaits the data which identifies the client's type
    def __register_client(self, connection, address):
        # try to create the client while checking for errors
        try:
            # create the client object (will also retrieve the client's info)
            client = Client(connection, address[0])

            # get the client's info
            client.get_data()

            # logging output
            self.logger.info("(Client Registrar) Got the data of client '" + client.data.uuid
                             + "', adding client to pool.")

        # in the case the client gave an invalid type
        except Client.InvalidInfo:
            # logging output
            self.logger.error("(Client Registrar) Failed to receive valid data from client client with IP '"
                              + str(address[0]) + "', ending connection.")

            # exit the function early
            return

        # check if a client is already connected which shares a UUID, assume that it is a invalid connection of the
        # client which is trying to reconnect and remove the old connection
        # go through all clients
        for check_client in reversed(self.__client_pool):
            # check and see if the current client's UUID matches that of another client
            if check_client.data.uuid == client.data.uuid:
                # logging output
                self.logger.debug("(Client Registrar) Client with UUID '" + client.data.uuid + "' has overridden a"
                                  + " established connection. This was likely due to reconnection before a heartbeat"
                                  + " check but could also be caused by two clients sharing a UUID.")

                # try to end the old client to end its connection if it still exists for some reason
                try:
                    # send the checked client the end message
                    check_client.end()
                finally:
                    # delete the client from the pool
                    del self.__client_pool[self.__client_pool.index(check_client)]

        # catch and exceptions within the general on_connect function
        # noinspection PyBroadException
        try:
            # run the on_connect function for the client
            self.on_connect(client)

        # in case of a exception when executing handler
        except Exception as error:
            self.logger.error(
                "(Message Handler) Exception caught when running the on_connect() handler. Exception: '"
                + str(error) + "'")

        # catch and exceptions within the device specific on_message function if any occur
        # noinspection PyBroadException
        try:
            # check if the user provided a device specific handler for this client's device type, if so execute it
            if client.data.type in self.__on_connect_handlers.keys():
                self.__on_connect_handlers[client.data.type](client)

        # in case of a exception when executing handler
        except Exception as error:
            self.logger.error(
                "(Message Handler) Exception caught when running the on_connect_" + client.data.type + "() handler."
                + "Exception: '" + str(error) + "'")

        # add the client to the pool
        self.__client_pool.append(client)

        # exit the thread
        return

    # heartbeat loop for checking if clients are still connected, run every x seconds based on the heartbeat_rate
    def __heartbeat_checker(self):
        while True:
            # wait the delay for a heartbeat to be sent
            time.sleep(self.heartbeat_rate)

            # logging output
            self.logger.info("(Heartbeat Checker) Starting client heartbeat check. Number of clients: '"
                             + str(len(self.__client_pool)) + "'.")

            # check the heartbeat of the connected clients
            for index in range(len(self.__client_pool) - 1, -1, -1):
                # logging output
                self.logger.debug("(Heartbeat Checker) Checking the heartbeat of client '"
                                  + self.__client_pool[index].data.uuid + "'.")

                # submit the heartbeat check to the executor
                self.__executor.submit(self.__heartbeat, index)

    # check the heartbeat of a client based on their given index
    def __heartbeat(self, client_index):

        # logging output
        self.logger.debug("(Heartbeat Checker for Client '" + self.__client_pool[client_index].data.uuid
                          + "') Initiating heartbeat check.")

        try:
            # check the heartbeat of the client
            self.__client_pool[client_index].heartbeat()

            # logging output
            self.logger.debug("(Heartbeat Checker for Client '"
                              + self.__client_pool[client_index].data.uuid + "') Client passed heartbeat check.")

            return
        except Client.ConnectionEnd:
            try:
                # end the client's connection
                self.__client_pool[client_index].end()
            finally:
                # logging output
                self.logger.error("(Heartbeat Checker for Client '" + self.__client_pool[client_index].data.uuid
                                  + "') Client failed heartbeat check, removing from pool.")

                # delete the client from the pool
                del self.__client_pool[client_index]

                return

    # this loop checks for client messages to the server
    def __message_listener(self):
        # loop for the lifetime of the program
        while True:
            # loop through each client
            for client in self.__client_pool:
                # check if the client has sent some data
                data = client.recv(0)

                # if the client has sent no data move onto the next client
                if data is None:
                    continue
                # if the client has sent some data then process it using the on_message function
                else:
                    # logging message
                    self.logger.debug("(Message Listener) Data received from client '" + client.data.uuid + "'."
                                      + " Sending data to appropriate handlers.")

                    # submit data to the __handle_message function
                    self.__executor.submit(self.__handle_message(client, data))

            # wait one second before trying to check messages again
            time.sleep(1)

    # function which is used to handle data sent from the client
    def __handle_message(self, client, data):
        # catch and exceptions within the general on_message function
        # noinspection PyBroadException
        try:
            # run the on_connect function for the client
            self.on_message(client, data)

        # in case of a exception when executing handler
        except Exception as error:
            self.logger.error("(Message Handler) Exception caught when running the on_message() handler. Exception: '"
                              + str(error) + "'")

        # catch and exceptions within the device specific on_message function if any occur
        # noinspection PyBroadException
        try:
            # check if the user provided a device specific handler for this client's device type, if so execute it
            if client.data.type in self.__on_message_handlers.keys():
                self.__on_message_handlers[client.data.type](client, data)

        # in case of a exception when executing handler
        except Exception as error:
            self.logger.error(
                "(Message Handler) Exception caught when running the on_message_" + client.data.type + "() handler."
                + "Exception: '" + str(error) + "'")

    # sends data to all clients
    def send_all(self, data):
        # for each client in the pool
        for client in self.__client_pool:
            # send the client the data
            self.__executor.submit(client.send, data)

    # sends data to all clients of a specified device_type
    def send_type(self, device_type, data):
        # for each client in the pool
        for client in self.__client_pool:
            # check if the client matches the provided type
            if client.data.type == device_type:
                # send the client the data
                self.__executor.submit(client.send, data)

    # sends data to a client given a uuid
    def send(self, unique_id, data):
        # for each client in the pool
        for client in self.__client_pool:
            # check if the client matches the provided uuid
            if client.data.uuid == unique_id:
                # send the client the data
                self.__executor.submit(client.send, data)
                return

    # sends a string to all clients
    def send_all_string(self, string):
        # for each client in the pool
        for client in self.__client_pool:
            # send the client the string
            self.__executor.submit(client.send_string, string)

    # sends a string to all clients of a specified device_type
    def send_type_string(self, device_type, string):
        # for each client in the pool
        for client in self.__client_pool:
            # check if the client matches the provided type
            if client.data.type == device_type:
                # send the client the string
                self.__executor.submit(client.send_string, string)

    # sends a string to a client given a uuid
    def send_string(self, unique_id, string):
        # for each client in the pool
        for client in self.__client_pool:
            # check if the client matches the provided uuid
            if client.data.uuid == unique_id:
                # send the client the string
                self.__executor.submit(client.send_string, string)
                return

    # returns an list of dictionaries storing the connected clients' information
    def get_client_data(self):
        # data list
        info = []

        # loop through the clients and add their info to the list
        for client in self.__client_pool:
            # add the info for the given client
            info.append(client.return_data())

        # return the list of client data
        return info

    # event manager decorator function
    def event(self, coroutine):
        # handle general on_connect and on_message handlers
        if coroutine.__name__ == "on_connect" or coroutine.__name__ == "on_message":
            # logging output
            self.logger.info("(Event Handler) '" + coroutine.__name__ + "' handler was added successfully.")

            # replaces the existing coroutine with the provided one
            setattr(self, coroutine.__name__, coroutine)
            return True

        # handle device specific on_connect handlers
        elif "on_connect_" in coroutine.__name__:
            # get the type of the device this handler is for
            device_type = coroutine.__name__.replace("on_connect_", "")

            # ensure the type of device the handler matches has been registered
            if device_type in self.__valid_types:
                # logging output
                self.logger.info("(Event Handler) '" + coroutine.__name__ + "' handler was added successfully.")

                # add the device specific handler to the list of on_message handlers
                self.__on_connect_handlers.update({device_type: coroutine})
                return True

            # in case the type is not a valid device type
            self.logger.error("(Event Handler) '" + coroutine.__name__ + "' is not a valid event handler and will"
                              + " be ignored. Please refer to the event handler documentation.")
            return False

        # handle device specific on_message handlers
        elif "on_message_" in coroutine.__name__:
            # get the type of the device this handler is for
            device_type = coroutine.__name__.replace("on_message_", "")

            # ensure the type of device the handler matches has been registered
            if device_type in self.__valid_types:
                # logging output
                self.logger.info("(Event Handler) '" + coroutine.__name__ + "' handler was added successfully.")

                # add the device specific handler to the list of on_message handlers
                self.__on_message_handlers.update({device_type: coroutine})
                return True

            # in case the type is not a valid device type
            self.logger.error("(Event Handler) '" + coroutine.__name__ + "' is not a valid event handler and will"
                              + " be ignored. Please refer to the event handler documentation.")
            return False

        # in case of an invalid event handler provided
        else:
            self.logger.error("(Event Handler) '" + coroutine.__name__ + "' is not a valid event handler and will"
                              + " be ignored. Please refer to the event handler documentation.")
            return False

    # on connection function - run on client connection
    def on_connect(self, client):
        return

    # on message function - runs when a client sends a message to the server
    def on_message(self, client, message):
        return

    # runs all the handlers
    def __thread_handler(self):
        # logging output
        self.logger.info("(Thread Handler) Adding threads to the thread pool.")

        # add the core threads to the pool
        self.__thread_pool.append(threading.Thread(target=self.__connection_listener, daemon=False))
        self.__thread_pool.append(threading.Thread(target=self.__heartbeat_checker, daemon=False))
        self.__thread_pool.append(threading.Thread(target=self.__message_listener, daemon=False))

        # logging output
        self.logger.info("(Thread Handler) Starting threads.")

        # start the threads in the pool
        for thread in self.__thread_pool:
            thread.start()

        # logging output
        self.logger.info("(Thread Handler) All threads started.")
        return
