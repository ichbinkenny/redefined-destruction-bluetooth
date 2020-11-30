import threading
import bluetooth
import subprocess
from os import system
import time
import multiprocessing
import queue

import sys
sys.path.append('/home/pi/redefined-destruction/Movement/')
### Local module imports
from FrontWheels import stop as front_stop
from BackWheels import stop as back_stop
from Weapon import reset as weapon_reset

uuid = "94f39d29-7d6d-437d-973b-fba39e49d4ee"
front_wheel_proc = None
back_wheel_proc = None
web_client_proc = None
weapon_proc = None
armor_refresh_rate_ms = 100
update_queue = queue.Queue(-1)
connected = False
should_update_armor = False
bot_id = -1

READY = 1
BUSY = 2
DEV_ADDED = 3
DEV_REMOVED = 4
ENTER_COMBAT = 5
EXIT_COMBAT = 6

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
        if 'id:' in msg:
            global bot_id
            bot_id = 99
        print(msg)
        parseStatusUpdate(client, msg)

def parseStatusUpdate(client, msg):
    status_code = -1
    message = ""
    if 'id: ' in msg:
        client.sendall(bytes("YOUR_ID: " + msg[msg.index(':') + 1:], 'utf-8'))
        global bot_id
        bot_id = int(msg[msg.index(': ') + 1:].strip())
        return
    if 'UNKNOWN STATUS' in msg:
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

def sendArmorStatusToPhone(client_sock, web_client_proc, weapon_proc):
    print("Armor process spawned.")
    serverUpdateThread = multiprocessing.Process(target=readServerUpdates, args=(client_sock, web_client_proc))
    serverUpdateThread.start()
    armor_state = [False, False, False] #armor initially disconnected.
    global connected
    while connected:
        armor_stat_proc = subprocess.Popen(["/usr/bin/python3", "/home/pi/redefined-destruction/Movement/ArmorPanelControl.py"], stdout=subprocess.PIPE)
        armor_status = armor_stat_proc.stdout.readline().decode('utf-8')
        armor_conns = list(map(lambda v: v.strip() == '1',armor_status.split(':')))
        client_sock.send("ArmorStatus: {}\n".format(armor_status.strip()))
        #Check if armor1 added
        if(armor_conns[0] != armor_state[0]):
            armor_state[0] = armor_conns[0]
            if armor_state[0] == True:
                #Armor panel added
                web_client_proc.stdin.write("3: armor1\n".encode('utf-8'))
                web_client_proc.stdin.flush()
                update_queue.put("3: armor1")
            elif armor_state[0] == False:
                web_client_proc.stdin.write("4: armor1\n".encode('utf-8'))
                web_client_proc.stdin.flush()
                update_queue.put("4: armor1")
        if(armor_conns[1] != armor_state[1]):
            armor_state[1] = armor_conns[1]
            if armor_state[1] == True:
                #Armor panel added
                web_client_proc.stdin.write("3: armor2\n".encode('utf-8'))
                web_client_proc.stdin.flush()
                update_queue.put("3: armor2")
            elif armor_state[1] == False:
                web_client_proc.stdin.write("4: armor2\n".encode('utf-8'))
                web_client_proc.stdin.flush()
                update_queue.put("4: armor2")
            else:
                print("UNKNOWN ARMOR STATE: %s" % armor_conns[1])
        if(armor_conns[2] != armor_state[2]):
            armor_state[2] = armor_conns[2]
            print("ARMOR3 STATE: %s" % armor_state[2])
            if armor_state[2] == True:
                #Armor panel added
                web_client_proc.stdin.write("3: armor3\n".encode('utf-8'))
                web_client_proc.stdin.flush()
                update_queue.put("3: armor3")
            elif armor_state[2] == False:
                web_client_proc.stdin.write("4: armor3\n".encode('utf-8'))
                web_client_proc.stdin.flush()
                update_queue.put("4: armor3")
            else:
                print("UNKNOWN ARMOR STATE: %s" % armor_state[2])
        time.sleep(armor_refresh_rate_ms / 1000.0)

