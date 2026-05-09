#!/usr/bin/env python3
import subprocess
import gi
import os
import sys

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, GLib, Gdk

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8080
PID_FILE = "/tmp/spoofdpi.pid"
SPOOFDPI_BIN = "/usr/lib/college-bypass/spoofdpi"
BYPASS_CLI = "/usr/local/bin/college-bypass"

CSS = b"""
window { background-color: #1a1a2e; }
.vbox { background-color: #1a1a2e; }
.title { font-size: 24px; font-weight: bold; color: #ffffff; }
.subtitle { font-size: 12px; color: #6c7a89; }

.card {
    background: #16213e;
    border-radius: 14px;
    padding: 14px 16px;
    margin: 8px 20px;
}

.card-label { font-size: 16px; font-weight: bold; color: #ffffff; }
.card-value { font-size: 13px; color: #6c7a89; }

.btn-green {
    background: #0f766e;
    color: #ffffff;
    border-radius: 8px;
    font-size: 13px;
    font-weight: bold;
    padding: 8px 16px;
    border: none;
}
.btn-green:hover { background: #14b8a6; }

.btn-red {
    background: #991b1b;
    color: #ffffff;
    border-radius: 8px;
    font-size: 13px;
    font-weight: bold;
    padding: 8px 16px;
    border: none;
}
.btn-red:hover { background: #ef4444; }

.btn-green:disabled { background: #1e3a2f; color: #4b6b60; }
.btn-red:disabled  { background: #3a1e1e; color: #6b4b4b; }

.dot-green { font-size: 18px; }
.dot-red   { font-size: 18px; }

.divider { background: #0f3460; height: 1px; margin: 4px 20px; }
"""


def detect_de():
    de = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if "KDE" in de or "plasma" in de:
        return "kde"
    elif "GNOME" in de or "Unity" in de or "Cinnamon" in de:
        return "gnome"
    elif "XFCE" in de:
        return "xfce"
    return "unknown"


def get_warp_status():
    try:
        r = subprocess.run(["warp-cli", "status"], capture_output=True, text=True, timeout=5)
        return r.stdout.split("\n")[0].strip() or "unknown"
    except Exception:
        return "not installed"


def is_warp_connected():
    return "connected" in get_warp_status().lower()


def get_spoofdpi_status():
    if os.path.isfile(PID_FILE):
        try:
            pid = int(open(PID_FILE).read().strip())
            os.kill(pid, 0)
            return f"running  (pid {pid})", True
        except (ValueError, OSError):
            pass
    return "stopped", False


def get_proxy_status():
    de = detect_de()
    if de in ("gnome", "xfce"):
        try:
            mode = subprocess.check_output(
                ["gsettings", "get", "org.gnome.system.proxy", "mode"], text=True
            ).strip().strip("'")
            return f"active  →  {PROXY_HOST}:{PROXY_PORT}" if mode == "manual" else "inactive"
        except Exception:
            return "inactive"
    elif de == "kde":
        try:
            r = subprocess.check_output(
                ["kreadconfig5", "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType"],
                text=True
            ).strip()
            return f"active  →  {PROXY_HOST}:{PROXY_PORT}" if r == "1" else "inactive"
        except Exception:
            return "inactive"
    return "inactive"


def is_bypass_active():
    de = detect_de()
    if de in ("gnome", "xfce"):
        try:
            mode = subprocess.check_output(
                ["gsettings", "get", "org.gnome.system.proxy", "mode"], text=True
            ).strip().strip("'")
            return mode == "manual"
        except Exception:
            return os.path.isfile(PID_FILE)
    elif de == "kde":
        try:
            r = subprocess.check_output(
                ["kreadconfig5", "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType"],
                text=True
            ).strip()
            return r == "1"
        except Exception:
            return os.path.isfile(PID_FILE)
    return os.path.isfile(PID_FILE)


def run(cmd, timeout=30):
    try:
        subprocess.run(cmd, capture_output=True, timeout=timeout)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)


def apply_css():
    p = Gtk.CssProvider()
    p.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), p, 600)


class StatusRow(Gtk.Box):
    def __init__(self, label, value, btn_label, btn_style, callback):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.CENTER)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        card.set_halign(Gtk.Align.FILL)
        card.set_valign(Gtk.Align.CENTER)
        card.set_size_request(-1, 54)
        card.set_margin_start(4)
        card.set_margin_end(4)

        sc = card.get_style_context()
        p = Gtk.CssProvider()
        p.load_from_data(b".card { background: #16213e; border-radius: 14px; padding: 0; }")
        sc.add_provider(p, 600)

        self.dot = Gtk.Label()
        self.dot.set_markup("<span color='#6c7a89' size='16000'>●</span>")
        self.dot.set_size_request(30, -1)
        card.pack_start(self.dot, False, False, 0)

        self.lbl = Gtk.Label()
        self.lbl.set_markup(f"<b><span size='15000' color='#ffffff'>{label}</span></b>")
        card.pack_start(self.lbl, False, False, 0)

        self.val = Gtk.Label()
        self.val.set_markup(f"<span size='12000' color='#6c7a89'>{value}</span>")
        self.val.set_hexpand(True)
        card.pack_start(self.val, True, True, 0)

        self.btn = Gtk.Button(label=f"  {btn_label}  ")
        self.btn.get_style_context().add_class(f"btn-{btn_style}")
        self.btn.connect("clicked", callback)
        card.pack_start(self.btn, False, False, 0)

        self.pack_start(card, True, True, 0)


