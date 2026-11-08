#!/usr/bin/env python3
"""SMTH Home: wallpaper, desktop icons, clock, glance rings. `ahian` switches on the live black-hole scene."""
import colorsys, datetime, glob, math, os, random, signal, sys, time
sys.path.insert(0, "/usr/local/lib/smth")
import cairo
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Gdk", "4.0"); gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk
from gi.repository import Gtk4LayerShell as LS
import smthdot as D

FLAG = os.path.expanduser("~/.config/smth/ahian")
WALL = "/usr/share/backgrounds/smth/wallpaper.png"
APPS = ["smth-files", "smth-browser", "smth-store", "smth-camera", "smth-gallery", "smth-paint", "smth-notes",
        "smth-calc", "smth-player", "smth-clock", "smth-terminal", "smth-settings"]
GOLD = math.pi * (3 - math.sqrt(5)); TAU = math.tau
HOT, CY, VI = (0.92, 1.0, 1.0), D.ACCENT, D.VIOLET

def wall_path():
    try:
        w = open(os.path.expanduser("~/.config/smth/wallpaper")).read().strip()
        if os.path.exists(w): return w
    except OSError: pass
    return WALL

class S:
    ahian = False; t0 = time.time(); mx = 0.5; my = 0.5; timer = 0; animated = []
def T(): return time.time() - S.t0

CSS = b"""
window.home { background: #000; }
.home button.app { border-radius: 20px; padding: 8px 10px; background: transparent; border: 1px solid transparent; }
.home button.app:hover { background: rgba(12,12,26,0.85); border-color: rgba(25,230,208,0.45); }
.home button.app:active { border-color: #7C5CFF; }
.home label.cap { color: #d7e3ef; font-size: 11px; }
.home .glance { background: rgba(8,8,18,0.55); border-radius: 26px; border: 1px solid rgba(124,92,255,0.25); padding: 10px 14px; }
@keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-9px); } 100% { transform: translateY(0px); } }
window.home.ahian button.app { animation: float 3.2s ease-in-out infinite; border: 1px solid rgba(25,230,208,0.35); background: rgba(8,8,24,0.55); box-shadow: 0 0 20px rgba(124,92,255,0.4); }
window.home.ahian flowboxchild:nth-child(2n) button.app { animation-delay: 0.8s; }
window.home.ahian flowboxchild:nth-child(3n) button.app { animation-delay: 1.6s; }
window.home.ahian button.app image { -gtk-icon-shadow: 0 0 14px rgba(25,230,208,0.85); }
window.home.ahian .glance { border-color: rgba(25,230,208,0.55); box-shadow: 0 0 24px rgba(25,230,208,0.25); }
"""

class Stats:
    def __init__(self): self.prev = self._raw()
    def _raw(self):
        v = list(map(int, open("/proc/stat").readline().split()[1:])); return sum(v), v[3] + v[4]
    def cpu(self):
        t, i = self._raw(); pt, pi = self.prev; self.prev = (t, i); return 0.0 if t == pt else 1 - (i - pi) / (t - pt)
    def mem(self):
        m = {}
        for l in open("/proc/meminfo"): k, v = l.split(":"); m[k] = int(v.split()[0])
        return 1 - m["MemAvailable"] / m["MemTotal"]
    def disk(self): s = os.statvfs("/"); return 1 - s.f_bavail / s.f_blocks
    def bat(self):
        for p in glob.glob("/sys/class/power_supply/BAT*/capacity"): return int(open(p).read()) / 100
        return None

def palette(shift):
    out = []
    for i in range(64):
        t = i / 63; c = D.lerp(HOT, CY, t / 0.22) if t < 0.22 else D.lerp(CY, VI, (t - 0.22) / 0.78)
        if shift:
            h, s, v = colorsys.rgb_to_hsv(*c); c = colorsys.hsv_to_rgb((h + shift) % 1, max(s, 0.55), v)
        out.append(c)
    return out

