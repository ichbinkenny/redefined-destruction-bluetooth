#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <bluetooth/bluetooth.h>
#include <bluetooth/rfcomm.h>

int main(){
    printf("Initial running!\n");
    //Create bluetooth socket
    printf("Creating bluetooth socket!\n");
    int sock = socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM);
    if(sock == -1){
        printf("Failure! ERR: %s\n", errno);
        return -1;
    }
    printf("Socket created successfully! %d\n", sock);
    struct sockaddr_rc local = {0};
    //cleanup sockets
    close(sock);
    return 0;
}