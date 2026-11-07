#!/usr/bin/env python3
"""SMTH Notify: org.freedesktop.Notifications server. Corner toasts + notification center (SIGUSR1 toggles, SIGUSR2 = do-not-disturb).
Also raises system alerts: Wi-Fi/Ethernet connect/disconnect, low battery, finished downloads."""
import glob, json, os, signal, subprocess, sys, time
sys.path.insert(0, "/usr/local/lib/smth")
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk
from gi.repository import Gtk4LayerShell as LS
import smthdot as D

HIST = os.path.expanduser("~/.local/share/smth/notifications.json"); os.makedirs(os.path.dirname(HIST), exist_ok=True)
XML = """<node><interface name="org.freedesktop.Notifications">
<method name="Notify"><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="as" direction="in"/><arg type="a{sv}" direction="in"/><arg type="i" direction="in"/><arg type="u" direction="out"/></method>
<method name="CloseNotification"><arg type="u" direction="in"/></method>
<method name="GetCapabilities"><arg type="as" direction="out"/></method>
<method name="GetServerInformation"><arg type="s" direction="out"/><arg type="s" direction="out"/><arg type="s" direction="out"/><arg type="s" direction="out"/></method>
<signal name="NotificationClosed"><arg type="u"/><arg type="u"/></signal></interface></node>"""
CSS = b"""
.toast { background: rgba(8,8,18,0.95); border: 1px solid rgba(124,92,255,0.5); border-radius: 18px; padding: 12px 14px; }
.toast.crit { border-color: #19E6D0; }
.toast .t { font-weight: 700; } .toast .b { color: #cfd8ea; font-size: 12px; } .toast .a { color: #8a93b8; font-size: 10px; }
window.center { background: rgba(8,8,18,0.97); border: 1px solid rgba(124,92,255,0.4); border-radius: 22px; }
"""