class BlackHole:
    def __init__(self):
        rng = random.Random(5)
        self.disk = [(1.45 + 2.95 * math.sqrt((i + 0.5) / 700), i * GOLD) for i in range(700)]
        self.stars = [(rng.random(), rng.random(), rng.random()) for _ in range(150)]
    def draw(self, cr, w, h, t, mx, my):
        sc = h / 1080; cx, cy, R = w * 0.66, h * 0.5, h * 0.105
        cr.set_source_rgb(0, 0, 0); cr.paint()
        buckets = [[], [], [], []]
        for sx, sy, sd in self.stars:
            x = (sx * w + (mx - 0.5) * 46 * sd) % w; y = (sy * h + (my - 0.5) * 26 * sd) % h
            buckets[int((math.sin(t * 1.7 + sx * 40) * 0.5 + 0.5) * 3.99)].append((x, y, 0.7 + 1.4 * sd))
        for k, lst in enumerate(buckets):
            cr.set_source_rgba(0.85, 0.93, 1.0, 0.22 + 0.2 * k)
            for x, y, r in lst: cr.new_sub_path(); cr.arc(x, y, r * sc, 0, TAU)
            cr.fill()
        g = cairo.RadialGradient(cx, cy, R, cx, cy, R * 5.5); g.add_color_stop_rgba(0, 0.3, 0.15, 0.9, 0.38); g.add_color_stop_rgba(1, 0, 0, 0, 0)
        cr.set_source(g); cr.paint()
        cs, sn, tilt = math.cos(-0.22), math.sin(-0.22), 0.27
        bk = [[], []]
        for i, (rr, a0) in enumerate(self.disk):
            a = a0 + 0.55 * (1.45 / rr) ** 1.5 * t                  # Keplerian: inner dots orbit faster
            r = rr * R; x = r * math.cos(a); s = math.sin(a)
            y = r * s * tilt if s >= 0 else -math.sqrt(max(0.0, r * r - x * x)) * 0.93
            tr = (rr - 1.45) / 2.95; b = 0.62 - 0.38 * math.cos(a)
            bk[(i + int(math.floor(tr * 9 - t * 1.4))) % 2].append((cx + x * cs - y * sn, cy + x * sn + y * cs, (1.0 + 3.4 * b * (1 - 0.55 * tr)) * sc * 0.9))
        for i, lst in enumerate(bk):
            if not lst: continue
            cr.set_source_rgba(*(CY, VI)[i], 0.95)
            for X, Y, r in lst: cr.new_sub_path(); cr.arc(X, Y, r, 0, TAU)
            cr.fill()
        cr.set_source_rgb(0, 0, 0); cr.arc(cx, cy, R, 0, TAU); cr.fill()
        pulse = 0.65 + 0.35 * math.sin(t * 2.2)
        cr.set_source_rgba(0.1, 0.9, 0.8, 0.16 * pulse); cr.set_line_width(9 * sc); cr.arc(cx, cy, R * 1.08, 0, TAU); cr.stroke()
        cr.set_source_rgba(0.85, 1, 0.98, 0.5 + 0.5 * pulse); cr.set_line_width(2 * sc); cr.arc(cx, cy, R * 1.08, 0, TAU); cr.stroke()
        ph = t % 8.0                                                  # shooting star
        if ph < 0.9:
            u = ph / 0.9
            for k in range(16):
                p = max(0, u - k * 0.014); cr.set_source_rgba(0.8, 1, 1, (1 - k / 16) * (1 - u * 0.6))
                cr.arc(w * 0.08 + p * w * 0.55, h * 0.1 + p * h * 0.22, (2.6 - k * 0.12) * sc, 0, TAU); cr.fill()

def neon_text(cr, text, x, y, dot, t):
    for i, ch in enumerate(text):
        rows = D.GLYPHS.get(ch, D.GLYPHS[" "])
        for r in range(7):
            for c in range(5):
                px, py = x + (i * 6 + c) * dot + dot / 2, y + r * dot + dot / 2
                if (rows[r] >> (4 - c)) & 1:
                    col = CY if (i * 6 + c + int(t * 3)) % 2 == 0 else VI
                    cr.set_source_rgba(*col, 0.2); cr.arc(px, py, dot * 0.78, 0, TAU); cr.fill()
                    cr.set_source_rgb(*col); cr.arc(px, py, dot * 0.4, 0, TAU); cr.fill()
                else:
                    cr.set_source_rgb(0.09, 0.09, 0.14); cr.arc(px, py, dot * 0.3, 0, TAU); cr.fill()

def clock_widget():
    a = Gtk.DrawingArea(); dot = 11; a.set_content_width(int(D.text_width("00:00", dot)) + 4); a.set_content_height(dot * 7 + 4)
    def draw(_a, cr, w, h):
        txt = datetime.datetime.now().strftime("%H:%M")
        neon_text(cr, txt, 0, 0, dot, T()) if S.ahian else D.draw_text(cr, txt, 0, 0, dot)
    a.set_draw_func(draw); S.animated.append(a); GLib.timeout_add_seconds(1, lambda: (a.queue_draw(), True)[1]); return a

