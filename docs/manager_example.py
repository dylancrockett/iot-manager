from flask import Flask, render_template, request
import logging
import iotmanager

# init a basic logging config
logging.basicConfig()

# list of valid device types
types = ["test"]

# create the manager (faster heartbeat rate and debug level verbose for demonstration purposes)
device_manager = iotmanager.Manager(types, heartbeat_rate=30, logging_level=logging.DEBUG)

# flask app
app = Flask("iot_manager example")

# web page to test device communication
@app.route('/', methods=['GET', 'POST'])
def hello():
    # get the client data so we can serve the page
    client_data = device_manager.get_client_data()

    # command form submission handling
    if request.method == 'POST' and "command" in request.form:
        # send the command
        device_manager.send_string(request.form["uuid"], request.form["command"])

    # command_all form submission handling
    if request.method == 'POST' and "command_all" in request.form:
        # send the command to all devices
        device_manager.send_all_string(request.form["command_all"])

    # html template rendering
    return render_template("index.html", data=client_data)

# handler for messaging test client on connection
@device_manager.event
def on_connect_test(client):
    client.send_string("hello client")


# handler for client sending messages to the server
@device_manager.event
def on_message_test(client, message):
    print("Message Received from Client: ")
    print(message)


# run the flaks app
if __name__ == '__main__':
    app.run()
