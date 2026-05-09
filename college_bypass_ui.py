#!/usr/bin/env python3
import subprocess
import threading
import gi
import os

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8080
PID_FILE = "/tmp/spoofdpi.pid"
SPOOFDPI_BIN = "/usr/lib/college-bypass/spoofdpi"


def log(msg):
    import datetime
    with open("/tmp/college_bypass_ui.log", "a") as f:
        f.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")

log("--- started ---")


def detect_de():
    de = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if "KDE" in de or "plasma" in de:
        return "kde"
    if "GNOME" in de or "Unity" in de or "Cinnamon" in de:
        return "gnome"
    if "XFCE" in de:
        return "xfce"
    return "unknown"


def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        log(f"CMD: {' '.join(cmd)} -> {r.returncode}")
        return r
    except Exception as e:
        log(f"CMD EXCEPTION: {' '.join(cmd)} -> {e}")
        return None


# ── Service helpers ────────────────────────────────────────────────────────────

def get_warp_status():
    r = run_cmd(["warp-cli", "status"])
    if r and r.stdout.strip():
        return r.stdout.split("\n")[0].strip()
    return "not installed"


def is_warp_connected():
    # Must match "connected" but NOT "disconnected" or "connecting"
    return get_warp_status().lower().startswith("status update: connected")


def get_spoofdpi_status():
    """Returns (text, is_running)."""
    if os.path.isfile(PID_FILE):
        try:
            pid = int(open(PID_FILE).read().strip())
            os.kill(pid, 0)
            return f"running (pid {pid})", True
        except (ValueError, OSError):
            pass
    return "stopped", False


def start_spoofdpi():
    """Launch SpoofDPI as a background daemon. Returns True when port is ready."""
    stop_spoofdpi()
    try:
        log_fh = open("/tmp/spoofdpi.log", "a")
        proc = subprocess.Popen(
            [SPOOFDPI_BIN,
             "--listen-addr", f"{PROXY_HOST}:{PROXY_PORT}",
             "--dns-addr", "1.1.1.1:53",
             "--dns-cache",
             "--silent"],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))
        log(f"SpoofDPI started (pid {proc.pid})")
    except Exception as e:
        log(f"Failed to start SpoofDPI: {e}")
        return False

    import time
    for _ in range(17):
        time.sleep(0.3)
        r = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True)
        if f":{PROXY_PORT} " in r.stdout:
            log("SpoofDPI port ready")
            return True
    log("SpoofDPI port did not open in time")
    return False


def stop_spoofdpi():
    """Kill SpoofDPI and clean up PID file."""
    if os.path.isfile(PID_FILE):
        try:
            pid = int(open(PID_FILE).read().strip())
            os.kill(pid, 9)
            log(f"Killed SpoofDPI (pid {pid})")
        except Exception:
            pass
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
    subprocess.run(["pkill", "-x", "spoofdpi"], capture_output=True)


def get_proxy_status():
    """Returns (text, is_active)."""
    de = detect_de()
    if de in ("gnome", "xfce"):
        r = run_cmd(["gsettings", "get", "org.gnome.system.proxy", "mode"])
        if r:
            mode = r.stdout.strip().strip("'")
            if mode == "manual":
                h = run_cmd(["gsettings", "get", "org.gnome.system.proxy.http", "host"])
                p = run_cmd(["gsettings", "get", "org.gnome.system.proxy.http", "port"])
                host_val = h.stdout.strip().strip("'") if h else ""
                port_val = p.stdout.strip() if p else ""
                return f"active  ->  {host_val}:{port_val}", True
        return "inactive", False
    if de == "kde":
        r = run_cmd(["kreadconfig5", "--file", "kioslaverc",
                     "--group", "Proxy Settings", "--key", "ProxyType"])
        if r and r.stdout.strip() == "1":
            return f"active  ->  {PROXY_HOST}:{PROXY_PORT}", True
        return "inactive", False
    return "inactive", False