class Server(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="os.smth.Notifd"); self.nid = 0; self.cards = {}; self.dnd = False; self.conn = None
        try: self.hist = json.load(open(HIST))
        except Exception: self.hist = []

    def do_activate(self):
        self.hold(); prov = Gtk.CssProvider(); prov.load_from_data(CSS); Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.toast_win = Gtk.Window(application=self); self.toast_win.set_decorated(False); self.toast_win.add_css_class("toastwin")
        LS.init_for_window(self.toast_win); LS.set_namespace(self.toast_win, "smth-toast"); LS.set_layer(self.toast_win, LS.Layer.OVERLAY)
        LS.set_anchor(self.toast_win, LS.Edge.TOP, True); LS.set_anchor(self.toast_win, LS.Edge.RIGHT, True); LS.set_margin(self.toast_win, LS.Edge.TOP, 14); LS.set_margin(self.toast_win, LS.Edge.RIGHT, 14)
        LS.set_keyboard_mode(self.toast_win, LS.KeyboardMode.NONE); self.stack = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, width_request=340); self.toast_win.set_child(self.stack)
        self.center = Gtk.Window(application=self); self.center.set_decorated(False); self.center.add_css_class("center")
        LS.init_for_window(self.center); LS.set_namespace(self.center, "smth-center"); LS.set_layer(self.center, LS.Layer.OVERLAY)
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.RIGHT): LS.set_anchor(self.center, e, True)
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.RIGHT): LS.set_margin(self.center, e, 12)
        LS.set_keyboard_mode(self.center, LS.KeyboardMode.ON_DEMAND); self.center.set_default_size(380, 600); self.build_center()
        key = Gtk.EventControllerKey(); key.connect("key-pressed", lambda c, v, *_: (self.center.set_visible(False), True)[1] if v == Gdk.KEY_Escape else False); self.center.add_controller(key)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self.toggle); GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR2, self.toggle_dnd)
        Gio.bus_own_name(Gio.BusType.SESSION, "org.freedesktop.Notifications", Gio.BusNameOwnerFlags.REPLACE, self.on_bus, None, lambda c, n: print("lost D-Bus name", n))
        self.start_watchers()

    # ---- D-Bus ----
    def on_bus(self, conn, name):
        self.conn = conn; conn.register_object("/org/freedesktop/Notifications", Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0], self.on_call, None, None)
    def on_call(self, conn, sender, path, iface, method, params, inv):
        if method == "Notify":
            app, rid, icon, summary, body, actions, hints, timeout = params.unpack()
            urgent = hints.get("urgency", 1) == 2
            inv.return_value(GLib.Variant("(u)", (self.post(app, summary, body, rid, timeout, urgent),)))
        elif method == "CloseNotification": self.close(params.unpack()[0], 3); inv.return_value(None)
        elif method == "GetCapabilities": inv.return_value(GLib.Variant("(as)", (["body", "persistence"],)))
        else: inv.return_value(GLib.Variant("(ssss)", ("SMTH Notify", "SMTH", "0.1", "1.2")))
    def emit_closed(self, nid, reason):
        if self.conn: self.conn.emit_signal(None, "/org/freedesktop/Notifications", "org.freedesktop.Notifications", "NotificationClosed", GLib.Variant("(uu)", (nid, reason)))

    # ---- toasts + history ----
    def post(self, app, summary, body, rid=0, timeout=-1, urgent=False):
        if rid in self.cards: nid = rid
        else: self.nid += 1; nid = self.nid
        self.hist.insert(0, {"app": app or "System", "summary": summary, "body": body, "time": time.strftime("%H:%M")}); self.hist = self.hist[:200]
        try: json.dump(self.hist, open(HIST, "w"))
        except OSError: pass
        self.build_center()
        if not self.dnd:
            if nid in self.cards: self.stack.remove(self.cards[nid][0])
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, css_classes=["toast"] + (["crit"] if urgent else []))
            card.append(Gtk.Label(label=summary, xalign=0, wrap=True, css_classes=["t"]))
            if body: card.append(Gtk.Label(label=body, xalign=0, wrap=True, css_classes=["b"], max_width_chars=40))
            card.append(Gtk.Label(label=(app or "System").upper(), xalign=0, css_classes=["a"]))
            g = Gtk.GestureClick(); g.connect("released", lambda *_: self.close(nid, 2)); card.add_controller(g)
            ms = 10000 if urgent else (timeout if timeout and timeout > 0 else 5500)
            self.cards[nid] = (card, GLib.timeout_add(ms, lambda: (self.close(nid, 1), False)[1])); self.stack.prepend(card); self.toast_win.present()
        return nid
    def close(self, nid, reason):
        if nid not in self.cards: return
        card, tid = self.cards.pop(nid)
        self.stack.remove(card); self.emit_closed(nid, reason)
        if not self.cards: self.toast_win.set_visible(False)

    # ---- notification center ----
    def build_center(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        head = Gtk.Box(spacing=8); head.append(D.dot_label("ALERTS", 3)); sp = Gtk.Box(hexpand=True); head.append(sp)
        dnd = Gtk.ToggleButton(label="DND", active=self.dnd, css_classes=["pill"]); dnd.connect("toggled", lambda b: setattr(self, "dnd", b.get_active()))
        clr = Gtk.Button(label="CLEAR", css_classes=["pill"]); clr.connect("clicked", lambda *_: (self.hist.clear(), json.dump([], open(HIST, "w")), self.build_center()))
        head.append(dnd); head.append(clr); root.append(head); lst = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        for n in self.hist[:100]:
            b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=8, margin_bottom=8, margin_start=12, margin_end=12)
            b.append(Gtk.Label(label=n["summary"], xalign=0, wrap=True, css_classes=["heading"]))
            if n["body"]: b.append(Gtk.Label(label=n["body"], xalign=0, wrap=True, css_classes=["dim-label"]))
            b.append(Gtk.Label(label=f'{n["app"].upper()} · {n["time"]}', xalign=0, css_classes=["caption", "dim-label"])); lst.append(b)
        if not self.hist: lst.append(Gtk.Label(label="No notifications", margin_top=30, margin_bottom=30, css_classes=["dim-label"]))
        root.append(Gtk.ScrolledWindow(child=lst, vexpand=True)); self.center.set_child(root)
    def toggle(self): self.center.set_visible(not self.center.get_visible()); return True
    def toggle_dnd(self): self.dnd = not self.dnd; self.post("System", "Do not disturb " + ("on" if self.dnd else "off"), ""); return True

    # ---- system alerts ----
    def start_watchers(self):
        self.last = {}; self.bat_warned = 0
        def once(key, fn):
            if time.time() - self.last.get(key, 0) > 4: self.last[key] = time.time(); fn()
        try:
            proc = Gio.Subprocess.new(["nmcli", "monitor"], Gio.SubprocessFlags.STDOUT_PIPE); stream = Gio.DataInputStream.new(proc.get_stdout_pipe())
            def line(s, res):
                try: l, _ = s.read_line_finish_utf8(res)
                except GLib.Error: return
                if l is None: return
                dev, _, st = l.partition(": ")
                if dev.startswith("wl"):
                    if st.startswith("disconnected"): once("w0", lambda: self.post("Network", "Wi-Fi disconnected", ""))
                    elif st.startswith("connected"): once("w1", lambda: self.post("Network", "Wi-Fi connected", ""))
                elif dev.startswith(("en", "eth")):
                    if st.startswith("disconnected"): once("e0", lambda: self.post("Network", "Ethernet unplugged", ""))
                    elif st.startswith("connected"): once("e1", lambda: self.post("Network", "Ethernet connected", ""))
                s.read_line_async(0, None, line)
            stream.read_line_async(0, None, line)
        except GLib.Error: pass
        def battery():
            for d in glob.glob("/sys/class/power_supply/BAT*"):
                try: cap = int(open(d + "/capacity").read()); st = open(d + "/status").read().strip()
                except OSError: continue
                if st == "Discharging" and cap <= 5 and self.bat_warned < 2: self.bat_warned = 2; self.post("Power", "Battery critical: %d%%" % cap, "Plug in now", urgent=True)
                elif st == "Discharging" and cap <= 15 and self.bat_warned < 1: self.bat_warned = 1; self.post("Power", "Low battery: %d%%" % cap, "Connect the charger")
                elif st != "Discharging": self.bat_warned = 0
            return True
        GLib.timeout_add_seconds(60, battery)
        dl = os.path.expanduser("~/Downloads"); os.makedirs(dl, exist_ok=True)
        try:
            self.mon = Gio.File.new_for_path(dl).monitor_directory(Gio.FileMonitorFlags.NONE, None)
            self.mon.connect("changed", lambda m, f, o, ev: (ev == Gio.FileMonitorEvent.CHANGES_DONE_HINT and not f.get_basename().endswith((".part", ".crdownload", ".download", ".tmp")) and self.post("Downloads", "Downloaded", f.get_basename())) or None)
        except GLib.Error: pass

sys.exit(Server().run(sys.argv))