def date_widget():
    a = Gtk.DrawingArea(); dot = 3.6; a.set_content_width(int(D.text_width("WED 28 OCT", dot)) + 4); a.set_content_height(int(dot * 7) + 2)
    a.set_draw_func(lambda _a, cr, w, h: D.draw_text(cr, datetime.datetime.now().strftime("%a %d %b"), 0, 0, dot, on=(0.8, 0.86, 0.95), off=None)); return a

def ring(label, getter):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4); a = Gtk.DrawingArea(); a.set_content_width(110); a.set_content_height(110); st = {"v": 0.0}
    def draw(_a, cr, w, h):
        D.dot_ring(cr, w / 2, h / 2, 44, st["v"], phase=(T() * 0.6 if S.ahian else 0.0), neon=S.ahian)
        txt = "%d" % round(st["v"] * 100); D.draw_text(cr, txt, w / 2 - D.text_width(txt, 3) / 2, h / 2 - 10.5, 3, off=None)
    a.set_draw_func(draw); S.animated.append(a)
    def tick(): v = getter(); st["v"] = 0.0 if v is None else v; a.queue_draw(); return True
    GLib.timeout_add_seconds(2, tick); tick()
    box.append(a); box.append(Gtk.Label(label=label, css_classes=["cap"])); return box

def icon_button(name):
    info = Gio.DesktopAppInfo.new(name + ".desktop")
    if not info: return None
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6); img = Gtk.Image.new_from_gicon(info.get_icon()); img.set_pixel_size(56)
    box.append(img); box.append(Gtk.Label(label=info.get_name().replace("SMTH ", ""), css_classes=["cap"]))
    b = Gtk.Button(child=box); b.add_css_class("app"); b.add_css_class("flat"); b.connect("clicked", lambda *_: info.launch([], None)); return b

def on_activate(app):
    win = Gtk.Window(application=app); win.add_css_class("home"); win.set_decorated(False)
    LS.init_for_window(win); LS.set_namespace(win, "smth-home"); LS.set_layer(win, LS.Layer.BACKGROUND)
    for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT): LS.set_anchor(win, e, True)
    LS.set_exclusive_zone(win, -1); LS.set_keyboard_mode(win, LS.KeyboardMode.NONE)
    overlay = Gtk.Overlay(); pic = Gtk.Picture.new_for_filename(wall_path())
    pic.set_content_fit(Gtk.ContentFit.COVER); overlay.set_child(pic)
    bh = BlackHole(); live = Gtk.DrawingArea(); live.set_visible(False); live.set_can_target(False)
    live.set_draw_func(lambda _a, cr, w, h: bh.draw(cr, w, h, T(), S.mx, S.my)); overlay.add_overlay(live)
    icons = Gtk.FlowBox(orientation=Gtk.Orientation.VERTICAL, selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6, min_children_per_line=3,
                        halign=Gtk.Align.START, valign=Gtk.Align.START, margin_start=44, margin_top=44, row_spacing=6, column_spacing=6)
    for n in APPS:
        b = icon_button(n)
        if b: icons.append(b)
    overlay.add_overlay(icons)
    col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20, halign=Gtk.Align.START, valign=Gtk.Align.END, margin_start=70, margin_bottom=140)
    col.append(clock_widget()); col.append(date_widget()); st = Stats()
    gl = Gtk.Box(spacing=8, css_classes=["glance"], halign=Gtk.Align.START)
    gl.append(ring("CPU", st.cpu)); gl.append(ring("RAM", st.mem))
    gl.append(ring("BAT" if st.bat() is not None else "DISK", lambda: st.bat() if st.bat() is not None else st.disk())); col.append(gl)
    overlay.add_overlay(col); win.set_child(overlay)
    mc = Gtk.EventControllerMotion(); mc.connect("motion", lambda c, x, y: (setattr(S, "mx", x / max(1, win.get_width())), setattr(S, "my", y / max(1, win.get_height())))); overlay.add_controller(mc)
    prov = Gtk.CssProvider(); prov.load_from_data(CSS); Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def frame():
        live.queue_draw()
        for a in S.animated: a.queue_draw()
        return S.ahian
    def apply():
        S.ahian = os.path.exists(FLAG); pic.set_filename(wall_path()); pic.set_visible(not S.ahian); live.set_visible(S.ahian)
        (win.add_css_class if S.ahian else win.remove_css_class)("ahian")
        if S.ahian and not S.timer: S.timer = GLib.timeout_add(40, lambda: (frame() or setattr(S, "timer", 0)) or S.ahian)
        return True
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, apply); apply(); win.present()

app = Gtk.Application(application_id="os.smth.Home"); app.connect("activate", on_activate); sys.exit(app.run(sys.argv))
