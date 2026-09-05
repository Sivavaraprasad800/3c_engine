#!/bin/bash
# setup_pi.sh — Run this on Raspberry Pi 5 to set up FRS camera relay
echo "======================================================"
echo "  FRS Camera Relay — Raspberry Pi Setup"
echo "======================================================"

# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip python3-opencv libopenblas-dev \
    libatlas-base-dev libjasper-dev libqtgui4 libqt4-test \
    git ffmpeg

# Install Python packages for camera relay (lightweight — no AI needed)
pip3 install requests opencv-python-headless numpy pymysql

echo ""
echo "======================================================"
echo "  Setup complete!"
echo ""
echo "  To run camera relay, edit SERVER_URL in camera_processor.py"
echo "  Then run: python3 camera_processor.py"
echo ""
echo "  Find your PC IP: run 'ipconfig' on your PC"
echo "  Set SERVER_URL = 'http://YOUR_PC_IP:8001'"
echo "======================================================"
