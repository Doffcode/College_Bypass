#!/bin/bash

# Path to the spoofdpi executable
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPOOFDPI_BIN="$DIR/spoofdpi"

# Check if proxy is currently enabled
MODE=$(gsettings get org.gnome.system.proxy mode)

if [ "$MODE" = "'manual'" ]; then
    echo "Turning OFF the restriction bypass..."
    
    # Disable system proxy
    gsettings set org.gnome.system.proxy mode 'none'
    
    # Kill the background SpoofDPI process
    killall spoofdpi 2>/dev/null
    
    echo "✅ Bypass is OFF. Regular internet settings restored."
else
    echo "Turning ON the restriction bypass..."
    
    # Start SpoofDPI in the background
    nohup "$SPOOFDPI_BIN" --listen-addr 127.0.0.1:8080 > /dev/null 2>&1 &
    
    # Wait a second for it to start
    sleep 1
    
    # Enable system proxy to route traffic through SpoofDPI
    gsettings set org.gnome.system.proxy mode 'manual'
    gsettings set org.gnome.system.proxy.http host '127.0.0.1'
    gsettings set org.gnome.system.proxy.http port 8080
    gsettings set org.gnome.system.proxy.https host '127.0.0.1'
    gsettings set org.gnome.system.proxy.https port 8080
    gsettings set org.gnome.system.proxy ignore-hosts "['localhost', '127.0.0.0/8', '::1']"
    
    echo "✅ Bypass is ON! Your browser will now bypass the firewall DPI."
fi
