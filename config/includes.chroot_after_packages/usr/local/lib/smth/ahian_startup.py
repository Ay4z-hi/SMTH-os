#!/usr/bin/env python3
"""AHIAN desktop reconstruction reveal.

A GTK4 layer-shell overlay that draws the AHIAN desktop rebuilding itself over
~9 seconds, then fades into the live AHIAN desktop that home.py is already
drawing underneath.  The timeline, geometry and colours live in
``ahian_startup_model.py`` and are shared with the Android and Windows
launchers.

There are no cursors in this sequence: wallpaper fragments, dot-matrix tiles,
taskbar segments, widgets and icons assemble in place.

Disable for one session:   SMTH_NO_STARTUP_ANIMATION=1 smth-ahian-startup
Disable permanently:       smth-settings -> Accessibility -> Startup animation
Preview:                   smth-ahian-startup --force
"""
import math
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, "/usr/local/lib/smth")
import ahian_startup_model as M

CONFIG = Path.home() / ".config" / "smth"

# App labels in the same order as home.py's shortcut list, so the reconstructed
# icons sit exactly where the live desktop icons appear.
ICON_LABELS = ("FILES", "BROWSER", "STORE", "CAMERA", "GALLERY", "PAINT",
               "NOTES", "CALC", "PLAYER", "CLOCK", "TERMINAL", "SETTINGS")

GOLD = math.pi * (3 - math.sqrt(5))
TAU = math.tau


def _flag(path):
    try:
        return path.read_text(encoding="utf-8").strip().lower() in ("1", "on", "true", "yes")
    except OSError:
        return False


def disabled():
    if os.environ.get("SMTH_NO_STARTUP_ANIMATION", "").strip().lower() in ("1", "on", "true", "yes"):
        return True
    try:
        cmdline = Path("/proc/cmdline").read_text(encoding="utf-8", errors="replace")
    except OSError:
        cmdline = ""
    if "smth.no_startup_animation=1" in cmdline:
        return True
    try:
        value = (CONFIG / "startup-animation").read_text(encoding="utf-8").strip().lower()
    except OSError:
        return False
    return value in ("0", "off", "false", "no")


def reduced_motion():
    return _flag(CONFIG / "reduce-motion")


def blend(colour, alpha):
    """Dotted labels have no alpha argument; blend against the dark canvas."""
    return tuple(c * alpha for c in colour)


def rgba(cr, colour, alpha=1.0):
    cr.set_source_rgba(colour[0], colour[1], colour[2], alpha)


