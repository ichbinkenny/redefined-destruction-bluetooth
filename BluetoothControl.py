import threading
import bluetooth
import subprocess
from os import system
import time
import multiprocessing
import queue

import sys
sys.path.append('../Movement/')
### Local module imports
from FrontWheels import stop as front_stop
from BackWheels import stop as back_stop

uuid = "94f39d29-7d6d-437d-973b-fba39e49d4ee"
front_wheel_proc = None
back_wheel_proc = None
web_client_proc = None
armor_refresh_rate_ms = 100
armor_state = ['0', '0', '0'] #armor is initially disconnected
update_queue = queue.Queue(-1)
connected = False

READY = 1
BUSY = 2
DEV_ADDED = 3
DEV_REMOVED = 4

def runUpdateQueue():
    print("Update queue starting")
    while True:
        if not update_queue.empty:
                stat : str = update_queue.get()
                web_client_proc.stdin.write(stat.encode('utf-8'))
                web_client_proc.stdin.flush() ## Ensure this makes it to the process!

def readServerUpdates(client, proc):
    while True:
        msg = proc.stdout.readline().decode('utf-8')
        print(msg)
        parseStatusUpdate(client, msg)

def parseStatusUpdate(client, msg):
    status_code = -1
    message = ""
    if 'id: ' in msg:
        client.sendall(bytes("YOUR_ID: " + msg[msg.index(':') + 1:], 'utf-8'))
        return
    if ':' in msg:
        status_code = int(msg[:msg.index(':')])
        message = msg[msg.index(':') + 2:]
    if status_code == READY:
        client.sendall(bytes("RDY: " + message, 'utf-8'))
    elif status_code == BUSY:
        client.sendall(bytes("BSY: " + message, 'utf-8'))
    elif status_code == DEV_ADDED:
        client.sendall(bytes("ADD: " + message, 'utf-8'))
    elif status_code == DEV_REMOVED:
        client.sendall(bytes("RMV: " + message, 'utf-8'))
    else:
        client.sendall(bytes(msg, 'utf-8'))