def doConnection(server_sock, web_client_proc, weapon_proc):
    client_sock, client_info = server_sock.accept()
    armor_process = multiprocessing.Process(target=sendArmorStatusToPhone, args=(client_sock,web_client_proc,weapon_proc))
    # Start process to communicate with webserver
    global connected
    connected = True
    armor_process.start()
    # We can fetch data now!
    while connected:
        try:
            data = client_sock.recv(1024).decode('utf-8')
            if not data: #no data received
                break
            parseCommand(client_sock, data.split(' '), web_client_proc, weapon_proc)
        except Exception as e:
            print("Exception: %s" % e)
            connected = False # client disconnected!

    front_stop()
    back_stop()
    weapon_reset()
    #armor_process.terminate()
    print("Client disconnected... Awaiting new client connection.")
    client_sock.close()
    doConnection(server_sock, web_client_proc, weapon_proc) # prevent from closing on dc

def parseCommand(client, cmd_list, web_client_proc=None, weapon_proc=None):
    if len(cmd_list) == 1:
        if 'EnteringCombat' in cmd_list[0].strip():
            print("SENDING COMBAT CMD ENTER")
            web_client_proc.stdin.write(bytes(str(ENTER_COMBAT) + ": " + str(bot_id) + '\n', 'utf-8'))
            web_client_proc.stdin.flush()
        elif "ExitingCombat" in cmd_list[0]:
            web_client_proc.stdin.write(bytes(str(EXIT_COMBAT) + ": " + str(bot_id) + '\n', 'utf-8'))
            web_client_proc.stdin.flush()
        else:
            print("Info CMD: " + cmd_list[0].strip())
            client.send("{}\n".format(bot_id))
    elif len(cmd_list) == 2:
        # Standard command sent
        if(cmd_list[0] == 'weapon:'):
            weapon = cmd_list[1]
            web_client_proc.stdin.write(bytes('3: ' + cmd_list[1] + '\n', 'utf-8'))
            web_client_proc.stdin.flush()
        elif cmd_list[0] == 'primary:':
            weapon_proc.stdin.write(bytes(cmd_list[1] + '\n', 'utf-8'))
            weapon_proc.stdin.flush()
        elif cmd_list[0] == 'secondary:':
            print("Attacking with secondary weapon")
        else:
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
                    wifi_proc = subprocess.Popen(["/bin/sh", "/home/pi/redefined-destruction/Networking/wifi-restart.sh"], stdout=subprocess.PIPE)
                    reconn_status = wifi_proc.communicate() # This needs to lock.
                    if reconn_status != "SUCCESS!":
                        print("Failed to connect to network!")
                    else:
                        # Now we need to start the client connection to the webserver
                        if web_client_proc is not None:
                            #previous process was running
                            web_client_proc.terminate()
                        web_client_proc = subprocess.Popen(["/usr/bin/python3", "/home/pi/redefined-destruction/Networking/client.py"], stdin=subprocess.PIPE)
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
    front_wheel_proc = subprocess.Popen(["/usr/bin/python3", "/home/pi/redefined-destruction/Movement/FrontWheels.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    global back_wheel_proc
    back_wheel_proc = subprocess.Popen(["/usr/bin/python3", "/home/pi/redefined-destruction/Movement/BackWheels.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    global weapon_proc
    weapon_proc = subprocess.Popen(["/usr/bin/python3", "/home/pi/redefined-destruction/Movement/Weapon.py"], stdin=subprocess.PIPE)
    print("Creating bluetooth server socket.")
    web_client_proc = subprocess.Popen(["/usr/bin/python3", "/home/pi/redefined-destruction/Networking/client.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
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
    doConnection(server_sock, web_client_proc, weapon_proc)
    # Something forced a return from doConnection, so cleanup the socket.
    server_sock.close()
    web_client_proc.terminate()

if __name__ == "__main__":
    setup()
