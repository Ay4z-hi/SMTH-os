#!/usr/bin/env python3
"""AHIAN takeover: the GTK4 overlay for the ISO.

Two acts, 19 seconds, drawn by the shared ``ahian_scene`` renderer:

    0 - 10 s   the 22 error windows arrive over the running desktop.  The
               overlay is transparent between windows, so the live wallpaper,
               icons, taskbar and every open window stay exactly where they
               are; the interference effects are translucent.
    10 - 19 s  the AH1AN system screen covers the display and counts down
               from nine.

At zero the countdown stops and the overlay closes.  The AHIAN desktop
underneath is the real, already-running session: nothing is rendered,
screenshotted or swapped in its place.  A click or any key closes the overlay
at any moment.  ``unahian`` clears it instantly too.

Disable for one session:   SMTH_NO_STARTUP_ANIMATION=1 smth-ahian-startup
Disable permanently:       smth-settings -> Accessibility -> Startup animation
Preview:                   smth-ahian-startup --force
"""
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, "/usr/local/lib/smth")
import ahian_startup_model as M
import ahian_scene

CONFIG = Path.home() / ".config" / "smth"
FONT_DIRS = (
    "/usr/share/fonts/truetype/space-mono",
    "/usr/share/fonts/truetype/doto",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts",
)


def _flag(path):
    try:
        return path.read_text(encoding="utf-8").strip().lower() in (
            "1", "on", "true", "yes")
    except OSError:
        return False


def disabled():
    if os.environ.get("SMTH_NO_STARTUP_ANIMATION", "").strip().lower() in (
            "1", "on", "true", "yes"):
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


def run(reduced=False):
    if not os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"):
        print("smth-ahian-startup: no graphical display; skipping", file=sys.stderr)
        return 0
    try:
        import cairo
    except Exception as exc:                       # pragma: no cover - ISO only
        print(f"smth-ahian-startup: cairo unavailable ({exc}); skipping",
              file=sys.stderr)
        return 0
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk, GLib, Gtk
    except Exception as exc:                       # pragma: no cover - ISO only
        print(f"smth-ahian-startup: GTK unavailable ({exc}); skipping", file=sys.stderr)
        return 0

    class AhianStartupApp(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="os.smth.AhianStartup")
            self.window = None
            self.area = None
            self.scene = None
            self.renderer = None
            self.t = 0.0
            self.started = 0.0
            self.skipping = None
            self.finished = False
            self.frame_image = None
            self.rendered_t = -1.0

        def do_activate(self):
            display = Gdk.Display.get_default()
            monitors = display.get_monitors() if display else None
            monitor = monitors.get_item(0) if monitors and monitors.get_n_items() else None
            geometry = monitor.get_geometry() if monitor else None
            width = geometry.width if geometry else 1280
            height = geometry.height if geometry else 800
            self.scene = M.StartupScene(width, height, reduced=reduced, profile="linux")
            self.renderer = ahian_scene.SceneRenderer(self.scene, font_dirs=FONT_DIRS)
            win = Gtk.Window(application=self)
            win.set_decorated(False)
            win.set_can_focus(True)
            win.add_css_class("smth-ahian-startup")
            win.set_default_size(width, height)
            self.window = win
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
            area.set_draw_func(self.draw)
            self.area = area
            win.set_child(area)
            provider = Gtk.CssProvider()
            # The overlay must not paint a backdrop: act 1 is a transparent
            # layer over the live desktop, and only the windows are opaque.
            provider.load_from_string(
                "window.smth-ahian-startup { background: transparent; }"
                "window.smth-ahian-startup drawingarea { background: transparent; }")
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            click = Gtk.GestureClick()
            click.connect("pressed", lambda *_: self.skip())
            win.add_controller(click)
            key = Gtk.EventControllerKey()
            key.connect("key-pressed", lambda *_: (self.skip(), True)[1])
            win.add_controller(key)
            self.started = time.monotonic()
            win.present()
            win.grab_focus()
            win.add_tick_callback(self.tick)

        def draw(self, _area, cr, width, height):
            if self.renderer is None:
                return
            try:
                image = self.renderer.render(self.t)
            except Exception as exc:               # never leave a black screen
                print(f"smth-ahian-startup: frame failed: {exc}", file=sys.stderr)
                self.finish()
                return
            if width > 0 and height > 0 and (image.width, image.height) != (width, height):
                image = image.resize((width, height))
            cr.set_operator(cairo.OPERATOR_SOURCE)
            data, stride = ahian_scene.to_argb32(image)
            surface = cairo.ImageSurface.create_for_data(
                data, cairo.FORMAT_ARGB32, image.width, image.height, stride)
            cr.set_source_surface(surface, 0, 0)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            self.frame_image = data          # keep the buffer alive with the surface
            self.rendered_t = self.t

        def skip(self):
            # A click or key removes the overlay immediately: no outro,
            # no fade, no second desktop.
            self.finish()

        def tick(self, _widget, _clock):
            try:
                now = time.monotonic()
                self.t = (now - self.started) * 1000.0
                # The tick callback fires at the display refresh; the scene is
                # authored at 30 fps and a Pillow frame is far too expensive to
                # draw at 60, so throttle the redraws instead of the clock.
                if self.rendered_t >= 0 and self.t - self.rendered_t < 30.0:
                    return GLib.SOURCE_CONTINUE
                frame = self.scene.frame(self.t)
                if frame.done:
                    self.finish()
                    return GLib.SOURCE_REMOVE
                self.area.queue_draw()
                return GLib.SOURCE_CONTINUE
            except Exception as exc:
                # A rendering failure must never leave the user without a
                # desktop: drop the overlay and let the live session show.
                print(f"smth-ahian-startup: renderer stopped: {exc}", file=sys.stderr)
                self.finish()
                return GLib.SOURCE_REMOVE

        def finish(self):
            if self.finished:
                return
            self.finished = True
            if self.window is not None:
                self.window.close()
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
        for t in (0, 2400, 5200, 8600, 9950, 10300, 12000, 15000, 18600, 19000):
            frame = scene.frame(t)
            print(f"{t:>6} ms  {frame.phase:<9} cards={len(frame.cards):>2} "
                  f"countdown={frame.blue.countdown} done={frame.done}")
        print(f"duration={M.DURATION_MS}ms")
        return 0
    if "--no-animation" in argv or (disabled() and "--force" not in argv):
        return 0
    return run(reduced=reduced_motion() and "--force" not in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
