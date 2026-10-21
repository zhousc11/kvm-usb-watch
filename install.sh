#!/bin/bash
set -e
LABEL=com.example.kvm-usb-watch
mkdir -p ~/bin ~/Library/LaunchAgents ~/Library/Logs
cp kvm-usb-watch.py ~/bin/ && chmod +x ~/bin/kvm-usb-watch.py
sed "s#__HOME__#$HOME#g" $LABEL.plist > ~/Library/LaunchAgents/$LABEL.plist
launchctl bootout gui/$(id -u)/$LABEL 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/$LABEL.plist
echo "installed; log: ~/Library/Logs/kvm-usb-watch.log"
