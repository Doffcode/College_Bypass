#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPOOFDPI_BIN="$SCRIPT_DIR/spoofdpi"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "  ${BLUE}[*]${NC} $*"; }
success() { echo -e "  ${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "  ${YELLOW}[!]${NC} $*"; }
error()   { echo -e "  ${RED}[✗]${NC} $*" >&2; exit 1; }

detect_arch() {
    case "$(uname -m)" in
        x86_64)        echo "amd64" ;;
        aarch64|arm64) echo "arm64" ;;
        armv7l)        echo "arm" ;;
        *) error "Unsupported CPU architecture: $(uname -m)" ;;
    esac
}

install_spoofdpi() {
    if [[ -x "$SPOOFDPI_BIN" ]]; then
        success "SpoofDPI already present — skipping download"
        return
    fi

    local arch
    arch=$(detect_arch)
    local url="https://github.com/xvzc/SpoofDPI/releases/latest/download/spoofdpi-linux-$arch"

    info "Downloading SpoofDPI (linux/$arch) from GitHub..."
    curl -fsSL --progress-bar -o "$SPOOFDPI_BIN" "$url" \
        || error "Download failed. Check your internet connection."
    chmod +x "$SPOOFDPI_BIN"
    success "SpoofDPI downloaded and ready"
}

install_warp() {
    if command -v warp-cli &>/dev/null; then
        success "Cloudflare WARP already installed — skipping"
        return
    fi

    info "Installing Cloudflare WARP..."
    local arch
    arch=$(dpkg --print-architecture 2>/dev/null || detect_arch)

    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg \
        | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg \
        || error "Failed to import Cloudflare GPG key"

    echo "deb [arch=$arch signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" \
        | sudo tee /etc/apt/sources.list.d/cloudflare-client.list > /dev/null

    sudo apt-get update -qq || error "apt-get update failed"
    sudo apt-get install -y cloudflare-warp || error "WARP installation failed"
    success "Cloudflare WARP installed"
}

register_warp() {
    local account_info
    account_info=$(warp-cli account 2>/dev/null || true)

    if echo "$account_info" | grep -qi "Missing\|not registered\|unregistered"; then
        info "Registering WARP (you may be prompted to accept the Terms of Service)..."
        warp-cli register 2>/dev/null \
            || warp-cli registration new 2>/dev/null \
            || warn "Could not auto-register — run manually: warp-cli register"
        success "WARP registered"
    else
        success "WARP already registered"
    fi
}

main() {
    echo ""
    echo -e "  ${BOLD}College Firewall Bypass — Setup${NC}"
    echo "  ================================"
    echo ""

    install_spoofdpi
    install_warp
    register_warp

    echo ""
    echo -e "  ${GREEN}${BOLD}All done!${NC} Next steps:"
    echo ""
    echo "    1.  Connect WARP:   warp-cli connect"
    echo "    2.  Start bypass:   ./bypass.sh"
    echo ""
}

main "$@"
