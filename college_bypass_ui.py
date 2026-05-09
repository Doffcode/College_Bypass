#!/usr/bin/env python3
import subprocess
import gi
import os
import sys

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8080
PID_FILE = "/tmp/spoofdpi.pid"
SPOOFDPI_BIN = "/usr/lib/college-bypass/spoofdpi"
BYPASS_CLI = "/usr/local/bin/college-bypass"


def detect_de():
    de = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if "KDE" in de or "plasma" in de:
        return "kde"
    if "GNOME" in de or "Unity" in de or "Cinnamon" in de:
        return "gnome"
    if "XFCE" in de:
        return "xfce"
    return "unknown"


def get_warp_status():
    try:
        r = subprocess.run(["warp-cli", "status"], capture_output=True, text=True, timeout=5)
        line = r.stdout.split("\n")[0].strip()
        return line if line else "unknown"
    except Exception:
        return "not installed"


def is_warp_connected():
    return "connected" in get_warp_status().lower()


def get_spoofdpi_status():
    if os.path.isfile(PID_FILE):
        try:
            pid = int(open(PID_FILE).read().strip())
            os.kill(pid, 0)
            return f"running (pid {pid})", True
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
            return f"active  ->  {PROXY_HOST}:{PROXY_PORT}" if mode == "manual" else "inactive"
        except Exception:
            return "inactive"
    if de == "kde":
        try:
            r = subprocess.check_output(
                ["kreadconfig5", "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType"],
                text=True
            ).strip()
            return f"active  ->  {PROXY_HOST}:{PROXY_PORT}" if r == "1" else "inactive"
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
            pass
    return os.path.isfile(PID_FILE)


def run_cmd(cmd, timeout=30):
    try:
        subprocess.run(cmd, capture_output=True, timeout=timeout)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)


class StatusCard(Gtk.Box):
    def __init__(self, label, on_click):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.CENTER)
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_top(10)
        self.set_margin_bottom(10)

        self.dot = Gtk.Label()
        self.dot.set_markup("<span color='#999' size='16000'>●</span>")
        self.dot.set_size_request(28, -1)
        self.pack_start(self.dot, False, False, 0)

        self.lbl = Gtk.Label()
        self.lbl.set_text(label)
        self.lbl.set_size_request(90, -1)
        self.pack_start(self.lbl, False, False, 0)

        self.val = Gtk.Label()
        self.val.set_text("")
        self.val.set_halign(Gtk.Align.START)
        self.val.set_hexpand(True)
        self.pack_start(self.val, True, True, 0)

        self.btn = Gtk.Button()
        self.btn.set_size_request(80, 32)
        self.btn.connect("clicked", on_click)
        self.pack_start(self.btn, False, False, 0)

    def update(self, value, dot_color, btn_label):
        self.val.set_text(value)
        self.dot.set_markup(f"<span color='{dot_color}' size='16000'>●</span>")
        self.btn.set_label(btn_label)


