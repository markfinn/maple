#!/bin/bash

set -e

xset s noblank
xset s off
xset -dpms

unclutter -idle 0.5 -root &

sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' /home/mark/.config/chromium/Default/Preferences
sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' /home/mark/.config/chromium/Default/Preferences

/usr/bin/chromium-browser --noerrdialogs --disable-infobars --kiosk http://localhost:8080 &

while true; do
#   xdotool keydown ctrl+Tab; xdotool keyup ctrl+Tab;
#   sleep 10
   sleep 1
done
