import bluetooth
import subprocess

uuid = "94f39d29-7d6d-437d-973b-fba39e49d4ee"
front_wheel_proc = None
back_wheel_proc = None

def doConnection(server_sock):
    client_sock, client_info = server_sock.accept()
    print("Got connection from", client_info)

    connected = True

    # We can fetch data now!
    while connected:
        try:
            data = client_sock.recv(1024).decode('utf-8')
            if not data: #no data received
                break
            print("Received:", data)
            parseCommand(data.split(' '))
        except:
            connected = False # client disconnected!

    print("Client disconnected... Awaiting new client connection.")
    client_sock.close()
    doConnection(server_sock) # prevent from closing on dc

def parseCommand(cmd_list):
    # For now, this accounts only for joystick position, and attack button status
    if len(cmd_list) == 2:
        # Only movements were sent.
        print("Movement request")
        front_val = str(cmd_list[0]) + "\n"
        front_wheel_proc.stdin.write(front_val.encode('utf-8'))
        front_wheel_proc.stdin.flush()
    elif len(cmd_list) == 3:
        # Movement and attack sent.
        if cmd_list[0].lower() == "wifi":
            print("Wifi Request")
        else:
            print("Movement and attack request")

def setup():
    print("Starting movement modules...")
    global front_wheel_proc
    front_wheel_proc = subprocess.Popen(["/usr/bin/python3", "../Movement/FrontWheels.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print("Creating server socket.")
    server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    server_sock.bind(("", bluetooth.PORT_ANY))
    server_sock.listen(1)
    # We now need to setup the service that specifies the type of connection we support. Without this, the client wont connect!
    bluetooth.advertise_service(server_sock, "BattleBot Control", service_id=uuid,
                            service_classes=[uuid, bluetooth.SERIAL_PORT_CLASS],
                            profiles=[bluetooth.SERIAL_PORT_PROFILE],
                            # protocols=[bluetooth.OBEX_UUID]
                            )
    print("Waiting for a client to connect...")
    doConnection(server_sock)
    # Something forced a return from doConnection, so cleanup the socket.
    server_sock.close()

if __name__ == "__main__":
    setup()