class CollegeBypassUI(Gtk.Window):
    def __init__(self):
        super().__init__(title="College Bypass")
        self.set_default_size(460, 440)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        self.connect("destroy", Gtk.main_quit)

        apply_css()

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_homogeneous(False)
        self.add(main)

        hdr = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        hdr.set_margin_top(28)
        hdr.set_margin_bottom(16)
        main.pack_start(hdr, False, False, 0)

        t = Gtk.Label()
        t.set_markup("<span size='24000' weight='bold' color='#ffffff'>College Bypass</span>")
        hdr.pack_start(t, False, False, 0)

        s = Gtk.Label()
        s.set_markup("<span size='11000' color='#6c7a89'>DPI Firewall Bypass Utility</span>")
        hdr.pack_start(s, False, False, 0)

        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        rows.set_margin_start(16)
        rows.set_margin_end(16)
        main.pack_start(rows, True, True, 0)

        self.warp_row = StatusRow("WARP", "", "Connect", "green", self.on_warp_connect)
        rows.pack_start(self.warp_row, False, False, 0)

        sep1 = Gtk.Separator()
        sep1.set_margin_start(20)
        sep1.set_margin_end(20)
        sep1.set_margin_top(4)
        sep1.set_margin_bottom(4)
        sc = sep1.get_style_context()
        p = Gtk.CssProvider()
        p.load_from_data(b"separator { background: #0f3460; min-height: 1px; }")
        sc.add_provider(p, 600)
        rows.pack_start(sep1, False, False, 0)

        self.spoof_row = StatusRow("SpoofDPI", "", "Start", "green", self.on_spoof_start)
        rows.pack_start(self.spoof_row, False, False, 0)

        sep2 = Gtk.Separator()
        sep2.set_margin_start(20)
        sep2.set_margin_end(20)
        sep2.set_margin_top(4)
        sep2.set_margin_bottom(4)
        sc2 = sep2.get_style_context()
        p2 = Gtk.CssProvider()
        p2.load_from_data(b"separator { background: #0f3460; min-height: 1px; }")
        sc2.add_provider(p2, 600)
        rows.pack_start(sep2, False, False, 0)

        self.proxy_row = StatusRow("Proxy", "", "ON", "green", self.on_bypass_toggle)
        rows.pack_start(self.proxy_row, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        footer.set_margin_top(20)
        footer.set_margin_bottom(28)
        footer.set_halign(Gtk.Align.CENTER)
        main.pack_start(footer, False, False, 0)

        self.btn_on = Gtk.Button(label="  Bypass ON  ")
        self.btn_on.set_size_request(140, 50)
        self.btn_on.get_style_context().add_class("btn-green")
        self.btn_on.connect("clicked", self.on_bypass_on)
        footer.pack_start(self.btn_on, False, False, 0)

        self.btn_off = Gtk.Button(label="  Bypass OFF  ")
        self.btn_off.set_size_request(140, 50)
        self.btn_off.get_style_context().add_class("btn-red")
        self.btn_off.connect("clicked", self.on_bypass_off)
        footer.pack_start(self.btn_off, False, False, 0)

        GLib.timeout_add(2000, self.refresh)
        self.refresh()

    def _update_row(self, row, ok, value, btn_label, btn_style):
        color = "#2ecc71" if ok else "#e74c3c"
        row.dot.set_markup(f"<span color='{color}' size='16000'>●</span>")
        row.val.set_markup(f"<span size='12000' color='#6c7a89'>{value}</span>")
        row.btn.set_label(f"  {btn_label}  ")
        row.btn.get_style_context().remove_class("btn-green")
        row.btn.get_style_context().remove_class("btn-red")
        row.btn.get_style_context().add_class(f"btn-{btn_style}")

    def refresh(self):
        warp_raw = get_warp_status()
        warp_ok = is_warp_connected()
        spoof_raw, spoof_ok = get_spoofdpi_status()
        proxy_raw = get_proxy_status()
        proxy_ok = "active" in proxy_raw.lower()
        active = is_bypass_active()

        self._update_row(
            self.warp_row, warp_ok, warp_raw,
            "Disconnect" if warp_ok else "Connect", "red" if warp_ok else "green"
        )
        self._update_row(
            self.spoof_row, spoof_ok, spoof_raw,
            "Stop" if spoof_ok else "Start", "red" if spoof_ok else "green"
        )
        self._update_row(
            self.proxy_row, proxy_ok, proxy_raw,
            "OFF" if proxy_ok else "ON", "red" if proxy_ok else "green"
        )

        self.btn_on.set_sensitive(not active)
        self.btn_off.set_sensitive(active)

        return True

    def on_warp_connect(self, _):
        if is_warp_connected():
            run(["warp-cli", "disconnect"])
        else:
            run(["warp-cli", "connect"])
        self.refresh()

    def on_spoof_start(self, _):
        _, running = get_spoofdpi_status()
        if running:
            if os.path.isfile(PID_FILE):
                try:
                    os.kill(int(open(PID_FILE).read().strip()), 9)
                except Exception:
                    pass
                os.remove(PID_FILE)
        else:
            run([SPOOFDPI_BIN, "--listen-addr", f"{PROXY_HOST}:{PROXY_PORT}",
                 "--dns-addr", "1.1.1.1:53", "--dns-cache", "--silent"])
        self.refresh()

    def on_bypass_toggle(self, _):
        if is_bypass_active():
            run([BYPASS_CLI, "off"])
        else:
            run([BYPASS_CLI, "on"])
        self.refresh()

    def on_bypass_on(self, _):
        run([BYPASS_CLI, "on"])
        self.refresh()

    def on_bypass_off(self, _):
        run([BYPASS_CLI, "off"])
        self.refresh()


if __name__ == "__main__":
    win = CollegeBypassUI()
    win.show_all()
    Gtk.main()