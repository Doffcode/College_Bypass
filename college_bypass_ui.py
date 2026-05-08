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

BYPASS_CLI = "/usr/local/bin/college-bypass"

GREEN_HEX = "#27ae60"
RED_HEX   = "#c0392b"
BLUE_HEX  = "#2980b9"
BG_HEX    = "#f5f6fa"
CARD_HEX  = "#ffffff"
TEXT_HEX  = "#2c3e50"
DIM_HEX   = "#7f8c8d"


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


def get_spoofdpi_status():
    if os.path.isfile(PID_FILE):
        try:
            pid = int(open(PID_FILE).read().strip())
            os.kill(pid, 0)
            return f"running (pid {pid})"
        except (ValueError, OSError):
            pass
    return "stopped"


def get_proxy_status():
    de = detect_de()
    if de in ("gnome", "xfce"):
        try:
            mode = subprocess.check_output(
                ["gsettings", "get", "org.gnome.system.proxy", "mode"], text=True
            ).strip().strip("'")
            return f"active  →  {PROXY_HOST}:{PROXY_PORT}  [{de}]" if mode == "manual" else f"inactive  [{de}]"
        except Exception:
            return f"inactive  [{de}]"
    elif de == "kde":
        try:
            r = subprocess.check_output(
                ["kreadconfig5", "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType"],
                text=True
            ).strip()
            return f"active  →  {PROXY_HOST}:{PROXY_PORT}  [{de}]" if r == "1" else f"inactive  [{de}]"
        except Exception:
            return f"inactive  [{de}]"
    return f"inactive  [{de}]"


def is_active():
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


def call_bypass(action):
    try:
        env = os.environ.copy()
        subprocess.run(
            [BYPASS_CLI, action],
            env=env,
            capture_output=True,
            timeout=30
        )
    except Exception as e:
        print(f"Error calling bypass: {e}", file=sys.stderr)


def hex_to_rgba(hex_color, alpha=1.0):
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    return Gdk.RGBA(r, g, b, alpha)


def apply_css():
    css = b"""
    window { background-color: #f5f6fa; }
    .title-label { font-size: 22px; font-weight: bold; color: #2c3e50; }
    .subtitle { font-size: 12px; color: #7f8c8d; }
    .status-row { padding: 10px 16px; background: #ffffff; border-radius: 10px; margin: 6px 20px; }
    .status-label { font-size: 14px; font-weight: 600; color: #2c3e50; }
    .status-value { font-size: 13px; color: #7f8c8d; }
    .dot { font-size: 20px; }
    .btn-on {
        background-color: #27ae60;
        color: #ffffff;
        border-radius: 10px;
        font-size: 16px;
        font-weight: bold;
        padding: 14px;
        border: none;
    }
    .btn-on:hover { background-color: #2ecc71; }
    .btn-on:disabled { background-color: #bdc3c7; }
    .btn-off {
        background-color: #c0392b;
        color: #ffffff;
        border-radius: 10px;
        font-size: 16px;
        font-weight: bold;
        padding: 14px;
        border: none;
    }
    .btn-off:hover { background-color: #e74c3c; }
    .btn-off:disabled { background-color: #bdc3c7; }
    """
    style_provider = Gtk.CssProvider()
    style_provider.load_from_data(css)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), style_provider, 600)


