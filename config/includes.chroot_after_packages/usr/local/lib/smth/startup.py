#!/usr/bin/env python3
"""SMTH OS cinematic startup construction.

A GTK4 layer-shell overlay that draws the real desktop being assembled, then
fades out to reveal the live labwc session underneath.  The scene geometry and
timing live in startup_model.py so they can be tested without a display.

Disable for one session:   SMTH_NO_STARTUP_ANIMATION=1 smth-startup
Disable permanently:       smth-settings -> Accessibility -> Startup animation
Preview:                   smth-startup --force
"""
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, "/usr/local/lib/smth")
import startup_model as M

LOGO_PATHS = ("/usr/share/smth/startup-logo.png", "/usr/share/smth/logo.png")
CONFIG = Path.home() / ".config" / "smth"


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


def logo_path():
    for path in LOGO_PATHS:
        if os.path.isfile(path):
            return path
    return None


def blend(colour, alpha):
    """Dotted labels have no alpha argument; blend against the black canvas."""
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
        self.logo = None
        self._load_logo()

    def _load_logo(self):
        import cairo
        path = logo_path()
        if not path:
            return
        try:
            self.logo = cairo.ImageSurface.create_from_png(path)
        except Exception:
            self.logo = None

    # ---- primitives ---------------------------------------------------------
    def _label(self, cr, text, x, y, dot, colour, alpha=1.0):
        import smthdot as D
        D.draw_text(cr, text, x, y, dot, on=blend(colour, alpha), off=None)

    def _panel(self, cr, rect, border=M.GREY, alpha=1.0, fill=M.BLACK):
        # Spatial depth: soft layered shadow beneath the panel.
        rgba(cr, M.BLACK, 0.45 * alpha)
        rounded(cr, rect.x + 2, rect.y + 4, rect.w, rect.h, 4)
        cr.fill()
        # Simulated liquid-glass surface: translucent fill + top highlight.
        rgba(cr, fill, 0.78 * alpha)
        rounded(cr, rect.x, rect.y, rect.w, rect.h, 4)
        cr.fill()
        rgba(cr, M.WHITE, 0.06 * alpha)
        cr.rectangle(rect.x + 2, rect.y + 1, rect.w - 4, max(1.0, rect.h * 0.18))
        cr.fill()
        rgba(cr, border, 0.72 * alpha)
        cr.set_line_width(1.0)
        rounded(cr, rect.x + 0.5, rect.y + 0.5, rect.w - 1, rect.h - 1, 4)
        cr.stroke()

    def _wipe(self, cr, rect, progress, horizontal=True):
        cr.save()
        if horizontal:
            cr.rectangle(rect.x - 2, rect.y - 2, max(0, rect.w * progress) + 4, rect.h + 4)
        else:
            cr.rectangle(rect.x - 2, rect.y - 2, rect.w + 4,
                         max(0, rect.h * progress) + 4)
        cr.clip()

    def _draw_logo(self, cr, frame, w, h):
        if frame.logo_alpha <= 0.001:
            return
        cx, cy = w / 2, h / 2
        target = min(w * 0.32, h * 0.30, 300.0)
        if self.logo is not None:
            iw, ih = self.logo.get_width(), self.logo.get_height()
        else:
            iw = ih = target
        target_w = target
        target_h = target * ih / max(1, iw)
        if target_h > target:
            target_h = target
            target_w = target * iw / max(1, ih)
        cr.save()
        cr.translate(cx, cy)
        cr.scale(frame.logo_scale, frame.logo_scale)
        cr.rectangle(-target_w / 2, -target_h / 2,
                     target_w, max(0.01, target_h * frame.logo_reveal))
        cr.clip()
        if self.logo is not None:
            cr.save()
            cr.scale(target_w / max(1, iw), target_h / max(1, ih))
            cr.set_source_surface(self.logo, -iw / 2, -ih / 2)
            cr.paint_with_alpha(frame.logo_alpha)
            cr.restore()
        else:
            import smthdot as D
            dot = max(1.6, target_w / D.text_width("SMTH", 1.0))
            self._label(cr, "SMTH",
                        -D.text_width("SMTH", dot) / 2,
                        -3.5 * dot, dot, M.WHITE, frame.logo_alpha)
        cr.restore()
        # Logo only: no text or extra marks are drawn during the logo phase.

    def _draw_dot_field(self, cr, frame, w, h):
        if frame.phase in ("logo", "done"):
            return
        alpha = 0.10
        if frame.t_ms > M.CONSTRUCT_END_MS:
            alpha *= max(0.0, 1 - (frame.t_ms - M.CONSTRUCT_END_MS) / 600)
        spacing = max(30, int(min(w, h) / 24))
        rgba(cr, M.GREY, alpha)
        for y in range(spacing, int(h) - spacing, spacing):
            for x in range(spacing, int(w) - spacing, spacing):
                cr.arc(x, y, 0.85, 0, math.tau)
                cr.fill()

    def _draw_status(self, cr, rect, progress, alpha, portrait):
        self._wipe(cr, rect, progress)
        self._panel(cr, rect, alpha=alpha)
        label_dot = max(1.3, min(2.1, rect.h / 24))
        self._label(cr, "SMTH", rect.x + 14, rect.y + rect.h / 2 - 3.5 * label_dot,
                    label_dot, M.WHITE, alpha)
        # module blocks, mirroring the real Waybar modules
        x = rect.x + rect.w * 0.28
        for i, width in enumerate((42, 54, 48, 70)):
            rgba(cr, M.GREY if i != 0 else M.RED, 0.9 * alpha)
            cr.rectangle(x, rect.y + rect.h / 2 - 5, width, 10)
            cr.fill()
            x += width + 12
        clock = "12:00" if portrait else "SMTH / DESKTOP"
        dot = max(1.15, min(1.8, rect.h / 28))
        self._label(cr, clock,
                    rect.right - 14 - __import__("smthdot").text_width(clock, dot),
                    rect.y + rect.h / 2 - 3.5 * dot, dot, M.WHITE, alpha)
        cr.restore()

    def _draw_grid(self, cr, rect, progress, alpha):
        self._wipe(cr, rect, progress)
        self._panel(cr, rect, border=M.GREY, alpha=alpha * 0.82)
        self._label(cr, "APPS", rect.x + 12, rect.y + 10, 1.5, M.CYAN, alpha)
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
        self._panel(cr, rect, border=M.GREY, alpha=alpha)
        inset = rect.inset(-4)
        rgba(cr, accent, 0.9 * alpha)
        cr.set_line_width(1.2)
        cr.move_to(inset.x, inset.y + 12)
        cr.line_to(inset.x, inset.y)
        cr.line_to(inset.x + 12, inset.y)
        cr.stroke()
        dot = max(1.5, rect.w / 22)
        label = f"{index + 1:02d}"
        self._label(cr, label, cx - __import__("smthdot").text_width(label, dot) / 2,
                    cy - 3.5 * dot, dot, accent, alpha)
        rgba(cr, M.GREY, 0.7 * alpha)
        cr.rectangle(rect.x + 10, rect.bottom - 10, rect.w * 0.55, 2)
        cr.fill()
        cr.restore()

    def _draw_window(self, cr, rect, progress, alpha):
        self._wipe(cr, rect, progress, horizontal=True)
        self._panel(cr, rect, border=M.GREY, alpha=alpha)
        bar = M.Rect(rect.x, rect.y, rect.w, min(34.0, rect.h * 0.12))
        rgba(cr, M.BLACK, 0.95 * alpha)
        cr.rectangle(bar.x, bar.y, bar.w, bar.h)
        cr.fill()
        rgba(cr, M.GREY, 0.8 * alpha)
        cr.set_line_width(1)
        cr.move_to(bar.x, bar.bottom - 0.5)
        cr.line_to(bar.right, bar.bottom - 0.5)
        cr.stroke()
        for i, colour in enumerate((M.RED, M.GREY, M.CYAN)):
            rgba(cr, colour, alpha)
            cr.arc(bar.x + 16 + i * 16, bar.y + bar.h / 2, 3.2, 0, math.tau)
            cr.fill()
        self._label(cr, "SMTH / WINDOW", bar.x + 78,
                    bar.y + bar.h / 2 - 5.0, 1.35, M.WHITE, alpha)
        side = M.Rect(rect.x + 1, bar.bottom + 1, rect.w * 0.25, rect.bottom - bar.bottom - 2)
        rgba(cr, M.BLACK, 0.72 * alpha)
        cr.rectangle(side.x, side.y, side.w, side.h)
        cr.fill()
        rgba(cr, M.GREY, 0.5 * alpha)
        cr.rectangle(side.right - 0.5, side.y, 0.5, side.h)
        cr.fill()
        for i in range(7):
            y = side.y + 22 + i * 28
            if y > side.bottom - 16:
                break
            rgba(cr, M.CYAN if i == 1 else M.GREY, alpha * (0.9 if i == 1 else 0.55))
            cr.rectangle(side.x + 14, y, side.w * (0.45 if i % 2 else 0.62), 5)
            cr.fill()
        content = M.Rect(side.right + 20, bar.bottom + 22,
                         rect.right - side.right - 40, rect.bottom - bar.bottom - 40)
        self._label(cr, "BUILDING THE DESKTOP", content.x, content.y, 1.5, M.WHITE, alpha)
        for i in range(4):
            y = content.y + 30 + i * 26
            if y > content.bottom - 8:
                break
            rgba(cr, M.BLUE if i == 0 else M.GREY, alpha * (0.75 if i == 0 else 0.35))
            cr.rectangle(content.x, y, content.w * (0.82 - i * 0.11), 4)
            cr.fill()
        chart = M.Rect(content.x, content.bottom - min(80, content.h * 0.3),
                       content.w * 0.55, min(62, content.h * 0.24))
        for i in range(12):
            height = chart.h * (0.25 + 0.7 * ((i * 7) % 11) / 10)
            rgba(cr, M.BLUE if i % 3 == 0 else M.CYAN, 0.6 * alpha)
            cr.rectangle(chart.x + i * (chart.w / 14), chart.bottom - height,
                         chart.w / 24, height)
            cr.fill()
        cr.restore()

    def _draw_clock(self, cr, rect, progress, alpha):
        self._wipe(cr, rect, progress)
        self._panel(cr, rect, alpha=alpha)
        import time
        text = time.strftime("%H:%M")
        dot = max(1.6, min(3.4, rect.w / 34))
        self._label(cr, text, rect.x + 16, rect.y + 18, dot, M.WHITE, alpha)
        self._label(cr, time.strftime("%a %d %b").upper(),
                    rect.x + 16, rect.bottom - 22, 1.35, M.GREY, alpha)
        cr.restore()

    def _draw_rings(self, cr, rect, progress, alpha):
        self._wipe(cr, rect, progress)
        import smthdot as D
        self._panel(cr, rect, alpha=alpha * 0.9)
        cy = rect.y + rect.h * 0.55
        D.dot_ring(cr, rect.x + rect.w * 0.22, cy, min(24, rect.h * 0.28),
                   0.64 * progress, n=24, dot=2.2, cols=(M.BLUE, M.CYAN))
        D.dot_ring(cr, rect.x + rect.w * 0.55, cy, min(24, rect.h * 0.28),
                   0.38 * progress, n=24, dot=2.2, cols=(M.PURPLE, M.GREY))
        self._label(cr, "SYS", rect.right - 34, cy - 5, 1.25, M.WHITE, alpha)
        cr.restore()

    def _draw_dock(self, cr, rect, progress, alpha):
        self._wipe(cr, rect, progress)
        self._panel(cr, rect, border=M.GREY, alpha=alpha)
        n = 6
        step = rect.w / (n + 1)
        for i in range(n):
            x = rect.x + step * (i + 0.5)
            colour = (M.RED, M.WHITE, M.CYAN, M.GREY, M.PURPLE, M.AMBER)[i]
            rgba(cr, colour, 0.92 * alpha)
            cr.arc(x, rect.y + rect.h / 2, min(9, rect.h * 0.22), 0, math.tau)
            cr.fill()
            rgba(cr, M.BLACK, alpha)
            cr.arc(x, rect.y + rect.h / 2, min(3.5, rect.h * 0.09), 0, math.tau)
            cr.fill()
        cr.restore()

    def _draw_items(self, cr, frame):
        for item in frame.items:
            spec, p = item.spec, item.progress
            if spec.kind == "status":
                self._draw_status(cr, spec.rect, p, item.alpha, self.scene.portrait)
            elif spec.kind == "grid":
                self._draw_grid(cr, spec.rect, p, item.alpha)
            elif spec.kind == "window":
                self._draw_window(cr, spec.rect, p, item.alpha)
            elif spec.kind == "icon":
                index = int(spec.key.split("-")[1])
                self._draw_icon(cr, spec.rect, p, item.alpha, index, spec.accent)
            elif spec.kind == "clock":
                self._draw_clock(cr, spec.rect, p, item.alpha)
            elif spec.kind == "rings":
                self._draw_rings(cr, spec.rect, p, item.alpha)
            elif spec.kind == "dock":
                self._draw_dock(cr, spec.rect, p, item.alpha)

    def _draw_box(self, cr, box):
        if box.alpha <= 0.01 or box.progress <= 0:
            return
        r = box.spec.rect
        p = box.progress
        a = box.alpha
        rgba(cr, box.spec.colour, 0.045 * a)
        cr.rectangle(r.x, r.y, r.w, r.h)
        cr.fill()
        cr.set_line_width(1.35)
        rgba(cr, box.spec.colour, 0.96 * a)
        perimeter = 2 * (r.w + r.h)
        drawn = perimeter * p
        segments = ((r.x, r.y, r.w, 0), (r.right, r.y, 0, r.h),
                    (r.right, r.bottom, -r.w, 0), (r.x, r.bottom, 0, -r.h))
        for sx, sy, dx, dy in segments:
            length = abs(dx) + abs(dy)
            if drawn <= 0:
                break
            f = min(1.0, drawn / max(1.0, length))
            cr.move_to(sx, sy)
            cr.line_to(sx + dx * f, sy + dy * f)
            cr.stroke()
            drawn -= length
        # corner registration ticks
        tick = min(9.0, max(5.0, min(r.w, r.h) * 0.10))
        for x, y, sx, sy in ((r.x, r.y, 1, 1), (r.right, r.y, -1, 1),
                             (r.x, r.bottom, 1, -1), (r.right, r.bottom, -1, -1)):
            cr.move_to(x, y)
            cr.line_to(x + sx * tick, y)
            cr.move_to(x, y)
            cr.line_to(x, y + sy * tick)
            cr.stroke()
        if p > 0.35:
            dot = max(1.15, min(2.0, min(r.w, r.h) / 45))
            import smthdot as D
            label_w = D.text_width(box.spec.label, dot)
            self._label(cr, box.spec.label, r.x, max(4, r.y - 7 * dot - 4),
                        dot, box.spec.colour, a)

    def _draw_cursor(self, cr, frame):
        import smthdot  # noqa: F401  (ensures bundled module import works)
        spec, x, y = frame.spec, frame.x, frame.y
        a = frame.alpha
        if a <= 0.01:
            return
        for i, (tx, ty) in enumerate(frame.trail):
            rgba(cr, spec.colour, a * (0.20 - i * 0.045))
            cr.arc(tx, ty, max(1.0, 4.0 - i * 0.7), 0, math.tau)
            cr.fill()
        if frame.click > 0:
            rgba(cr, spec.colour, frame.click * 0.7 * a)
            cr.set_line_width(1.4)
            cr.arc(x, y, 8 + 22 * (1 - frame.click), 0, math.tau)
            cr.stroke()
        cr.save()
        cr.translate(x, y)
        cr.scale(1.15, 1.15)
        points = ((0, 0), (0, 18), (4.6, 13.4), (7.4, 20),
                  (10.2, 18.7), (7.4, 12.2), (13.5, 12.2))
        cr.new_path()
        cr.move_to(*points[0])
        for px, py in points[1:]:
            cr.line_to(px, py)
        cr.close_path()
        rgba(cr, M.BLACK, 0.9 * a)
        cr.set_line_width(3.2)
        cr.stroke_preserve()
        rgba(cr, spec.colour, a)
        cr.fill_preserve()
        rgba(cr, M.WHITE, 0.45 * a)
        cr.set_line_width(0.8)
        cr.stroke()
        cr.restore()
        dot = 1.2
        self._label(cr, spec.key, x + 18, y + 18, dot, spec.colour, a)

    def draw(self, cr, w, h):
        frame = self.scene.frame(self.t)
        cr.set_source_rgb(0, 0, 0)
        cr.paint()
        self._draw_dot_field(cr, frame, w, h)
        self._draw_logo(cr, frame, w, h)
        self._draw_items(cr, frame)
        for box in frame.boxes:
            self._draw_box(cr, box)
        for cursor in frame.cursors:
            self._draw_cursor(cr, cursor)
        # The final fade is handled by window opacity in the GTK shell.
        return frame