def enable_proxy():
    de = detect_de()
    if de in ("gnome", "xfce"):
        run_cmd(["gsettings", "set", "org.gnome.system.proxy", "mode", "manual"])
        run_cmd(["gsettings", "set", "org.gnome.system.proxy.http", "host", PROXY_HOST])
        run_cmd(["gsettings", "set", "org.gnome.system.proxy.http", "port", str(PROXY_PORT)])
        run_cmd(["gsettings", "set", "org.gnome.system.proxy.https", "host", PROXY_HOST])
        run_cmd(["gsettings", "set", "org.gnome.system.proxy.https", "port", str(PROXY_PORT)])
        run_cmd(["gsettings", "set", "org.gnome.system.proxy", "ignore-hosts",
                 "['localhost', '127.0.0.0/8', '::1']"])
    elif de == "kde":
        run_cmd(["kwriteconfig5", "--file", "kioslaverc",
                 "--group", "Proxy Settings", "--key", "ProxyType", "1"])
        run_cmd(["kwriteconfig5", "--file", "kioslaverc",
                 "--group", "Proxy Settings", "--key",
                 "httpProxy", f"http://{PROXY_HOST} {PROXY_PORT}"])
        run_cmd(["kwriteconfig5", "--file", "kioslaverc",
                 "--group", "Proxy Settings", "--key",
                 "httpsProxy", f"http://{PROXY_HOST} {PROXY_PORT}"])
        run_cmd(["dbus-send", "--session", "--type=signal", "/KIO/Scheduler",
                 "org.kde.KIO.Scheduler.reparseSlaveConfiguration", "string:''"])
    log("proxy enabled")


def disable_proxy():
    de = detect_de()
    if de in ("gnome", "xfce"):
        run_cmd(["gsettings", "set", "org.gnome.system.proxy", "mode", "none"])
    elif de == "kde":
        run_cmd(["kwriteconfig5", "--file", "kioslaverc",
                 "--group", "Proxy Settings", "--key", "ProxyType", "0"])
        run_cmd(["dbus-send", "--session", "--type=signal", "/KIO/Scheduler",
                 "org.kde.KIO.Scheduler.reparseSlaveConfiguration", "string:''"])
    log("proxy disabled")


# ── UI Components ──────────────────────────────────────────────────────────────

class StatusCard(Gtk.Box):
    def __init__(self, label, on_click):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.CENTER)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

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
        self.btn.set_size_request(90, 32)
        self.btn.connect("clicked", on_click)
        self.pack_start(self.btn, False, False, 0)

    def update(self, value, dot_color, btn_label):
        self.val.set_text(value)
        self.dot.set_markup(f"<span color='{dot_color}' size='16000'>●</span>")
        self.btn.set_label(btn_label)