class CollegeBypassUI(Gtk.Window):
    def __init__(self):
        super().__init__(title="College Bypass")
        self.set_default_size(440, 360)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        self.connect("destroy", Gtk.main_quit)

        apply_css()

        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_vbox)

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        header.set_margin_top(24)
        header.set_margin_bottom(12)
        main_vbox.pack_start(header, False, False, 0)

        title = Gtk.Label()
        title.set_markup("<span size='22000' weight='bold' color='#2c3e50'>College Bypass</span>")
        header.pack_start(title, False, False, 0)

        subtitle = Gtk.Label()
        subtitle.set_markup("<span size='11000' color='#7f8c8d'>DPI Firewall Bypass</span>")
        header.pack_start(subtitle, False, False, 0)

        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        status_box.set_margin_left(16)
        status_box.set_margin_right(16)
        main_vbox.pack_start(status_box, True, True, 0)

        self.warp_row   = self._make_row("WARP",       "")
        self.spoof_row  = self._make_row("SpoofDPI",   "")
        self.proxy_row  = self._make_row("Proxy",       "")

        status_box.pack_start(self.warp_row,  False, False, 0)
        status_box.pack_start(self.spoof_row,  False, False, 0)
        status_box.pack_start(self.proxy_row,  False, False, 0)

        btn_box = Gtk.Box(spacing=16)
        btn_box.set_margin_top(16)
        btn_box.set_margin_bottom(28)
        btn_box.set_halign(Gtk.Align.CENTER)
        main_vbox.pack_start(btn_box, False, False, 0)

        self.btn_on = Gtk.Button(label="  ON  ")
        self.btn_on.set_size_request(130, 52)
        self.btn_on.get_style_context().add_class("btn-on")
        self.btn_on.connect("clicked", self.on_on)
        btn_box.pack_start(self.btn_on, False, False, 0)

        self.btn_off = Gtk.Button(label="  OFF  ")
        self.btn_off.set_size_request(130, 52)
        self.btn_off.get_style_context().add_class("btn-off")
        self.btn_off.connect("clicked", self.on_off)
        btn_box.pack_start(self.btn_off, False, False, 0)

        GLib.timeout_add(2000, self.refresh)

    def _make_row(self, label_text, value_text):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        row.set_halign(Gtk.Align.FILL)
        row.set_valign(Gtk.Align.CENTER)

        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        card.set_halign(Gtk.Align.FILL)
        card.set_valign(Gtk.Align.CENTER)
        card.set_size_request(-1, 52)
        card.set_margin_top(5)
        card.set_margin_bottom(5)
        card.set_margin_left(4)
        card.set_margin_right(4)
        style = card.get_style_context()
        style.add_class("status-row")

        scard = Gtk.StyleContext()
        provider = Gtk.CssProvider()
        provider.load_from_data(b".status-row { background: #ffffff; border-radius: 10px; border: 1px solid #ecf0f1; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }")
        style.add_provider(provider, 600)

        dot = Gtk.Label()
        dot.set_markup(f"<span color='#bdc3c7' size='18000'>●</span>")
        dot.set_size_request(32, -1)
        card.pack_start(dot, False, False, 0)

        lbl = Gtk.Label()
        lbl.set_markup(f"<b><span size='13000' color='#2c3e50'>{label_text}</span></b>")
        lbl.set_halign(Gtk.Align.START)
        card.pack_start(lbl, False, False, 0)

        val = Gtk.Label()
        val.set_markup(f"<span size='12000' color='#7f8c8d'>{value_text}</span>")
        val.set_halign(Gtk.Align.END)
        val.set_hexpand(True)
        card.pack_start(val, True, True, 0)

        row.pack_start(card, True, True, 0)
        return row

    def refresh(self):
        warp_raw  = get_warp_status()
        spoof_raw = get_spoofdpi_status()
        proxy_raw = get_proxy_status()
        active    = is_active()

        warp_ok   = "connected" in warp_raw.lower()
        spoof_ok  = spoof_raw.startswith("running")
        proxy_ok  = "active" in proxy_raw.lower()

        self._update_row(self.warp_row,  warp_ok,   f"<b><span size='13000' color='#2c3e50'>WARP</span></b>",       f"<span size='12000' color='#7f8c8d'>{warp_raw}</span>")
        self._update_row(self.spoof_row, spoof_ok,   f"<b><span size='13000' color='#2c3e50'>SpoofDPI</span></b>",   f"<span size='12000' color='#7f8c8d'>{spoof_raw}</span>")
        self._update_row(self.proxy_row, proxy_ok,   f"<b><span size='13000' color='#2c3e50'>Proxy</span></b>",       f"<span size='12000' color='#7f8c8d'>{proxy_raw}</span>")

        self.btn_on.set_sensitive(not active)
        self.btn_off.set_sensitive(active)

        return True

    def _update_row(self, row, ok, label_markup, value_markup):
        card = row.get_children()[0]
        dot  = card.get_children()[0]
        lbl  = card.get_children()[1]
        val  = card.get_children()[2]
        color = "#27ae60" if ok else "#e74c3c"
        dot.set_markup(f"<span color='{color}' size='18000'>●</span>")
        lbl.set_markup(label_markup)
        val.set_markup(value_markup)

    def on_on(self, _):
        call_bypass("on")
        self.refresh()

    def on_off(self, _):
        call_bypass("off")
        self.refresh()


if __name__ == "__main__":
    win = CollegeBypassUI()
    win.show_all()
    win.refresh()
    Gtk.main()