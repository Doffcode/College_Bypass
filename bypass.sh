#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPOOFDPI_BIN="$SCRIPT_DIR/spoofdpi"
PROXY_HOST="127.0.0.1"
PROXY_PORT=8080
PID_FILE="/tmp/spoofdpi.pid"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "  ${BLUE}[*]${NC} $*"; }
success() { echo -e "  ${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "  ${YELLOW}[!]${NC} $*"; }
error()   { echo -e "  ${RED}[✗]${NC} $*" >&2; exit 1; }

# ── Desktop Environment ────────────────────────────────────────────────────────

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

# Plasma 5 and 6 ship different binary names
kde_write() { (command -v kwriteconfig6 &>/dev/null && kwriteconfig6 "$@") \
                || kwriteconfig5 "$@"; }
kde_read()  { (command -v kreadconfig6  &>/dev/null && kreadconfig6  "$@") \
                || kreadconfig5  "$@" 2>/dev/null || echo ""; }

# ── Proxy helpers ──────────────────────────────────────────────────────────────

proxy_enable() {
    case "$(detect_de)" in
        gnome|xfce)
            gsettings set org.gnome.system.proxy mode 'manual'
            gsettings set org.gnome.system.proxy.http  host "$PROXY_HOST"
            gsettings set org.gnome.system.proxy.http  port  "$PROXY_PORT"
            gsettings set org.gnome.system.proxy.https host "$PROXY_HOST"
            gsettings set org.gnome.system.proxy.https port  "$PROXY_PORT"
            gsettings set org.gnome.system.proxy ignore-hosts \
                "['localhost', '127.0.0.0/8', '::1']"
            ;;
        kde)
            kde_write --file kioslaverc --group "Proxy Settings" --key ProxyType   "1"
            kde_write --file kioslaverc --group "Proxy Settings" --key httpProxy   "http://$PROXY_HOST $PROXY_PORT"
            kde_write --file kioslaverc --group "Proxy Settings" --key httpsProxy  "http://$PROXY_HOST $PROXY_PORT"
            kde_write --file kioslaverc --group "Proxy Settings" --key NoProxyFor  "localhost,127.0.0.0/8,::1"
            dbus-send --session --type=signal /KIO/Scheduler \
                org.kde.KIO.Scheduler.reparseSlaveConfiguration string:'' 2>/dev/null || true
            ;;
        *)
            warn "Desktop not auto-detected — set proxy manually: $PROXY_HOST:$PROXY_PORT"
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
        *)
            warn "Desktop not auto-detected — disable your proxy manually."
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

# ── Auto-healing preflight ─────────────────────────────────────────────────────

ensure_binary() {
    [[ -x "$SPOOFDPI_BIN" ]] && return
    info "SpoofDPI not found — running setup..."
    bash "$SCRIPT_DIR/setup.sh" || error "Setup failed. Re-run: ./setup.sh"
    [[ -x "$SPOOFDPI_BIN" ]] || error "SpoofDPI still missing after setup."
}

ensure_warp() {
    if ! command -v warp-cli &>/dev/null; then
        info "Cloudflare WARP not installed — running setup..."
        bash "$SCRIPT_DIR/setup.sh" || error "Setup failed. Re-run: ./setup.sh"
    fi
    if ! warp-cli status 2>/dev/null | grep -qi "Connected"; then
        info "WARP not connected — connecting..."
        warp-cli connect || error "Could not connect WARP. Try manually: warp-cli connect"
        # Give WARP a moment to establish the tunnel
        local i=0
        while ! warp-cli status 2>/dev/null | grep -qi "Connected"; do
            sleep 1; i=$((i+1))
            [[ $i -ge 15 ]] && error "WARP did not connect in time. Try: warp-cli connect"
        done
        success "WARP connected"
    fi
}

# Poll for the proxy port to open (max ~5 s)
wait_for_port() {
    local i=0
    while ! ss -tlnp 2>/dev/null | grep -q ":${PROXY_PORT} "; do
        sleep 0.3
        i=$((i + 1))
        [[ $i -ge 17 ]] && return 1
    done
}

# ── Commands ───────────────────────────────────────────────────────────────────

cmd_on() {
    ensure_binary
    ensure_warp

    # Kill any stale instance tracked in PID file
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
        error "SpoofDPI failed to start on port $PROXY_PORT. See: /tmp/spoofdpi.log"
    fi

    proxy_enable

    echo ""
    success "Bypass is ON — browser traffic is now bypassing DPI."
    echo ""
}

cmd_off() {
    proxy_disable

    if [[ -f "$PID_FILE" ]]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null || true
        rm -f "$PID_FILE"
    else
        pkill -x spoofdpi 2>/dev/null || true
    fi

    echo ""
    success "Bypass is OFF — normal internet settings restored."
    echo ""
}

cmd_status() {
    local de
    de=$(detect_de)
    echo ""
    echo -e "  ${BOLD}Status${NC}"
    echo "  ──────────────────────────────────"

    if command -v warp-cli &>/dev/null; then
        local ws
        ws=$(warp-cli status 2>/dev/null | head -1 || echo "unknown")
        printf "  %-12s %s\n" "WARP:" "$ws"
    else
        printf "  %-12s %s\n" "WARP:" "not installed  (run ./setup.sh)"
    fi

    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        printf "  %-12s %s\n" "SpoofDPI:" "running  (pid $(cat "$PID_FILE"), :$PROXY_PORT)"
    else
        printf "  %-12s %s\n" "SpoofDPI:" "stopped"
    fi

    if proxy_is_active; then
        printf "  %-12s %s\n" "Proxy:" "active → $PROXY_HOST:$PROXY_PORT  [$de]"
    else
        printf "  %-12s %s\n" "Proxy:" "inactive  [$de]"
    fi

    echo ""
}

cmd_toggle() {
    if proxy_is_active; then
        cmd_off
    else
        cmd_on
    fi
}

# ── Entry point ────────────────────────────────────────────────────────────────

case "${1:-toggle}" in
    on)     cmd_on     ;;
    off)    cmd_off    ;;
    status) cmd_status ;;
    toggle) cmd_toggle ;;
    *)
        echo ""
        echo "  Usage: $(basename "$0") [on|off|status|toggle]"
        echo "  Default (no argument): toggle"
        echo ""
        exit 1
        ;;
esac
