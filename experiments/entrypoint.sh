#!/bin/bash
set -e

# Start Xvfb
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99

# Start fluxbox + VNC
fluxbox & 
x11vnc -display :99 -localhost -nopw -forever -shared -rfbport 5900 &

# Run your script based on environment variable
if [ "$SCRIPT" = "iaai" ]; then
    exec python /app/iaai_login.py
else
    exec python /app/copart_login.py
fi

