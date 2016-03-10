#!/bin/bash

BITRATE=$1

if [ -z "$BITRATE" ]; then
	BITRATE=500000
fi

sudo ip link set can0 down
sudo ip link set can0 up type can bitrate $BITRATE

echo "I executed: ip link set can0 up type can bitrate $BITRATE"

candump -c can0,0:0,#FFFFFFFF
