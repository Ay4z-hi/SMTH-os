#!/usr/bin/env python3
"""SMTH Launcher: start menu with search, pinned apps, all apps and power buttons. Run it again to close it."""
import subprocess, sys
sys.path.insert(0, "/usr/local/lib/smth")
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk
from gi.repository import Gtk4LayerShell as LS
import smthdot as D

PINNED = ["smth-files", "smth-browser", "smth-store", "smth-camera", "smth-gallery", "smth-paint", "smth-notes", "smth-calc", "smth-player", "smth-clock", "smth-terminal", "smth-settings"]
CSS = b"""
window.launcher { background: rgba(8,8,18,0.96); border: 1px solid rgba(124,92,255,0.5); border-radius: 26px; }
.launcher searchentry { border-radius: 999px; padding: 8px 14px; }
.launcher button.pin { border-radius: 18px; padding: 8px; background: transparent; }
.launcher button.pin:hover { background: rgba(124,92,255,0.18); }
.launcher list { background: transparent; }
.launcher row { border-radius: 14px; padding: 4px 8px; }
.launcher row:selected { background: rgba(25,230,208,0.20); }
.launcher label.cap { font-size: 11px; color: #cfd8ea; }
"""

class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="os.smth.Launcher"); self.win = None; self.was_active = False

    def do_activate(self):
        if self.win: self.quit(); return                       # second run = toggle closed
        win = self.win = Gtk.Window(application=self); win.set_decorated(False); win.add_css_class("launcher"); win.set_default_size(660, 720)
        LS.init_for_window(win); LS.set_namespace(win, "smth-launcher"); LS.set_layer(win, LS.Layer.OVERLAY)
        LS.set_anchor(win, LS.Edge.BOTTOM, True); LS.set_margin(win, LS.Edge.BOTTOM, 78); LS.set_keyboard_mode(win, LS.KeyboardMode.EXCLUSIVE)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=22, margin_bottom=18, margin_start=22, margin_end=22)
        root.append(D.dot_label("SMTH", 4)); self.entry = Gtk.SearchEntry(placeholder_text="Search apps", hexpand=True); root.append(self.entry)
        self.pin_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); self.pin_box.append(D.dot_label("PINNED", 2))
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6, min_children_per_line=4, row_spacing=4, column_spacing=4)
        for n in PINNED:
            info = Gio.DesktopAppInfo.new(n + ".desktop")
            if not info: continue
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4); img = Gtk.Image.new_from_gicon(info.get_icon()); img.set_pixel_size(44)
            box.append(img); box.append(Gtk.Label(label=info.get_name().replace("SMTH ", ""), css_classes=["cap"]))
            b = Gtk.Button(child=box, css_classes=["pin", "flat"]); b.connect("clicked", lambda _b, i=info: self.launch(i)); flow.append(b)
        self.pin_box.append(flow); root.append(self.pin_box); root.append(D.dot_label("ALL APPS", 2))
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, activate_on_single_click=True); self.rows = []
        for a in sorted([a for a in Gio.AppInfo.get_all() if a.should_show()], key=lambda a: a.get_name().lower()):
            if a.get_id() == "smth-launcher.desktop": continue
            row = Gtk.ListBoxRow(); row.info = a; row.key = a.get_name().lower()
            h = Gtk.Box(spacing=12, margin_top=4, margin_bottom=4); img = Gtk.Image.new_from_gicon(a.get_icon()); img.set_pixel_size(28)
            h.append(img); h.append(Gtk.Label(label=a.get_name(), xalign=0)); row.set_child(h); self.list.append(row); self.rows.append(row)
        self.list.connect("row-activated", lambda l, r: self.launch(r.info)); root.append(Gtk.ScrolledWindow(child=self.list, vexpand=True))
        foot = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        for label, cmd in (("LOCK", ["smth-lock"]), ("SIGN OUT", ["labwc", "--exit"]), ("RESTART", ["systemctl", "reboot"]), ("SHUT DOWN", ["systemctl", "poweroff"])):
            b = Gtk.Button(label=label, css_classes=["pill"]); b.connect("clicked", lambda _b, c=cmd: (subprocess.Popen(c), self.quit())); foot.append(b)
        root.append(foot); win.set_child(root)
        self.entry.connect("search-changed", self.filter)
        key = Gtk.EventControllerKey(); key.connect("key-pressed", self.on_key); win.add_controller(key)
        win.connect("notify::is-active", self.on_active)
        p = Gtk.CssProvider(); p.load_from_data(CSS); Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        win.present(); self.entry.grab_focus()

    def visible(self): return [r for r in self.rows if r.get_visible()]
    def filter(self, *_):
        q = self.entry.get_text().lower().strip()
        for r in self.rows: r.set_visible(q in r.key)
        self.pin_box.set_visible(not q); v = self.visible()
        if v and q: self.list.select_row(v[0])
    def on_key(self, c, val, code, st):
        v = self.visible(); cur = self.list.get_selected_row()
        if val == Gdk.KEY_Escape: self.quit(); return True
        if val in (Gdk.KEY_Down, Gdk.KEY_Up) and v:
            i = v.index(cur) if cur in v else -1; i = min(len(v) - 1, i + 1) if val == Gdk.KEY_Down else max(0, i - 1)
            self.list.select_row(v[i]); v[i].grab_focus(); self.entry.grab_focus(); return True
        if val in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and v: self.launch((cur if cur in v else v[0]).info); return True
        return False
    def on_active(self, w, _):
        if w.is_active(): self.was_active = True
        elif self.was_active: GLib.timeout_add(250, lambda: (self.quit() if not w.is_active() else None, False)[1])
    def launch(self, info):
        try: info.launch([], None)
        except GLib.Error: pass
        self.quit()

sys.exit(App().run(sys.argv))
