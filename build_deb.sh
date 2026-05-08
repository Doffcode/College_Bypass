#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="college-bypass"
PKG_VERSION="1.1"
PKG_ARCH="amd64"
PKG_DIR="$SCRIPT_DIR/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}"
OUT_DEB="$SCRIPT_DIR/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"

BOLD='\033[1m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "  ${BLUE}[*]${NC} $*"; }
success() { echo -e "  ${GREEN}[✓]${NC} $*"; }

echo ""
echo -e "  ${BOLD}Building college-bypass.deb v${PKG_VERSION}${NC}"
echo "  ================================="
echo ""

command -v dpkg-deb &>/dev/null || { echo "dpkg-deb not found. Install: sudo apt install dpkg"; exit 1; }
[[ -x "$SCRIPT_DIR/spoofdpi" ]] || { echo "spoofdpi binary not found in $SCRIPT_DIR"; exit 1; }
[[ -f "$SCRIPT_DIR/college_bypass_ui.py" ]] || { echo "college_bypass_ui.py not found in $SCRIPT_DIR"; exit 1; }

info "Creating package structure..."
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/local/bin"
mkdir -p "$PKG_DIR/usr/lib/college-bypass"
mkdir -p "$PKG_DIR/usr/share/applications"

info "Copying spoofdpi binary..."
cp "$SCRIPT_DIR/spoofdpi" "$PKG_DIR/usr/lib/college-bypass/spoofdpi"
chmod 755 "$PKG_DIR/usr/lib/college-bypass/spoofdpi"

info "Copying GUI script..."
cp "$SCRIPT_DIR/college_bypass_ui.py" "$PKG_DIR/usr/lib/college-bypass/college_bypass_ui.py"
chmod 644 "$PKG_DIR/usr/lib/college-bypass/college_bypass_ui.py"

info "Writing DEBIAN/control..."
cat > "$PKG_DIR/DEBIAN/control" << 'EOF'
Package: college-bypass
Version: 1.1
Architecture: amd64
Maintainer: college-bypass
Depends: curl, libnotify-bin, python3-gi, gir1.2-gtk-3.0
Description: College DPI firewall bypass with GUI (SpoofDPI + Cloudflare WARP)
 One-click toggle that bypasses Deep Packet Inspection on college networks.
 Uses SpoofDPI for SNI fragmentation and Cloudflare WARP for encryption.
 Run `college-bypass-gui` or click the app icon to launch the GTK UI.
 Run `college-bypass` for CLI usage.
EOF

info "Writing DEBIAN/postinst..."
cat > "$PKG_DIR/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
set -e
case "$1" in configure) ;; *) exit 0 ;; esac

if ! command -v warp-cli &>/dev/null; then
    echo "  [*] Installing Cloudflare WARP..."
    ARCH=$(dpkg --print-architecture)
    CODENAME=$(lsb_release -cs 2>/dev/null || echo "jammy")
    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg \
        | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
    echo "deb [arch=$ARCH signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $CODENAME main" \
        > /etc/apt/sources.list.d/cloudflare-client.list
    apt-get update -qq
    apt-get install -y cloudflare-warp
    echo "  [✓] Cloudflare WARP installed."
    echo ""
    echo "  Next: run  college-bypass-gui  (or click the app icon)"
    echo "        First run will register WARP and turn the bypass ON."
else
    echo "  [✓] Cloudflare WARP already installed."
fi
POSTINST
chmod 755 "$PKG_DIR/DEBIAN/postinst"

info "Writing DEBIAN/prerm..."
cat > "$PKG_DIR/DEBIAN/prerm" << 'PRERM'
#!/bin/bash
set -e
case "$1" in remove|purge)
    pkill -x spoofdpi 2>/dev/null || true
    rm -f /tmp/spoofdpi.pid
    gsettings set org.gnome.system.proxy mode 'none' 2>/dev/null || true
    (command -v kwriteconfig6 &>/dev/null && kwriteconfig6 --file kioslaverc --group "Proxy Settings" --key ProxyType "0") 2>/dev/null || \
    (command -v kwriteconfig5 &>/dev/null && kwriteconfig5 --file kioslaverc --group "Proxy Settings" --key ProxyType "0") 2>/dev/null || true
;; esac
PRERM
chmod 755 "$PKG_DIR/DEBIAN/prerm"

info "Writing .desktop entry..."
cat > "$PKG_DIR/usr/share/applications/college-bypass.desktop" << 'EOF'
[Desktop Entry]
Name=College Bypass
Comment=Toggle DPI firewall bypass ON/OFF
Exec=college-bypass-gui
Icon=network-vpn
Terminal=false
Type=Application
Categories=Network;Security;
Keywords=vpn;bypass;dpi;firewall;warp;
EOF