def rounded(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class Renderer:
    def __init__(self, scene):
        self.scene = scene
        self.t = 0.0

    # ---- primitives ---------------------------------------------------------
    def _label(self, cr, text, x, y, dot, colour, alpha=1.0):
        try:
            import smthdot as D
            D.draw_text(cr, text, x, y, dot, on=blend(colour, alpha), off=None)
        except Exception:
            rgba(cr, colour, alpha)
            cr.select_font_face("monospace")
            cr.set_font_size(dot * 7)
            cr.move_to(x, y + dot * 7)
            cr.show_text(text)

    @staticmethod
    def _text_width(text, dot):
        try:
            import smthdot as D
            return D.text_width(text, dot)
        except Exception:
            return len(text) * dot * 6

    def _panel(self, cr, rect, accent, alpha=1.0, radius=4.0):
        rgba(cr, M.BLACK, 0.42 * alpha)
        rounded(cr, rect.x + 2, rect.y + 4, rect.w, rect.h, radius)
        cr.fill()
        rgba(cr, M.PANEL, 0.92 * alpha)
        rounded(cr, rect.x, rect.y, rect.w, rect.h, radius)
        cr.fill()
        # A quiet purple-to-teal edge instead of glass highlights.
        grad = (M.PURPLE if rect.x < self.scene.width * 0.5 else M.TEAL)
        del grad
        rgba(cr, accent, 0.42 * alpha)
        cr.set_line_width(1.0)
        rounded(cr, rect.x + 0.5, rect.y + 0.5, rect.w - 1, rect.h - 1, radius)
        cr.stroke()

    # ---- wallpaper ----------------------------------------------------------
    def _draw_wallpaper(self, cr, frame, w, h):
        # One continuous gradient under every fragment: the tiles reveal it,
        # the assembled wall has no seams, and the live desktop matches.
        gradient = None
        if frame.tiles:
            gradient = __import__("cairo").LinearGradient(0, 0, w, h)
            gradient.add_color_stop_rgba(0, *M.WALLPAPER_PURPLE, 1.0)
            gradient.add_color_stop_rgba(1, *M.WALLPAPER_TEAL, 1.0)
        for tile in frame.tiles:
            self._draw_tile(cr, frame, tile, gradient)
        # The AHIAN gradient wash: strongest while the fragments assemble, then
        # settling into the same quiet tint the live desktop keeps.
        if frame.wallpaper_alpha > 0:
            g = __import__("cairo").LinearGradient(0, 0, w, h)
            g.add_color_stop_rgba(0, *M.PURPLE, 0.06 * frame.wallpaper_alpha)
            g.add_color_stop_rgba(1, *M.TEAL, 0.06 * frame.wallpaper_alpha)
            cr.set_source(g)
            cr.rectangle(0, 0, w, h)
            cr.fill()

    def _draw_tile(self, cr, frame, tile, gradient=None):
        r = tile.spec.rect
        a = tile.alpha
        if a <= 0.001:
            return
        tint = M.mix_colour(M.PURPLE, M.TEAL, tile.spec.mix)
        cx, cy = r.centre()
        cr.save()
        cr.translate(cx, cy)
        cr.scale(tile.scale, tile.scale)
        cr.translate(-cx, -cy)
        cr.rectangle(r.x, r.y, r.w, r.h)
        cr.clip()
        # Each fragment resolves to the same near-black plate, so the assembled
        # wall has no seams when the reconstruction completes.
        cr.rectangle(r.x, r.y, r.w, r.h)
        if gradient is not None:
            cr.set_source(gradient)
            cr.paint_with_alpha(a)
        else:
            rgba(cr, M.wallpaper_colour(tile.spec.mix), a)
            cr.fill()
        # Dot-matrix detail is a construction pattern: it fades once assembled.
        detail = M.clamp(1.0 - (frame.t_ms - 2400) / 900.0)
        if detail > 0.01:
            n = tile.spec.dots
            step_x = r.w / (n + 1)
            step_y = r.h / (n + 1)
            radius = max(0.7, min(step_x, step_y) * 0.10)
            for row in range(n):
                for col in range(n):
                    rgba(cr, tint, 0.55 * a * detail)
                    cr.arc(r.x + step_x * (col + 1), r.y + step_y * (row + 1),
                           radius, 0, TAU)
                    cr.fill()
        cr.restore()

    def _draw_rings(self, cr, frame):
        for ring in frame.rings:
            rgba(cr, ring.colour, ring.alpha)
            cr.set_line_width(1.2)
            cr.arc(ring.x, ring.y, ring.r, 0, TAU)
            cr.stroke()

    def _draw_particles(self, cr, frame):
        for p in frame.particles:
            rgba(cr, p.colour, p.alpha)
            cr.arc(p.x, p.y, p.r, 0, TAU)
            cr.fill()

    def _draw_black_hole(self, cr, frame, w, h):
        """The live AHIAN desktop scene: dot disk, void and teal orbit ring."""
        alpha = frame.wallpaper_alpha
        if alpha <= 0.01:
            return
        cx, cy = w * 0.64, h * 0.48
        R = h * 0.105
        scale = h / 1080.0
        tilt, cs, sn = 0.27, math.cos(-0.22), math.sin(-0.22)
        seconds = frame.t_ms / 1000.0
        for i in range(220):
            rr = 1.45 + 2.95 * math.sqrt((i + 0.5) / 220)
            a = i * GOLD + 0.55 * (1.45 / rr) ** 1.5 * seconds
            r = rr * R
            x = r * math.cos(a)
            s = math.sin(a)
            y = (r * s * tilt if s >= 0
                 else -math.sqrt(max(0.0, r * r - x * x)) * 0.93)
            tr = (rr - 1.45) / 2.95
            bright = 0.62 - 0.38 * math.cos(a)
            radius = (1.0 + 3.4 * bright * (1 - 0.55 * tr)) * scale * 0.9
            colour = M.TEAL if i % 2 else M.PURPLE_SOFT
            rgba(cr, colour, alpha * (0.35 + 0.45 * bright))
            cr.arc(cx + x * cs - y * sn, cy + x * sn + y * cs, radius, 0, TAU)
            cr.fill()
        rgba(cr, M.DARK, alpha)
        cr.arc(cx, cy, R, 0, TAU)
        cr.fill()
        pulse = 0.65 + 0.35 * math.sin(seconds * 2.2)
        rgba(cr, M.TEAL_BRIGHT, alpha * 0.9)
        cr.set_line_width((1.2 + 1.8 * pulse) * scale)
        cr.arc(cx, cy, R * 1.08, 0, TAU)
        cr.stroke()

    # ---- structure ----------------------------------------------------------
    def _draw_items(self, cr, frame):
        for item in frame.items:
            spec, p, a = item.spec, item.progress, item.alpha
            if spec.kind == "taskbar":
                self._draw_taskbar(cr, spec.rect, p, a)
            elif spec.kind == "edge":
                self._draw_edge(cr, spec.rect, p, a)
            elif spec.kind == "clock":
                self._draw_clock(cr, spec.rect, p, a)
            elif spec.kind == "rings":
                self._draw_rings_widget(cr, spec.rect, p, a)
            elif spec.kind == "icon":
                index = int(spec.key.split("-")[1])
                self._draw_icon(cr, spec.rect, p, a, index, spec.accent)
            elif spec.kind == "window":
                self._draw_window(cr, spec.rect, p, a)

    def _draw_taskbar(self, cr, rect, progress, alpha):
        cr.save()
        cr.rectangle(rect.x - 2, rect.y - 2,
                     max(0.1, rect.w * progress) + 4, rect.h + 4)
        cr.clip()
        self._panel(cr, rect, M.TEAL, alpha, radius=3.0)
        dot = max(1.2, min(1.8, rect.h / 26))
        self._label(cr, "SMTH", rect.x + 14,
                    rect.y + rect.h / 2 - 3.5 * dot, dot, M.INK, alpha)
        text = "AHIAN / DESKTOP"
        self._label(cr, text,
                    rect.right - 14 - self._text_width(text, dot),
                    rect.y + rect.h / 2 - 3.5 * dot, dot, M.TEAL_BRIGHT, alpha)
        cr.restore()

    def _draw_edge(self, cr, rect, progress, alpha):
        g = __import__("cairo").LinearGradient(rect.x, rect.y, rect.right, rect.y)
        g.add_color_stop_rgba(0, *M.PURPLE, 0.95 * alpha)
        g.add_color_stop_rgba(0.5, *M.PURPLE_SOFT, 0.85 * alpha)
        g.add_color_stop_rgba(1, *M.TEAL, 0.95 * alpha)
        cr.set_source(g)
        cr.rectangle(rect.x, rect.y, rect.w * progress, max(1.0, rect.h))
        cr.fill()

    def _draw_clock(self, cr, rect, progress, alpha):
        cr.save()
        cr.rectangle(rect.x - 2, rect.y - 2,
                     max(0.1, rect.w * progress) + 4, rect.h + 4)
        cr.clip()
        self._panel(cr, rect, M.PURPLE_SOFT, alpha)
        dot = max(1.6, min(3.0, rect.w / 34))
        self._label(cr, time.strftime("%H:%M"), rect.x + 14, rect.y + 12,
                    dot, M.INK, alpha)
        self._label(cr, time.strftime("%a %d %b").upper(),
                    rect.x + 14, rect.bottom - 12 - dot * 7,
                    max(1.1, dot * 0.45), M.GREY, alpha)
        cr.restore()

    def _draw_rings_widget(self, cr, rect, progress, alpha):
        cr.save()
        cr.rectangle(rect.x - 2, rect.y - 2,
                     max(0.1, rect.w * progress) + 4, rect.h + 4)
        cr.clip()
        self._panel(cr, rect, M.TEAL, alpha, radius=10.0)
        try:
            import smthdot as D
            cy = rect.y + rect.h * 0.55
            D.dot_ring(cr, rect.x + rect.w * 0.24, cy, min(24, rect.h * 0.28),
                       0.64 * progress, n=24, dot=2.2,
                       cols=(M.PURPLE, M.TEAL))
            D.dot_ring(cr, rect.x + rect.w * 0.56, cy, min(24, rect.h * 0.28),
                       0.38 * progress, n=24, dot=2.2,
                       cols=(M.PURPLE_SOFT, M.GREY))
        except Exception:
            rgba(cr, M.TEAL, 0.5 * alpha)
            cr.set_line_width(1.4)
            cr.arc(rect.x + rect.w * 0.3, rect.y + rect.h * 0.55, 14, 0, TAU)
            cr.stroke()
        self._label(cr, "SYS", rect.right - 40, rect.y + rect.h / 2 - 5,
                    1.25, M.INK, alpha)
        cr.restore()

    def _draw_icon(self, cr, rect, progress, alpha, index, accent):
        if progress <= 0:
            return
        scale = 0.72 + 0.28 * M.ease(progress)
        cx, cy = rect.centre()
        cr.save()
        cr.translate(cx, cy)
        cr.scale(scale, scale)
        cr.translate(-cx, -cy)
        self._panel(cr, rect, accent, alpha, radius=6.0)
        # A 3x3 dot-matrix app mark, drawn from fragments.
        dot = max(1.4, min(3.0, rect.w / 26))
        gx = cx - dot * 1.5
        gy = rect.y + rect.h * 0.33
        for row in range(3):
            for col in range(3):
                if (row + col + index) % 4 == 3:
                    continue
                rgba(cr, accent, 0.9 * alpha)
                cr.arc(gx + col * dot * 1.6, gy + row * dot * 1.6,
                       dot * 0.44, 0, TAU)
                cr.fill()
        label = ICON_LABELS[index % len(ICON_LABELS)]
        ldot = max(1.0, min(1.35, rect.w / 64))
        self._label(cr, label, cx - self._text_width(label, ldot) / 2,
                    rect.bottom - 8 - ldot * 7, ldot, M.INK, alpha)
        cr.restore()

    def _draw_window(self, cr, rect, progress, alpha):
        cr.save()
        cr.rectangle(rect.x - 2, rect.y - 2,
                     max(0.1, rect.w * progress) + 4, rect.h + 4)
        cr.clip()
        self._panel(cr, rect, M.PURPLE, alpha, radius=8.0)
        bar_h = min(34.0, rect.h * 0.12)
        rgba(cr, M.BLACK, 0.55 * alpha)
        cr.rectangle(rect.x + 1, rect.y + 1, rect.w - 2, bar_h)
        cr.fill()
        for i, colour in enumerate((M.PURPLE, M.TEAL, M.PURPLE_SOFT)):
            rgba(cr, colour, 0.95 * alpha)
            cr.arc(rect.x + 16 + i * 16, rect.y + bar_h / 2, 3.2, 0, TAU)
            cr.fill()
        self._label(cr, "SMTH / WINDOW", rect.x + 76,
                    rect.y + bar_h / 2 - 4.5, 1.3, M.INK, alpha)
        top = rect.y + bar_h + 12
        left = rect.x + 18
        self._label(cr, "DESKTOP RECONSTRUCTION", left, top, 1.5,
                    M.INK, alpha)
        for i in range(4):
            y = top + 26 + i * 22
            if y > rect.bottom - 24:
                break
            rgba(cr, M.TEAL if i == 0 else M.PURPLE, (0.5 if i == 0 else 0.22) * alpha)
            cr.rectangle(left, y, (rect.w - 36) * (0.78 - i * 0.12), 4)
            cr.fill()
        chart_h = min(58.0, rect.h * 0.2)
        base = rect.bottom - 18
        for i in range(14):
            height = chart_h * (0.22 + 0.7 * ((i * 7) % 11) / 10)
            rgba(cr, M.TEAL if i % 3 == 0 else M.PURPLE_SOFT,
                 (0.55 if i % 3 == 0 else 0.25) * alpha)
            cr.rectangle(left + i * ((rect.w - 36) / 16), base - height,
                         (rect.w - 36) / 26, height)
            cr.fill()
        cr.restore()

    def _draw_segments(self, cr, frame):
        for segment in frame.segments:
            spec = segment.spec
            r = spec.rect
            width = max(2.0, r.w * segment.progress)
            rgba(cr, spec.accent, 0.22)
            rounded(cr, r.x, r.y, width, r.h, 2.0)
            cr.fill()
            rgba(cr, spec.accent, 0.85)
            rounded(cr, r.x, r.y, width, max(1.0, r.h * 0.34), 2.0)
            cr.fill()

    # ---- frame --------------------------------------------------------------
    def draw(self, cr, w, h):
        frame = self.scene.frame(self.t)
        cr.set_source_rgb(*M.DARK)
        cr.paint()
        self._draw_wallpaper(cr, frame, w, h)
        self._draw_rings(cr, frame)
        self._draw_particles(cr, frame)
        self._draw_black_hole(cr, frame, w, h)
        self._draw_items(cr, frame)
        self._draw_segments(cr, frame)
        # The final fade is the overlay window's own opacity.
        return frame


def run(reduced=False):
    if not os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"):
        print("smth-ahian-startup: no graphical display; skipping", file=sys.stderr)
        return 0
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk, GLib, Gtk
    except Exception as exc:
        print(f"smth-ahian-startup: GTK unavailable ({exc}); skipping", file=sys.stderr)
        return 0

    class AhianStartupApp(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="os.smth.AhianStartup")
            self.win = None
            self.area = None
            self.scene = None
            self.renderer = None
            self.started = 0
            self.skipping = None
            self.done = False

        def do_activate(self):
            display = Gdk.Display.get_default()
            monitors = display.get_monitors() if display else None
            monitor = monitors.get_item(0) if monitors and monitors.get_n_items() else None
            geometry = monitor.get_geometry() if monitor else None
            width = geometry.width if geometry else 1280
            height = geometry.height if geometry else 800
            self.scene = M.StartupScene(width, height, reduced=reduced)
            self.renderer = Renderer(self.scene)
            win = Gtk.Window(application=self)
            win.set_decorated(False)
            win.set_can_focus(True)
            win.add_css_class("smth-ahian-startup")
            win.set_default_size(width, height)
            self.win = win
            try:
                gi.require_version("Gtk4LayerShell", "1.0")
                from gi.repository import Gtk4LayerShell as LS
                LS.init_for_window(win)
                LS.set_namespace(win, "smth-ahian-startup")
                LS.set_layer(win, LS.Layer.OVERLAY)
                for edge in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
                    LS.set_anchor(win, edge, True)
                LS.set_exclusive_zone(win, -1)
                LS.set_keyboard_mode(win, LS.KeyboardMode.ON_DEMAND)
            except Exception:
                win.fullscreen()
            area = Gtk.DrawingArea()
            area.set_hexpand(True)
            area.set_vexpand(True)
            area.set_draw_func(lambda _a, cr, w, h: self.renderer.draw(cr, w, h))
            self.area = area
            win.set_child(area)
            provider = Gtk.CssProvider()
            provider.load_from_string(
                "window.smth-ahian-startup { background: #07060d; }")
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            click = Gtk.GestureClick()
            click.connect("pressed", lambda *_: self.skip())
            win.add_controller(click)
            key = Gtk.EventControllerKey()
            key.connect("key-pressed", lambda *_: (self.skip(), True)[1])
            win.add_controller(key)
            self.started = GLib.get_monotonic_time() / 1000.0
            win.present()
            win.grab_focus()
            win.add_tick_callback(self.tick)
            area.queue_draw()

        def skip(self):
            if self.skipping is None:
                self.skipping = GLib.get_monotonic_time() / 1000.0

        def tick(self, widget, clock):
            try:
                now = GLib.get_monotonic_time() / 1000.0
                self.renderer.t = now - self.started
                if self.skipping is not None:
                    fade = max(0.0, 1.0 - (now - self.skipping) / 160.0)
                    self.win.set_opacity(fade)
                    self.area.queue_draw()
                    if fade <= 0.001:
                        self.finish()
                    return GLib.SOURCE_CONTINUE
                frame = self.scene.frame(self.renderer.t)
                self.win.set_opacity(frame.overlay_alpha)
                self.area.queue_draw()
                if frame.done:
                    self.finish()
                    return GLib.SOURCE_REMOVE
                return GLib.SOURCE_CONTINUE
            except Exception as exc:
                # A rendering failure must never leave the user without a
                # desktop: drop the overlay and let the live session show.
                print(f"smth-ahian-startup: renderer stopped: {exc}", file=sys.stderr)
                self.finish()
                return GLib.SOURCE_REMOVE

        def finish(self):
            if self.done:
                return
            self.done = True
            if self.win is not None:
                self.win.close()
            self.quit()

    app = AhianStartupApp()
    try:
        return app.run([])
    except Exception as exc:
        print(f"smth-ahian-startup: renderer stopped: {exc}", file=sys.stderr)
        return 0


def main(argv):
    if "--print-plan" in argv:
        scene = M.StartupScene(1920, 1080)
        frame = scene.frame(5500)
        print(f"phase={frame.phase} particles={len(frame.particles)} "
              f"tiles={len(frame.tiles)} segments={len(frame.segments)} "
              f"items={len(frame.items)} duration={M.DURATION_MS}ms")
        return 0
    if "--no-animation" in argv or (disabled() and "--force" not in argv):
        return 0
    return run(reduced=reduced_motion() and "--force" not in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