class CollegeBypassUI(Gtk.Window):
    def __init__(self):
        super().__init__(title="College Bypass")
        self.set_default_size(480, 440)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        self.connect("destroy", Gtk.main_quit)

        # Prevents concurrent button operations
        self._busy = False

        self._apply_styles()
        self._build_ui()

        # Start background refresh loop
        GLib.timeout_add(2000, self._schedule_refresh)
        self._schedule_refresh()

    def _build_ui(self):
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
        title_box.pack_start(sub, False, False, 0)

        status_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        status_container.set_margin_start(24)
        status_container.set_margin_end(24)
        box.pack_start(status_container, True, True, 0)

        self.warp_card = StatusCard("WARP", self._on_warp_clicked)
        status_container.pack_start(self.warp_card, False, False, 0)

        sep1 = Gtk.Separator()
        sep1.set_margin_top(6)
        sep1.set_margin_bottom(6)
        status_container.pack_start(sep1, False, False, 0)

        self.spoof_card = StatusCard("SpoofDPI", self._on_spoof_clicked)
        status_container.pack_start(self.spoof_card, False, False, 0)

        sep2 = Gtk.Separator()
        sep2.set_margin_top(6)
        sep2.set_margin_bottom(6)
        status_container.pack_start(sep2, False, False, 0)

        self.proxy_card = StatusCard("Proxy", self._on_proxy_clicked)
        status_container.pack_start(self.proxy_card, False, False, 0)

        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        footer_box.set_margin_top(16)
        footer_box.set_margin_bottom(24)
        footer_box.set_halign(Gtk.Align.CENTER)
        box.pack_start(footer_box, False, False, 0)

        self.btn_on = Gtk.Button(label="Bypass ON")
        self.btn_on.set_size_request(130, 44)
        self.btn_on.connect("clicked", lambda _: self._on_bypass("on"))
        footer_box.pack_start(self.btn_on, False, False, 0)

        self.btn_off = Gtk.Button(label="Bypass OFF")
        self.btn_off.set_size_request(130, 44)
        self.btn_off.connect("clicked", lambda _: self._on_bypass("off"))
        footer_box.pack_start(self.btn_off, False, False, 0)

    def _apply_styles(self):
        css = b"""
        window { background-color: #1a1a2e; }
        label { color: #e0e0e0; }
        GtkBox { background-color: #1a1a2e; }
        GtkSeparator { background-color: #0f3460; }
        button {
            background: #16213e;
            color: #e0e0e0;
            border-radius: 6px;
            border: 1px solid #0f3460;
            padding: 6px 12px;
        }
        button:hover { background: #1f2f52; }
        button:disabled { color: #555; background: #111827; }
        """
        p = Gtk.CssProvider()
        p.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), p, 600)

    def _set_all_buttons_sensitive(self, sensitive):
        self.btn_on.set_sensitive(sensitive)
        self.btn_off.set_sensitive(sensitive)
        self.warp_card.btn.set_sensitive(sensitive)
        self.spoof_card.btn.set_sensitive(sensitive)
        self.proxy_card.btn.set_sensitive(sensitive)

    # ── Refresh (background thread → GLib.idle_add → main thread) ─────────────

    def _schedule_refresh(self):
        """Timer callback: spawn a background status-fetch thread."""
        threading.Thread(target=self._fetch_status, daemon=True).start()
        return GLib.SOURCE_CONTINUE  # keep repeating every 2 s

    def _fetch_status(self):
        """Background thread: gather all status values, then hand off to UI."""
        warp_text = get_warp_status()
        warp_ok = warp_text.lower().startswith("status update: connected")
        spoof_text, spoof_ok = get_spoofdpi_status()
        proxy_text, proxy_ok = get_proxy_status()
        GLib.idle_add(self._apply_status, warp_text, warp_ok,
                      spoof_text, spoof_ok, proxy_text, proxy_ok)

    def _apply_status(self, warp_text, warp_ok, spoof_text, spoof_ok, proxy_text, proxy_ok):
        """Main thread: push fetched status into widgets."""
        if self._busy:
            return GLib.SOURCE_REMOVE

        self.warp_card.update(
            warp_text,
            "#2ecc71" if warp_ok else "#e74c3c",
            "Disconnect" if warp_ok else "Connect",
        )
        self.spoof_card.update(
            spoof_text,
            "#2ecc71" if spoof_ok else "#e74c3c",
            "Stop" if spoof_ok else "Start",
        )
        self.proxy_card.update(
            proxy_text,
            "#2ecc71" if proxy_ok else "#e74c3c",
            "Disable" if proxy_ok else "Enable",
        )

        # Bypass ON = both spoofdpi running AND proxy active
        active = spoof_ok and proxy_ok
        self.btn_on.set_sensitive(not active)
        self.btn_off.set_sensitive(active)
        return GLib.SOURCE_REMOVE

    # ── Button action runner ───────────────────────────────────────────────────

    def _run_in_bg(self, fn):
        """Disable all buttons, run fn in a background thread, then refresh."""
        if self._busy:
            return
        self._busy = True
        self._set_all_buttons_sensitive(False)

        def wrapper():
            try:
                fn()
            finally:
                self._busy = False
                # Refresh status and re-enable buttons
                self._fetch_status()
                GLib.idle_add(self._set_all_buttons_sensitive, True)

        threading.Thread(target=wrapper, daemon=True).start()

    # ── Button handlers ────────────────────────────────────────────────────────

    def _on_warp_clicked(self, _):
        def action():
            if is_warp_connected():
                log("Disconnecting WARP")
                run_cmd(["warp-cli", "disconnect"])
            else:
                log("Connecting WARP")
                run_cmd(["warp-cli", "connect"])
        self._run_in_bg(action)

    def _on_spoof_clicked(self, _):
        def action():
            _, running = get_spoofdpi_status()
            if running:
                log("Stopping SpoofDPI")
                stop_spoofdpi()
            else:
                log("Starting SpoofDPI")
                start_spoofdpi()
        self._run_in_bg(action)

    def _on_proxy_clicked(self, _):
        def action():
            _, proxy_ok = get_proxy_status()
            if proxy_ok:
                log("Disabling proxy")
                disable_proxy()
            else:
                log("Enabling proxy")
                enable_proxy()
        self._run_in_bg(action)

    def _on_bypass(self, action):
        def do_on():
            log("Bypass ON")
            _, running = get_spoofdpi_status()
            if not running:
                ok = start_spoofdpi()
                if not ok:
                    log("SpoofDPI failed to start — not enabling proxy")
                    return
            enable_proxy()

        def do_off():
            log("Bypass OFF")
            disable_proxy()
            stop_spoofdpi()

        self._run_in_bg(do_on if action == "on" else do_off)


if __name__ == "__main__":
    win = CollegeBypassUI()
    win.show_all()
    Gtk.main()
