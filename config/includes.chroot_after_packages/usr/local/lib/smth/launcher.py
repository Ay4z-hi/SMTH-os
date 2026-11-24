#!/usr/bin/env python3
"""SMTH Launcher: the Start menu.

A restrained glass panel with search, pinned apps, the full application list and
real session controls. Run it again (or press Escape) to close it.
"""
import subprocess, sys
sys.path.insert(0, "/usr/local/lib/smth")
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk
from gi.repository import Gtk4LayerShell as LS
import smthdot as D

PINNED = ["smth-files", "smth-browser", "smth-store", "smth-camera", "smth-gallery", "smth-paint",
          "smth-notes", "smth-calc", "smth-player", "smth-clock", "smth-orbit", "smth-terminal", "smth-settings", "smth-ahian"]

CSS = b"""
window.launcher {
  background-color: transparent;
  background-image: radial-gradient(ellipse at 12% -8%, alpha(#701b35, 0.42), transparent 56%),
                    linear-gradient(168deg, alpha(#f2c6d2, 0.10), alpha(#f2c6d2, 0.035) 38%, alpha(#701b35, 0.14));
  border: 1px solid alpha(#f2c6d2, 0.20);
  border-radius: 24px;
  box-shadow: inset 0 1px 0 alpha(#ffffff, 0.12), 0 26px 60px alpha(#000000, 0.60);
  color: #f2c6d2;
}
.launcher label { color: #f2c6d2; }
.launcher .head { color: alpha(#f2c6d2, 0.52); font-size: 10px; letter-spacing: 2px; }
.launcher searchentry {
  border-radius: 999px; padding: 5px 16px; min-height: 30px;
  background-image: linear-gradient(180deg, alpha(#f2c6d2, 0.09), alpha(#f2c6d2, 0.03));
  border: 1px solid alpha(#f2c6d2, 0.16); color: #f2c6d2;
  box-shadow: inset 0 1px 3px alpha(#000000, 0.30), inset 0 1px 0 alpha(#ffffff, 0.06);
}
.launcher searchentry:focus-within {
  border-color: alpha(#f2c6d2, 0.48);
  background-image: linear-gradient(180deg, alpha(#701b35, 0.34), alpha(#f2c6d2, 0.035));
  box-shadow: inset 0 1px 3px alpha(#000000, 0.30), 0 0 0 2px alpha(#701b35, 0.45);
}
.launcher button.pin {
  border-radius: 14px; padding: 4px;
  background-image: linear-gradient(170deg, alpha(#f2c6d2, 0.085), alpha(#f2c6d2, 0.02));
  border: 1px solid alpha(#f2c6d2, 0.12); box-shadow: inset 0 1px 0 alpha(#ffffff, 0.07);
  min-width: 52px; min-height: 50px;
}
.launcher button.pin:hover { background-image: linear-gradient(170deg, alpha(#f2c6d2, 0.16), alpha(#701b35, 0.22)); border-color: alpha(#f2c6d2, 0.26); }
.launcher button.pin:active { background-image: linear-gradient(170deg, alpha(#701b35, 0.55), alpha(#701b35, 0.30)); }
.launcher list { background: transparent; }
.launcher row { border-radius: 12px; padding: 3px 8px; }
.launcher row:hover { background-color: alpha(#f2c6d2, 0.075); }
.launcher row:selected { background-image: linear-gradient(180deg, alpha(#f2c6d2, 0.16), alpha(#701b35, 0.52)); }
.launcher label.cap { font-size: 10px; color: #f2c6d2; }
.launcher button.pill {
  border-radius: 999px; padding: 5px 14px;
  background-image: linear-gradient(180deg, alpha(#f2c6d2, 0.095), alpha(#f2c6d2, 0.03));
  border: 1px solid alpha(#f2c6d2, 0.15); color: #f2c6d2; font-size: 10px; letter-spacing: 1px;
}
.launcher button.pill:hover { background-image: linear-gradient(180deg, alpha(#f2c6d2, 0.17), alpha(#701b35, 0.40)); border-color: alpha(#f2c6d2, 0.28); }
"""


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="os.smth.Launcher"); self.win = None; self.was_active = False

    def do_activate(self):
        if self.win: self.quit(); return                       # second run = toggle closed
        win = self.win = Gtk.Window(application=self); win.set_decorated(False)
        win.add_css_class("launcher"); win.set_default_size(560, 620)
        LS.init_for_window(win); LS.set_namespace(win, "smth-launcher"); LS.set_layer(win, LS.Layer.OVERLAY)
        LS.set_anchor(win, LS.Edge.BOTTOM, True); LS.set_margin(win, LS.Edge.BOTTOM, 58)
        LS.set_keyboard_mode(win, LS.KeyboardMode.EXCLUSIVE)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       margin_top=16, margin_bottom=14, margin_start=18, margin_end=18)
        head = Gtk.Box(spacing=8)
        logo = D.dot_label("SMTH", 4, on=D.BLUSH)
        head.append(logo)
        click = Gtk.GestureClick()
        click.connect("pressed", lambda *_: self.entry.grab_focus())
        logo.add_controller(click)
        spacer = Gtk.Box(hexpand=True); head.append(spacer)
        head.append(Gtk.Label(label="START", css_classes=["head"]))
        root.append(head)
        self.entry = Gtk.SearchEntry(placeholder_text="Search applications", hexpand=True)
        root.append(self.entry)

        self.pin_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.pin_box.append(Gtk.Label(label="PINNED", css_classes=["head"], xalign=0))
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6,
                           min_children_per_line=6, row_spacing=2, column_spacing=2, homogeneous=True)
        for n in PINNED:
            info = Gio.DesktopAppInfo.new(n + ".desktop")
            if not info: continue
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            img = Gtk.Image.new_from_gicon(info.get_icon()); img.set_pixel_size(20)
            box.append(img)
            box.append(Gtk.Label(label=info.get_name().replace("SMTH ", ""), css_classes=["cap"],
                                 ellipsize=3, max_width_chars=8))
            b = Gtk.Button(child=box, css_classes=["pin", "flat"]); b.set_tooltip_text(info.get_name())
            b.set_size_request(56, 54)
            b.connect("clicked", lambda _b, i=info: self.launch(i)); flow.append(b)
        self.pin_box.append(flow); root.append(self.pin_box)

        root.append(Gtk.Label(label="ALL APPLICATIONS", css_classes=["head"], xalign=0))
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, activate_on_single_click=True)
        self.list.add_css_class("apps")
        self.rows = []
        for a in sorted([a for a in Gio.AppInfo.get_all() if a.should_show()], key=lambda a: a.get_name().lower()):
            if a.get_id() == "smth-launcher.desktop": continue
            row = Gtk.ListBoxRow(); row.info = a; row.key = a.get_name().lower()
            h = Gtk.Box(spacing=10, margin_top=1, margin_bottom=1)
            img = Gtk.Image.new_from_gicon(a.get_icon()); img.set_pixel_size(18)
            h.append(img); h.append(Gtk.Label(label=a.get_name(), xalign=0, css_classes=["cap"]))
            row.set_child(h); self.list.append(row); self.rows.append(row)
        self.list.connect("row-activated", lambda l, r: self.launch(r.info))
        root.append(Gtk.ScrolledWindow(child=self.list, vexpand=True))
        foot = Gtk.Box(spacing=6, halign=Gtk.Align.END)
        for label, cmd in (("SETTINGS", ["smth-settings"]), ("LOCK", ["smth-lock"]),
                           ("SIGN OUT", ["labwc", "--exit"]), ("RESTART", ["systemctl", "reboot"]),
                           ("SHUT DOWN", ["systemctl", "poweroff"])):
            b = Gtk.Button(label=label, css_classes=["pill"]); b.connect("clicked", lambda _b, c=cmd: (subprocess.Popen(c), self.quit()))
            foot.append(b)
        root.append(foot); win.set_child(root)
        self.entry.connect("search-changed", self.filter)
        key = Gtk.EventControllerKey(); key.connect("key-pressed", self.on_key); win.add_controller(key)
        win.connect("notify::is-active", self.on_active)
        p = Gtk.CssProvider(); p.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
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
            i = v.index(cur) if cur in v else -1
            i = min(len(v) - 1, i + 1) if val == Gdk.KEY_Down else max(0, i - 1)
            self.list.select_row(v[i]); v[i].grab_focus(); self.entry.grab_focus(); return True
        if val in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and v:
            self.launch((cur if cur in v else v[0]).info); return True
        return False

    def on_active(self, w, _):
        if w.is_active(): self.was_active = True
        elif self.was_active: GLib.timeout_add(250, lambda: (self.quit() if not w.is_active() else None, False)[1])

    def launch(self, info):
        try:
            info.launch([], None)
        except Exception as exc:  # GLib.Error and any launch failure
            print(f"smth-launcher: failed to launch {info.get_id()}: {exc}", file=sys.stderr)
        self.quit()


sys.exit(App().run(sys.argv))
