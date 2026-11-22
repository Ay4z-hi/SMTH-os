#!/usr/bin/env python3
"""SMTH OS startup: the SMTH logo fading in, then out.

A GTK4 layer-shell overlay that shows only the wordmark on black.  There is no
desktop reconstruction, no cursor choreography and no other animation: the logo
fades in, holds, fades out, and the overlay closes onto the live session that
was already running underneath.  The timing lives in startup_model.py so it can
be tested without a display.

Disable for one session:   SMTH_NO_STARTUP_ANIMATION=1 smth-startup
Disable permanently:       smth-settings -> Accessibility -> Startup animation
Preview:                   smth-startup --force
"""
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


class Renderer:
    """Draws the single logo fade.  No other element exists."""

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

    def _draw_logo(self, cr, frame, w, h):
        if frame.logo_alpha <= 0.001:
            return
        cx, cy = w / 2, h / 2
        target = min(w * 0.24, h * 0.23, 220.0)
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
            text = "SMTH"
            cr.new_sub_path()
            D.draw_text(cr, text,
                        -D.text_width(text, dot) / 2,
                        -3.5 * dot, dot,
                        on=blend(M.WHITE, frame.logo_alpha), off=None)
        cr.restore()

    def draw(self, cr, w, h):
        frame = self.scene.frame(self.t)
        cr.set_source_rgb(0, 0, 0)
        cr.paint()
        self._draw_logo(cr, frame, w, h)
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
                # A click cuts straight to the desktop: no outro animation.
                self.finish()
                return GLib.SOURCE_REMOVE
            frame = self.scene.frame(self.renderer.t)
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

    # Keep the AHIAN takeover as the session startup after the user activates
    # AHIAN once. This is the normal ISO startup entry point.
    if (CONFIG / "ahian").exists() and "--normal" not in argv:
        import ahian_startup
        forwarded = [arg for arg in argv if arg != "--normal"]
        return ahian_startup.main(forwarded)

    if "--print-plan" in argv:
        scene = M.StartupScene(1920, 1080)
        for t in (0, 300, 700, 1100, 1400, M.DURATION_MS):
            frame = scene.frame(t)
            print(f"{t:>5} ms  {frame.phase:<9} alpha={frame.logo_alpha:.2f} "
                  f"duration={M.DURATION_MS}ms")
        return 0
    return run(reduced=reduced_motion() and "--force" not in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
