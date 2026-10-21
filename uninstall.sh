#!/bin/bash
LABEL=com.example.kvm-usb-watch
launchctl bootout gui/$(id -u)/$LABEL 2>/dev/null || true
rm -f ~/Library/LaunchAgents/$LABEL.plist ~/bin/kvm-usb-watch.py
echo "uninstalled"