info "Writing CLI wrapper (college-bypass)..."
cat > "$PKG_DIR/usr/local/bin/college-bypass" << 'SCRIPT'
#!/bin/bash
set -euo pipefail

SPOOFDPI_BIN="/usr/lib/college-bypass/spoofdpi"
PROXY_HOST="127.0.0.1"
PROXY_PORT=8080
PID_FILE="/tmp/spoofdpi.pid"

_in_terminal() { [[ -t 1 ]]; }

info()    { _in_terminal && echo -e "  \033[0;34m[*]\033[0m $*" || true; }
success() {
    local msg="$*"
    _in_terminal && echo -e "  \033[0;32m[✓]\033[0m $msg" || true
    notify-send -i network-vpn -t 4000 "College Bypass" "$msg" 2>/dev/null || true
}
warn() {
    local msg="$*"
    _in_terminal && echo -e "  \033[1;33m[!]\033[0m $msg" || true
    notify-send -i dialog-warning -t 5000 "College Bypass" "$msg" 2>/dev/null || true
}
error() {
    local msg="$*"
    _in_terminal && echo -e "  \033[0;31m[✗]\033[0m $msg" >&2 || true
    notify-send -i dialog-error -t 8000 "College Bypass — Error" "$msg" 2>/dev/null || true
    exit 1
}

detect_de() {
    local de="${XDG_CURRENT_DESKTOP:-}"
    if [[ -n "${KDE_FULL_SESSION:-}" ]] || [[ "$de" == *KDE* ]] || [[ "$de" == *plasma* ]]; then
        echo "kde"
    elif [[ -n "${GNOME_DESKTOP_SESSION_ID:-}" ]] || [[ "$de" == *GNOME* ]] \
        || [[ "$de" == *Unity* ]] || [[ "$de" == *Cinnamon* ]]; then
        echo "gnome"
    elif [[ "$de" == *XFCE* ]]; then
        echo "xfce"
    else
        echo "unknown"
    fi
}

kde_write() { (command -v kwriteconfig6 &>/dev/null && kwriteconfig6 "$@") || kwriteconfig5 "$@"; }
kde_read()  { (command -v kreadconfig6  &>/dev/null && kreadconfig6  "$@") || kreadconfig5  "$@" 2>/dev/null || echo ""; }

proxy_enable() {
    case "$(detect_de)" in
        gnome|xfce)
            gsettings set org.gnome.system.proxy mode 'manual'
            gsettings set org.gnome.system.proxy.http  host "$PROXY_HOST"
            gsettings set org.gnome.system.proxy.http  port  "$PROXY_PORT"
            gsettings set org.gnome.system.proxy.https host "$PROXY_HOST"
            gsettings set org.gnome.system.proxy.https port  "$PROXY_PORT"
            gsettings set org.gnome.system.proxy ignore-hosts "['localhost', '127.0.0.0/8', '::1']"
            ;;
        kde)
            kde_write --file kioslaverc --group "Proxy Settings" --key ProxyType  "1"
            kde_write --file kioslaverc --group "Proxy Settings" --key httpProxy  "http://$PROXY_HOST $PROXY_PORT"
            kde_write --file kioslaverc --group "Proxy Settings" --key httpsProxy "http://$PROXY_HOST $PROXY_PORT"
            kde_write --file kioslaverc --group "Proxy Settings" --key NoProxyFor "localhost,127.0.0.0/8,::1"
            dbus-send --session --type=signal /KIO/Scheduler \
                org.kde.KIO.Scheduler.reparseSlaveConfiguration string:'' 2>/dev/null || true
            ;;
        *)
            warn "Unknown desktop — set proxy manually: $PROXY_HOST:$PROXY_PORT"
            ;;
    esac
}

proxy_disable() {
    case "$(detect_de)" in
        gnome|xfce)
            gsettings set org.gnome.system.proxy mode 'none'
            ;;
        kde)
            kde_write --file kioslaverc --group "Proxy Settings" --key ProxyType "0"
            dbus-send --session --type=signal /KIO/Scheduler \
                org.kde.KIO.Scheduler.reparseSlaveConfiguration string:'' 2>/dev/null || true
            ;;
    esac
}

proxy_is_active() {
    case "$(detect_de)" in
        gnome|xfce)
            [[ "$(gsettings get org.gnome.system.proxy mode 2>/dev/null)" == "'manual'" ]]
            ;;
        kde)
            [[ "$(kde_read --file kioslaverc --group 'Proxy Settings' --key ProxyType)" == "1" ]]
            ;;
        *)
            [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
            ;;
    esac
}

