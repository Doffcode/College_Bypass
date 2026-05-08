# College Firewall Bypass

Bypasses your college's Deep Packet Inspection (DPI) firewall using **SpoofDPI** (fragments the TLS handshake to hide the SNI) + **Cloudflare WARP** (encrypts the tunnel).

---

## Usage

### GUI (recommended)
```
college-bypass-gui
```
Or click the **College Bypass** icon in your app menu.

The GUI shows live status of WARP, SpoofDPI, and your proxy. Use the **ON** and **OFF** buttons to toggle the bypass.

### CLI
```
./bypass.sh
```

- **First run:** auto-installs SpoofDPI and Cloudflare WARP if missing, auto-connects WARP, then turns the bypass **ON**.
- **Every run after:** toggles the bypass **ON** or **OFF**.

### Optional subcommands

```bash
./bypass.sh on       # force ON
./bypass.sh off      # force OFF
./bypass.sh status   # show current state
```

That's it. No manual setup steps.

> If Tailscale is running, turn it off first — it conflicts with WARP: `sudo tailscale down`

### Optional subcommands

```bash
./bypass.sh on       # force ON
./bypass.sh off      # force OFF
./bypass.sh status   # show current state
```

Works on GNOME, Cinnamon, KDE Plasma 5/6, and XFCE.

---

## How it works

1. `bypass.sh on` verifies WARP is connected, then starts SpoofDPI as a local HTTP proxy on `127.0.0.1:8080` with DNS routed through `1.1.1.1` (bypassing the college's DNS blocks).
2. It sets your system proxy to that local port — all browser traffic flows through SpoofDPI → WARP → internet.
3. `bypass.sh off` kills the proxy process (tracked by PID file) and restores your system proxy settings.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Sites still blocked | Run `./bypass.sh status` and confirm all three lines show active/running |
| WARP not connected | `warp-cli connect` |
| Tailscale conflict | `sudo tailscale down` |
| SpoofDPI crashed | Check `/tmp/spoofdpi.log` |
| Browser shows cached block page | Fully close and reopen your browser |
