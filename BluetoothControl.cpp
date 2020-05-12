#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <bluetooth/bluetooth.h>
#include <bluetooth/rfcomm.h>
#include <bluetooth/hci.h>
#include <bluetooth/hci_lib.h>

void setScanMode(int sock, int mode, hci_dev_req* reqs){
    if(ioctl(sock, mode, reqs) < 0){
        fprintf(stderr, "Could not set scan mode... Error: %d\n", errno);
    }
    else{
        printf("Discovery enabled! You should see this device now!\n");
    }
}

int main(){
    printf("Starting...\n");
    int sock = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI);
    printf("Socket created successfully! %d\n", sock);
    //setup discovery mode
    struct hci_dev_req requirements;
    requirements.dev_id = 0;
    requirements.dev_opt = SCAN_DISABLED;
    requirements.dev_opt = SCAN_PAGE | SCAN_INQUIRY;
    //Enable the pi to be discoverable 
    setScanMode(sock, HCISETSCAN, &requirements);
    //cleanup sockets
    close(sock);
    return 0;
}