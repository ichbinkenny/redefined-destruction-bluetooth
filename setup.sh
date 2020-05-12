#!/bin/sh

echo "Attempting to start bluetooth device..."

bluetoothctl
agent on
default-agent
exit