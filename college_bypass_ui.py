#!/usr/bin/env python3
import subprocess
import gi
import os

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, GLib

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8080
PID_FILE = "/tmp/spoofdpi.pid"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BYPASS_SCRIPT = os.path.join(SCRIPT_DIR, "bypass.sh")


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
        result = subprocess.run(
            ["warp-cli", "status"],
            capture_output=True, text=True, timeout=5
        )
        first = result.stdout.split("\n")[0].strip()
        return first if first else "unknown"
    except Exception:
        return "not installed"


def get_spoofdpi_status():
    if os.path.isfile(PID_FILE):
        try:
            pid = int(open(PID_FILE).read().strip())
            os.kill(pid, 0)
            return f"running (pid {pid}, :{PROXY_PORT})"
        except (ValueError, OSError):
            return "stopped (stale PID)"
    return "stopped"


def get_proxy_status():
    de = detect_de()
    if de in ("gnome", "xfce"):
        try:
            mode = subprocess.check_output(
                ["gsettings", "get", "org.gnome.system.proxy", "mode"],
                text=True
            ).strip().strip("'")
            return f"active  →  {PROXY_HOST}:{PROXY_PORT}  [{de}]" if mode == "manual" else f"inactive  [{de}]"
        except Exception:
            return f"inactive  [{de}]"
    elif de == "kde":
        try:
            result = subprocess.check_output(
                ["kreadconfig5", "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType"],
                text=True
            ).strip()
            return f"active  →  {PROXY_HOST}:{PROXY_PORT}  [{de}]" if result == "1" else f"inactive  [{de}]"
        except Exception:
            return f"inactive  [{de}]"
    return f"inactive  [{de}]"


def get_bypass_active():
    de = detect_de()
    if de in ("gnome", "xfce"):
        try:
            mode = subprocess.check_output(
                ["gsettings", "get", "org.gnome.system.proxy", "mode"],
                text=True
            ).strip().strip("'")
            return mode == "manual"
        except Exception:
            return os.path.isfile(PID_FILE)
    elif de == "kde":
        try:
            result = subprocess.check_output(
                ["kreadconfig5", "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType"],
                text=True
            ).strip()
            return result == "1"
        except Exception:
            return os.path.isfile(PID_FILE)
    return os.path.isfile(PID_FILE)


def call_bypass(action):
    try:
        subprocess.run([BYPASS_SCRIPT, action], capture_output=True, timeout=30)
    except Exception:
        pass


class CollegeBypassUI(Gtk.Window):
    def __init__(self):
        super().__init__(title="College Bypass")
        self.set_default_size(420, 260)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy", Gtk.main_quit)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_homogeneous(False)
        self.add(box)

        title_label = Gtk.Label()
        title_label.set_markup("<b><big>College Bypass</big></b>")
        title_label.set_margin_top(20)
        box.pack_start(title_label, False, False, 0)

        sep = Gtk.HSeparator()
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        box.pack_start(sep, False, False, 0)

        status_grid = Gtk.Grid()
        status_grid.set_row_spacing(8)
        status_grid.set_column_spacing(6)
        box.pack_start(status_grid, False, False, 0)

        self.warp_dot = Gtk.Label()
        self.warp_label = Gtk.Label()
        status_grid.attach(self.warp_dot, 0, 0, 1, 1)
        status_grid.attach(self.warp_label, 1, 0, 1, 1)

        self.spoofdot = Gtk.Label()
        self.spoof_label = Gtk.Label()
        status_grid.attach(self.spoofdot, 0, 1, 1, 1)
        status_grid.attach(self.spoof_label, 1, 1, 1, 1)

        self.proxy_dot = Gtk.Label()
        self.proxy_label = Gtk.Label()
        status_grid.attach(self.proxy_dot, 0, 2, 1, 1)
        status_grid.attach(self.proxy_label, 1, 2, 1, 1)

        btn_box = Gtk.Box(spacing=16)
        btn_box.set_margin_top(16)
        btn_box.set_margin_bottom(24)
        box.pack_start(btn_box, False, False, 0)

        self.btn_on = Gtk.Button(label="ON")
        self.btn_on.set_size_request(100, 40)
        self.btn_on.connect("clicked", self.on_on)
        btn_box.pack_start(self.btn_on, True, True, 0)

        self.btn_off = Gtk.Button(label="OFF")
        self.btn_off.set_size_request(100, 40)
        self.btn_off.connect("clicked", self.on_off)
        btn_box.pack_start(self.btn_off, True, True, 0)

        GLib.timeout_add(2000, self.refresh)

    def color_dot(self, is_good):
        return "<span color='#2ecc71'>●</span>" if is_good else "<span color='#e74c3c'>●</span>"

    def refresh(self):
        warp_raw = get_warp_status()
        warp_ok = "connected" in warp_raw.lower()

        spoof_raw = get_spoofdpi_status()
        spoof_ok = spoof_raw.startswith("running")

        proxy_raw = get_proxy_status()
        proxy_ok = "active" in proxy_raw.lower()

        self.warp_label.set_markup(f"<b>WARP:</b>       {warp_raw}")
        self.spoof_label.set_markup(f"<b>SpoofDPI:</b>  {spoof_raw}")
        self.proxy_label.set_markup(f"<b>Proxy:</b>     {proxy_raw}")

        self.warp_dot.set_markup(self.color_dot(warp_ok))
        self.spoofdot.set_markup(self.color_dot(spoof_ok))
        self.proxy_dot.set_markup(self.color_dot(proxy_ok))

        active = get_bypass_active()
        self.btn_on.set_sensitive(not active)
        self.btn_off.set_sensitive(active)

        return True

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