ensure_warp() {
    if ! command -v warp-cli &>/dev/null; then
        error "Cloudflare WARP not installed. Run: sudo dpkg -i college-bypass.deb"
    fi
    local acct
    acct=$(warp-cli account 2>/dev/null || true)
    if echo "$acct" | grep -qi "Missing\|not registered\|unregistered"; then
        info "Registering WARP..."
        warp-cli register 2>/dev/null || warp-cli registration new 2>/dev/null || true
    fi
    if ! warp-cli status 2>/dev/null | grep -qi "Connected"; then
        info "Connecting WARP..."
        warp-cli connect 2>/dev/null || true
        local i=0
        while ! warp-cli status 2>/dev/null | grep -qi "Connected"; do
            sleep 1; i=$((i+1))
            [[ $i -ge 15 ]] && error "WARP failed to connect. Try: warp-cli connect"
        done
    fi
}

wait_for_port() {
    local i=0
    while ! ss -tlnp 2>/dev/null | grep -q ":${PROXY_PORT} "; do
        sleep 0.3; i=$((i+1))
        [[ $i -ge 17 ]] && return 1
    done
}

cmd_on() {
    ensure_warp

    if [[ -f "$PID_FILE" ]]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null || true
        rm -f "$PID_FILE"
    fi

    info "Starting SpoofDPI..."
    nohup "$SPOOFDPI_BIN" \
        --listen-addr "$PROXY_HOST:$PROXY_PORT" \
        --dns-addr    "1.1.1.1:53" \
        --dns-cache \
        --silent \
        > /tmp/spoofdpi.log 2>&1 &
    echo $! > "$PID_FILE"

    if ! wait_for_port; then
        rm -f "$PID_FILE"
        error "SpoofDPI failed to start. See /tmp/spoofdpi.log"
    fi

    proxy_enable
    success "Bypass is ON — DPI firewall bypassed."
}

cmd_off() {
    proxy_disable

    if [[ -f "$PID_FILE" ]]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null || true
        rm -f "$PID_FILE"
    else
        pkill -x spoofdpi 2>/dev/null || true
    fi

    success "Bypass is OFF — normal internet restored."
}

cmd_status() {
    local de warp_s proxy_s spoof_s
    de=$(detect_de)

    if command -v warp-cli &>/dev/null; then
        warp_s=$(warp-cli status 2>/dev/null | head -1 || echo "unknown")
    else
        warp_s="not installed"
    fi

    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        spoof_s="running (pid $(cat "$PID_FILE"), :$PROXY_PORT)"
    else
        spoof_s="stopped"
    fi

    if proxy_is_active; then
        proxy_s="active → $PROXY_HOST:$PROXY_PORT [$de]"
    else
        proxy_s="inactive [$de]"
    fi

    if _in_terminal; then
        echo ""
        printf "  \033[1mStatus\033[0m\n"
        printf "  ──────────────────────────────────\n"
        printf "  %-12s %s\n" "WARP:"     "$warp_s"
        printf "  %-12s %s\n" "SpoofDPI:" "$spoof_s"
        printf "  %-12s %s\n" "Proxy:"    "$proxy_s"
        echo ""
    else
        notify-send -i network-vpn "College Bypass — Status" \
            "WARP: $warp_s\nSpoofDPI: $spoof_s\nProxy: $proxy_s" 2>/dev/null || true
    fi
}

cmd_toggle() {
    if proxy_is_active; then cmd_off; else cmd_on; fi
}

case "${1:-toggle}" in
    on)     cmd_on     ;;
    off)    cmd_off    ;;
    status) cmd_status ;;
    toggle) cmd_toggle ;;
    *)
        echo "Usage: college-bypass [on|off|status|toggle]"
        exit 1
        ;;
esac
SCRIPT
chmod 755 "$PKG_DIR/usr/local/bin/college-bypass"

info "Writing GUI launcher (college-bypass-gui)..."
cat > "$PKG_DIR/usr/local/bin/college-bypass-gui" << 'LAUNCHER'
#!/bin/bash
exec python3 /usr/lib/college-bypass/college_bypass_ui.py
LAUNCHER
chmod 755 "$PKG_DIR/usr/local/bin/college-bypass-gui"

info "Running dpkg-deb..."
dpkg-deb --build --root-owner-group "$PKG_DIR" "$OUT_DEB"

rm -rf "$PKG_DIR"

echo ""
success "Built: $(basename "$OUT_DEB")"
echo ""
echo "  Install:   sudo dpkg -i $OUT_DEB"
echo "  GUI:       college-bypass-gui        (or click the app icon)"
echo "  CLI:       college-bypass             (terminal)"
echo ""