def run(reduced=False):
    if not os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"):
        print("smth-startup: no graphical display; skipping", file=sys.stderr)
        return 0
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk, GLib, Gtk
    except Exception as exc:
        print(f"smth-startup: GTK unavailable ({exc}); skipping", file=sys.stderr)
        return 0

    class StartupApp(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="os.smth.Startup")
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
            win.add_css_class("smth-startup")
            win.set_default_size(width, height)
            self.win = win
            try:
                gi.require_version("Gtk4LayerShell", "1.0")
                from gi.repository import Gtk4LayerShell as LS
                LS.init_for_window(win)
                LS.set_namespace(win, "smth-startup")
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
            provider.load_from_string("window.smth-startup { background: #000000; }")
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

        def finish(self):
            if self.done:
                return
            self.done = True
            if self.win is not None:
                self.win.close()
            self.quit()

    app = StartupApp()
    try:
        return app.run([])
    except Exception as exc:
        print(f"smth-startup: renderer stopped: {exc}", file=sys.stderr)
        return 0


def main(argv):
    if "--no-animation" in argv or (disabled() and "--force" not in argv):
        return 0

    # Keep the full AHIAN cursor-built desktop as the session startup after
    # the user activates AHIAN once. This is the normal ISO startup entry point.
    if _flag(CONFIG / "ahian") and "--normal" not in argv:
        import ahian_startup
        forwarded = [arg for arg in argv if arg != "--normal"]
        return ahian_startup.main(forwarded)

    if "--print-plan" in argv:
        scene = M.StartupScene(1920, 1080)
        frame = scene.frame(4200)
        print(f"phase={frame.phase} cursors={len(frame.cursors)} "
              f"boxes={len(frame.boxes)} items={len(frame.items)} "
              f"duration={M.DURATION_MS}ms")
        return 0
    return run(reduced=reduced_motion() and "--force" not in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