class CollegeBypassUI(Gtk.Window):
    def __init__(self):
        super().__init__(title="College Bypass")
        self.set_default_size(480, 420)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        self.connect("destroy", Gtk.main_quit)

        self.apply_styles()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add(box)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_margin_top(20)
        title_box.set_margin_bottom(16)
        title_box.set_halign(Gtk.Align.CENTER)
        box.pack_start(title_box, False, False, 0)

        t = Gtk.Label()
        t.set_markup("<b><big>College Bypass</big></b>")
        title_box.pack_start(t, False, False, 0)

        sub = Gtk.Label()
        sub.set_text("DPI Firewall Bypass Utility")
        sub.set_size_request(200, 20)
        title_box.pack_start(sub, False, False, 0)

        status_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        status_container.set_margin_start(24)
        status_container.set_margin_end(24)
        box.pack_start(status_container, True, True, 0)

        self.warp_card = StatusCard("WARP", lambda _: self.on_warp())
        status_container.pack_start(self.warp_card, False, False, 0)

        sep1 = Gtk.Separator()
        sep1.set_margin_top(6)
        sep1.set_margin_bottom(6)
        status_container.pack_start(sep1, False, False, 0)

        self.spoof_card = StatusCard("SpoofDPI", lambda _: self.on_spoof())
        status_container.pack_start(self.spoof_card, False, False, 0)

        sep2 = Gtk.Separator()
        sep2.set_margin_top(6)
        sep2.set_margin_bottom(6)
        status_container.pack_start(sep2, False, False, 0)

        self.proxy_card = StatusCard("Proxy", lambda _: self.on_proxy())
        status_container.pack_start(self.proxy_card, False, False, 0)

        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        footer_box.set_margin_top(16)
        footer_box.set_margin_bottom(24)
        footer_box.set_halign(Gtk.Align.CENTER)
        box.pack_start(footer_box, False, False, 0)

        self.btn_on = Gtk.Button(label="Bypass ON")
        self.btn_on.set_size_request(130, 44)
        self.btn_on.connect("clicked", lambda _: self.on_bypass("on"))
        footer_box.pack_start(self.btn_on, False, False, 0)

        self.btn_off = Gtk.Button(label="Bypass OFF")
        self.btn_off.set_size_request(130, 44)
        self.btn_off.connect("clicked", lambda _: self.on_bypass("off"))
        footer_box.pack_start(self.btn_off, False, False, 0)

        GLib.timeout_add(2000, self.refresh)
        self.refresh()

    def apply_styles(self):
        css = b"""
        window { background-color: #1a1a2e; }
        label { color: #e0e0e0; }
        GtkBox { background-color: #1a1a2e; }
        GtkSeparator { background-color: #0f3460; min-height: 1px; }
        .card { background: #16213e; border-radius: 10px; }
        """
        p = Gtk.CssProvider()
        p.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), p, 600)

    def refresh(self):
        warp_ok = is_warp_connected()
        spoof_ok, _ = get_spoofdpi_status()
        proxy_ok = "active" in get_proxy_status()
        active = is_bypass_active()

        self.warp_card.update(
            get_warp_status(),
            "#2ecc71" if warp_ok else "#e74c3c",
            "Disconnect" if warp_ok else "Connect"
        )
        self.spoof_card.update(
            get_spoofdpi_status()[0],
            "#2ecc71" if spoof_ok else "#e74c3c",
            "Stop" if spoof_ok else "Start"
        )
        self.proxy_card.update(
            get_proxy_status(),
            "#2ecc71" if proxy_ok else "#e74c3c",
            "OFF" if proxy_ok else "ON"
        )

        self.btn_on.set_sensitive(not active)
        self.btn_off.set_sensitive(active)
        return True

    def on_warp(self):
        if is_warp_connected():
            run_cmd(["warp-cli", "disconnect"])
        else:
            run_cmd(["warp-cli", "connect"])
        self.refresh()

    def on_spoof(self):
        _, running = get_spoofdpi_status()
        if running:
            try:
                os.kill(int(open(PID_FILE).read().strip()), 9)
            except Exception:
                pass
            try:
                os.remove(PID_FILE)
            except Exception:
                pass
        else:
            run_cmd([SPOOFDPI_BIN, "--listen-addr", f"{PROXY_HOST}:{PROXY_PORT}",
                     "--dns-addr", "1.1.1.1:53", "--dns-cache", "--silent"])
        self.refresh()

    def on_proxy(self):
        if is_bypass_active():
            run_cmd([BYPASS_CLI, "off"])
        else:
            run_cmd([BYPASS_CLI, "on"])
        self.refresh()

    def on_bypass(self, action):
        run_cmd([BYPASS_CLI, action])
        self.refresh()


if __name__ == "__main__":
    win = CollegeBypassUI()
    win.show_all()
    Gtk.main()