def sendArmorStatusToPhone(client_sock):
    print("Armor process spawned.")
    web_client_proc = subprocess.Popen(["/usr/bin/python3", "../Networking/client.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    serverUpdateThread = multiprocessing.Process(target=readServerUpdates, args=(client_sock, web_client_proc))
    serverUpdateThread.start()
    while True:
        armor_stat_proc = subprocess.Popen(["/usr/bin/python3", "../Movement/ArmorPanelControl.py"], stdout=subprocess.PIPE)
        armor_status = armor_stat_proc.stdout.readline().decode('utf-8')
        armor_conns = armor_status.split(':')
        client_sock.send("Armor Status: {}\n".format(armor_status.strip()))
        #Check if armor1 added
        if(armor_conns[0] != armor_state[0]):
            armor_state[0] = armor_conns[0]
            if(armor_conns[0]):
                #Armor panel added
                print("ARMOR TOGGLE")
                web_client_proc.stdin.write("3: armor1\n".encode('utf-8'))
                web_client_proc.stdin.flush()
                update_queue.put("3: armor1")
            else:
                update_queue.put("4: armor1")
        if(armor_conns[1] != armor_state[1]):
            armor_state[1] = armor_conns[1]
            if(armor_conns[1]):
                #Armor panel added
                web_client_proc.stdin.write("3: armor2\n".encode('utf-8'))
                web_client_proc.stdin.flush()
                update_queue.put("3: armor2")
            else:
                update_queue.put("4: armor2")
        if(armor_conns[2] != armor_state[2]):
            armor_state[2] = armor_conns[2]
            if(armor_conns[2]):
                #Armor panel added
                web_client_proc.stdin.write("3: armor3\n".encode('utf-8'))
                web_client_proc.stdin.flush()
                update_queue.put("3: armor3")
            else:
                update_queue.put("4: armor3")
        time.sleep(armor_refresh_rate_ms / 1000.0)

def doConnection(server_sock):
    client_sock, client_info = server_sock.accept()
    armor_process = multiprocessing.Process(target=sendArmorStatusToPhone, args=(client_sock,))
    armor_process.start()
    # Start process to communicate with webserver
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

    front_stop()
    back_stop()
    armor_process.terminate()
    print("Client disconnected... Awaiting new client connection.")
    client_sock.close()
    doConnection(server_sock) # prevent from closing on dc

def parseCommand(cmd_list):
    # For now, this accounts only for joystick position, and attack button status
    if len(cmd_list) == 2:
        # Standard command sent
        print("Standard command") 
        front_val = str(cmd_list[0]) + "\n"
        front_wheel_proc.stdin.write(front_val.encode('utf-8'))
        front_wheel_proc.stdin.flush()
        speed = str(cmd_list[1]) + "\n"
        back_wheel_proc.stdin.write(speed.encode('utf-8'))
        back_wheel_proc.stdin.flush()
    elif len(cmd_list) == 3:
        # Movement and attack sent.
        if cmd_list[0].lower() == "wifi":
            print("Wifi Request")
            # Generate the wpa_config for connection to begin
            with open('wpa_supplicant.conf', 'w') as wpa_conf:
                print("Generating WPA file...")
                try:
                    wpa_conf.write(giveWpaSuppStr(cmd_list[1].strip(), cmd_list[2].strip()))
                    print("Generation successful")
                    print("Replacing old wpa_supplicant")
                    system("mv wpa_supplicant.conf /etc/wpa_supplicant/")
                    wifi_proc = subprocess.Popen(["/bin/sh", "../Networking/wifi-restart.sh"], stdout=subprocess.PIPE)
                    reconn_status = wifi_proc.communicate() # This needs to lock.
                    if reconn_status != "SUCCESS!":
                        print("Failed to connect to network!")
                    else:
                        # Now we need to start the client connection to the webserver
                        global web_client_proc
                        if web_client_proc is not None:
                            #previous process was running
                            web_client_proc.terminate()
                        web_client_proc = subprocess.Popen(["/usr/bin/python3", "../Networking/client.py"], stdin=subprocess.PIPE)
                except:
                    print("Generation failed due to invalid characters...")
        else:
            print("Movement and attack request")

def giveWpaSuppStr(ssid, password):
    if(len(ssid) < 0 or len(password) < 8):
        raise("Invalid Characters or Password Length.")
    return "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\ncountry=US\n\nnetwork={{\n\tssid=\"{}\"\n\tpsk=\"{}\"\n}}\n".format(str(ssid), str(password))
            
def setup():
    print("Putting hci0 into its UP state...")
    system("hciconfig hci0 up")
    system("hciconfig hci0 piscan")
    print("Starting movement modules...")
    global front_wheel_proc
    front_wheel_proc = subprocess.Popen(["/usr/bin/python3", "../Movement/FrontWheels.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    global back_wheel_proc
    back_wheel_proc = subprocess.Popen(["/usr/bin/python3", "../Movement/BackWheels.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print("Creating bluetooth server socket.")
    server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    server_sock.bind(("", bluetooth.PORT_ANY))
    server_sock.listen(1)
    # We now need to setup the service that specifies the type of connection we support. Without this, the client wont connect!
    bluetooth.advertise_service(server_sock, "BattleBot Control", service_id=uuid,
                            service_classes=[uuid, bluetooth.SERIAL_PORT_CLASS],
                            profiles=[bluetooth.SERIAL_PORT_PROFILE],
                            # protocols=[bluetooth.OBEX_UUID]
                            )
    print("Waiting for a bluetooth client to connect...")
    doConnection(server_sock)
    # Something forced a return from doConnection, so cleanup the socket.
    server_sock.close()

if __name__ == "__main__":
    setup()
