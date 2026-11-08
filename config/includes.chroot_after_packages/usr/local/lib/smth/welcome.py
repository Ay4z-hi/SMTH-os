#!/usr/bin/env python3
"""SMTH Welcome: logo + spinner, then fade into the desktop."""
import math, os, sys, time
sys.path.insert(0, "/usr/local/lib/smth")
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, GLib, Gtk
from gi.repository import Gtk4LayerShell as LS
import smthdot as D
SHOW, FADE = 3.4, 0.7

def on_activate(app):
    win = Gtk.Window(application=app); win.set_decorated(False); win.add_css_class("welcome")
    LS.init_for_window(win); LS.set_namespace(win, "smth-welcome"); LS.set_layer(win, LS.Layer.OVERLAY)
    for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT): LS.set_anchor(win, e, True)
    LS.set_exclusive_zone(win, -1); LS.set_keyboard_mode(win, LS.KeyboardMode.NONE)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=26, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    logo = "/usr/share/smth/logo.png"
    if os.path.exists(logo):
        pic = Gtk.Picture.new_for_filename(logo); pic.set_can_shrink(False); box.append(pic)
    label = Gtk.Label(label="Welcome", css_classes=["wl"]); box.append(label)
    spin = Gtk.DrawingArea(); spin.set_content_width(70); spin.set_content_height(70); box.append(spin)
    t0 = time.time()
    def draw(_a, cr, w, h):
        head = (time.time() - t0) * 9 % 12
        for i in range(12):
            d = (head - i) % 12; a = max(0.12, 1 - d / 5.0); ang = i / 12 * D.TAU
            cr.set_source_rgb(*(D.ACCENT if i % 2 == 0 else D.VIOLET)); cr.arc(w / 2 + 26 * math.sin(ang), h / 2 - 26 * math.cos(ang), 3.8 * a, 0, D.TAU); cr.fill()
    spin.set_draw_func(draw)
    def tick(*_):
        t = time.time() - t0; spin.queue_draw()
        if t > SHOW: win.set_opacity(max(0.0, 1 - (t - SHOW) / FADE))
        if t > SHOW + FADE: win.close(); app.quit(); return False
        return True
    win.set_child(box); win.add_tick_callback(lambda w, c: tick() and GLib.SOURCE_CONTINUE)
    p = Gtk.CssProvider(); p.load_from_string("window.welcome { background: #000; } label.wl { color: #ffffff; font-size: 26px; font-weight: 300; letter-spacing: 3px; }")
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    win.present()
app = Gtk.Application(application_id="os.smth.Welcome"); app.connect("activate", on_activate); sys.exit(app.run(sys.argv))
