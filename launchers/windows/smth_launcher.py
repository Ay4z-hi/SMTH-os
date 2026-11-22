"""SMTH Launcher for Windows.

A companion desktop shell in the SMTH OS visual language: maroon #701B35,
obsidian #09090B and blush #F2C6D2, the bundled Doto and Space Mono faces, a
custom wallpaper and a small original line-icon set. It launches real Windows
applications and settings targets; it does not replace Explorer.

Every action reports its failure in the status line instead of failing silently.
"""

# Terminal command support
TERMINAL_COMMANDS = {
    "help": """SMTH Terminal - built-in commands
  help       show this message
  clear      clear the terminal
  date       show current date and time
  version    show SMTH OS version
  about      about this terminal
  ahian      activate AHIAN mode (easter egg)
  unahian    exit AHIAN mode

AHIAN is a hidden experience. Type 'ahian' and press Enter.""",
    "about": """SMTH Terminal
A built-in terminal for SMTH OS.

This terminal runs on Android, Linux (ISO) and Windows.
It understands a small set of SMTH commands including the
AHIAN easter egg. It does not expose the system shell.""",
}


def get_terminal_response(command):
    """Process a terminal command and return (output, is_ahian_action)."""
    cmd = command.strip().lower()
    if cmd == "help":
        return TERMINAL_COMMANDS["help"], False
    elif cmd == "clear":
        return "terminal cleared", False
    elif cmd == "date":
        import datetime
        return datetime.datetime.now().strftime("%A, %d %B %Y | %H:%M:%S"), False
    elif cmd == "version":
        return "SMTH OS Launcher v1.0.0\nTerminal v1.0.0 | Windows\nAHIAN mode v1.0.0", False
    elif cmd == "about":
        return TERMINAL_COMMANDS["about"], False
    elif cmd == "exit" or cmd == "quit":
        return "Type 'ahian' for the SMTH easter egg, or close the terminal.", False
    return None, False  # Unknown command - caller should handle

import ctypes
import datetime
import json
import math
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import font as tkfont

try:                                   # Pillow ships with the portable build
    from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageTk
    HAVE_PIL = True
except Exception:                      # pragma: no cover - minimal fallback
    HAVE_PIL = False

OBSIDIAN = "#09090B"
MAROON = "#701B35"
BLUSH = "#F2C6D2"
SURFACE = "#0D0B0F"          # obsidian lifted one step for the taskbar
BLUSH_DIM = "#8A7078"        # blush at low emphasis, still within the palette
MAROON_DEEP = "#3A0F1D"
BODY = "#120E13"            # the inside of a glass card
AHIAN_PURPLE = "#4FB0E0"      # cold blue (was purple)
AHIAN_TEAL = "#F0A85A"        # amber (was teal)
AHIAN_DEEP = "#141822"

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
if not os.path.isdir(ASSETS):
    ASSETS = os.path.join(getattr(sys, "_MEIPASS", ""), "assets")


def register_bundled_fonts():
    """Load the bundled fonts for this process only (no system-wide install)."""
    if not sys.platform.startswith("win"):
        return
    FR_PRIVATE = 0x10
    for name in ("SpaceMono-Regular.ttf", "Doto.ttf"):
        path = os.path.join(ASSETS, name)
        if os.path.isfile(path):
            try:
                ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0)
            except OSError:
                pass


# Each app: label, launcher target, fallback targets, kind, glyph.
# kind: "scheme" -> os.startfile, "exe" -> subprocess, "url" -> webbrowser
APPS = [
    ("Files", "explorer.exe", [], "exe", "folder"),
    ("Settings", "ms-settings:", [], "scheme", "gear"),
    ("Store", "ms-windows-store:", ["ms-windows-store://home"], "scheme", "bag"),
    ("Calculator", "calc.exe", [], "exe", "calc"),
    ("Terminal", "wt.exe", ["powershell.exe"], "exe", "terminal"),
    ("Browser", "https://www.bing.com", [], "url", "globe"),
    ("Clock", "ms-clock:", [], "scheme", "clock"),
    ("Notepad", "notepad.exe", [], "exe", "note"),
    ("Photos", "ms-photos:", [], "scheme", "photo"),
    ("Task Manager", "taskmgr.exe", [], "exe", "gauge"),
    ("Display settings", "ms-settings:display", [], "scheme", "display"),
    ("Sound settings", "ms-settings:sound", [], "scheme", "speaker"),
    ("SMTH Terminal", None, [], "smth_terminal", "terminal"),
]

PINNED = ("Files", "Browser", "Terminal", "Settings", "Calculator", "Photos")

# Track built-in terminal window
smth_terminal_window = None


def glass_image(width, height, radius=16, tint=(23, 16, 23), alpha=226):
    """The liquid-glass card as an RGBA Pillow image, drawn at 2x and reduced.

    Shared by the Tk photo cache and the headless preview tool so the artwork
    shown in review is the artwork the launcher paints.
    """
    if not HAVE_PIL:
        return None
    scale = 2
    w, h = max(2, int(width)) * scale, max(2, int(height)) * scale
    r = min(int(radius) * scale, min(w, h) // 2)
    # Highlights and rims are translucent layers: drawing them straight onto
    # the card replaces its pixels (ImageDraw does not blend alpha), so they
    # are composited instead of stamped.
    card = Image.new("RGBA", (w, h), tint + (alpha,))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    glow_h = int(h * 0.52)
    for y in range(glow_h):
        a = int(22 * (1 - y / max(1, glow_h)))
        if a:
            gd.line((0, y, w, y), fill=(255, 255, 255, a))
    card = Image.alpha_composite(card, glow)
    rim = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rim)
    rd.rounded_rectangle((0, 0, w - 1, h - 1), r,
                         outline=(242, 198, 210, 74), width=scale)
    if w > 6 * scale:
        rd.rounded_rectangle((scale, scale, w - 1 - scale, h - 1 - scale),
                             max(0, r - scale), outline=(255, 255, 255, 22),
                             width=scale)
    card = Image.alpha_composite(card, rim)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
    card.putalpha(ImageChops.multiply(card.getchannel("A"), mask))
    return card.resize((int(width), int(height)), Image.LANCZOS)


def draw_glyph(canvas, kind, cx, cy, size, colour=BLUSH, width=1.6, tags=()):
    """One coherent line-icon language, drawn with canvas primitives."""
    s = size / 2.0
    common = dict(outline=colour, width=width, tags=tags)

    def rect(x0, y0, x1, y1, r=0):
        canvas.create_rectangle(cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s,
                                fill="", **common)

    def line(x0, y0, x1, y1):
        canvas.create_line(cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s, fill=colour,
                           width=width, tags=tags, capstyle="round")

    def oval(x0, y0, x1, y1):
        canvas.create_oval(cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s,
                           fill="", **common)

    if kind == "folder":
        canvas.create_line(cx - s * 0.8, cy - s * 0.45, cx - s * 0.25, cy - s * 0.45,
                           cx - s * 0.1, cy - s * 0.62, cx + s * 0.8, cy - s * 0.62,
                           fill=colour, width=width, tags=tags)
        rect(-0.8, -0.42, 0.8, 0.62)
    elif kind == "gear":
        oval(-0.42, -0.42, 0.42, 0.42)
        oval(-0.16, -0.16, 0.16, 0.16)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-0.72, -0.72), (0.72, 0.72), (-0.72, 0.72), (0.72, -0.72)):
            line(dx * 0.55, dy * 0.55, dx * 0.82, dy * 0.82)
    elif kind == "bag":
        line(-0.62, -0.35, 0.62, -0.35)
        line(-0.62, -0.35, -0.78, 0.72)
        line(0.62, -0.35, 0.78, 0.72)
        line(-0.78, 0.72, 0.78, 0.72)
        canvas.create_arc(cx - s * 0.35, cy - s * 0.95, cx + s * 0.35, cy - s * 0.05,
                          start=0, extent=180, style="arc", outline=colour, width=width, tags=tags)
    elif kind == "calc":
        rect(-0.62, -0.78, 0.62, 0.78)
        rect(-0.38, -0.55, 0.38, -0.22)
        for row in range(2):
            for col in range(3):
                x = -0.36 + col * 0.36
                y = 0.02 + row * 0.34
                canvas.create_oval(cx + x * s - 1.4, cy + y * s - 1.4, cx + x * s + 1.4,
                                   cy + y * s + 1.4, fill=colour, outline="", tags=tags)
    elif kind == "terminal":
        rect(-0.82, -0.62, 0.82, 0.62, 2)
        line(-0.5, -0.22, -0.18, 0.04)
        line(-0.5, 0.3, -0.18, 0.04)
        line(0.06, 0.3, 0.5, 0.3)
    elif kind == "globe":
        oval(-0.8, -0.8, 0.8, 0.8)
        line(-0.8, 0, 0.8, 0)
        canvas.create_arc(cx - s * 0.38, cy - s * 0.8, cx + s * 0.38, cy + s * 0.8,
                          start=0, extent=360, style="arc", outline=colour, width=width, tags=tags)
    elif kind == "clock":
        oval(-0.78, -0.78, 0.78, 0.78)
        line(0, -0.42, 0, 0.05)
        line(0, 0.05, 0.34, 0.24)
    elif kind == "note":
        rect(-0.62, -0.78, 0.62, 0.78)
        line(-0.36, -0.4, 0.36, -0.4)
        line(-0.36, -0.1, 0.36, -0.1)
        line(-0.36, 0.2, 0.1, 0.2)
    elif kind == "photo":
        rect(-0.82, -0.62, 0.82, 0.62)
        line(-0.7, 0.48, -0.16, -0.12)
        line(-0.16, -0.12, 0.18, 0.22)
        line(0.18, 0.22, 0.44, -0.04)
        line(0.44, -0.04, 0.7, 0.48)
        canvas.create_oval(cx + s * 0.34 - 2, cy - s * 0.34 - 2, cx + s * 0.34 + 2,
                           cy - s * 0.34 + 2, fill=colour, outline="", tags=tags)
    elif kind == "gauge":
        canvas.create_arc(cx - s * 0.8, cy - s * 0.8, cx + s * 0.8, cy + s * 0.8,
                          start=20, extent=140, style="arc", outline=colour, width=width, tags=tags)
        line(-0.38, 0.28, 0.34, -0.26)
    elif kind == "display":
        rect(-0.85, -0.62, 0.85, 0.46)
        line(0, 0.46, 0, 0.72)
        line(-0.36, 0.72, 0.36, 0.72)
    elif kind == "speaker":
        canvas.create_polygon(cx - s * 0.7, cy - s * 0.22, cx - s * 0.32, cy - s * 0.22,
                              cx - s * 0.02, cy - s * 0.58, cx - s * 0.02, cy + s * 0.58,
                              cx - s * 0.32, cy + s * 0.22, cx - s * 0.7, cy + s * 0.22,
                              fill="", outline=colour, width=width, tags=tags)
        canvas.create_arc(cx - s * 0.12, cy - s * 0.5, cx + s * 0.62, cy + s * 0.5,
                          start=-55, extent=110, style="arc", outline=colour, width=width, tags=tags)
    else:  # fallback mark
        rect(-0.62, -0.62, 0.62, 0.62, 3)
        canvas.create_polygon(cx, cy - s * 0.34, cx + s * 0.34, cy, cx, cy + s * 0.34,
                              cx - s * 0.34, cy, fill="", outline=MAROON, width=width, tags=tags)


class SMTHLauncher:
    def __init__(self, root):
        self.root = root
        root.title("SMTH")
        root.geometry("1100x700")
        root.minsize(820, 560)
        root.configure(bg=OBSIDIAN)
        try:
            icon = os.path.join(ASSETS, "smth.ico")
            if os.path.isfile(icon):
                root.iconbitmap(icon)
        except (OSError, tk.TclError):
            pass
        root.bind("<Escape>", self.on_escape)
        root.bind("<Control-f>", lambda *_: self.focus_search())

        self.mono = self.pick_font(("Space Mono", "Consolas", "Courier New"))
        self.display = self.pick_font(("Doto", "Space Mono", "Segoe UI"))
        self.wallpaper = None
        self._img_cache = {}
        self.recent = []
        self.start_open = False
        self.shortcut_positions = {}
        self.layout_file = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "SMTH", "desktop-layout.json"
        )
        try:
            with open(self.layout_file, encoding="utf-8") as handle:
                saved = json.load(handle)
            if isinstance(saved, dict):
                for name, pos in saved.items():
                    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                        self.shortcut_positions[str(name)] = (float(pos[0]), float(pos[1]))
        except (OSError, ValueError, TypeError):
            pass
        self.drag_state = None
        self.ahian_mode = False
        self.ahian_state_file = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "SMTH", "ahian-mode"
        )
        self.canvas = tk.Canvas(root, bg=OBSIDIAN, highlightthickness=0, bd=0)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.canvas.bind("<Configure>", lambda _e: self.paint_desktop())
        self.canvas.bind("<Button-1>", self.on_desktop_click)
        self.root.bind("<Configure>", self.on_root_configure, add="+")

        self.build_taskbar()
        self.build_start()
        self.tick()
        self.intro = None
        self.root.after(20, self.start_intro)

    # ---- chrome ---------------------------------------------------------
    def pick_font(self, candidates):
        available = set(tkfont.families(self.root))
        for name in candidates:
            if name in available:
                return name
        return "TkDefaultFont"

    # ---- glass assets ----------------------------------------------------
    def glass_photo(self, width, height, radius=16, tint=(23, 16, 23), alpha=226):
        """A cached Tk photo of the shared glass card, drawn with Pillow."""
        key = (int(width), int(height), int(radius), tint, alpha)
        if key in self._img_cache:
            return self._img_cache[key]
        img = glass_image(width, height, radius, tint, alpha)
        if img is None or ImageTk is None:
            return None
        photo = ImageTk.PhotoImage(img, master=self.root)
        self._img_cache[key] = photo
        return photo

    def wallpaper_image(self):
        if not HAVE_PIL:
            return None
        art = getattr(self, "_wall_pil", None)
        if art is not None:
            return art
        if self.root.winfo_width() < 100 or self.root.winfo_height() < 100:
            return None                      # not mapped yet; do not cache a 1x1
        try:
            art = Image.open(os.path.join(ASSETS, "smth-wallpaper.png")).convert("RGB")
        except (OSError, ValueError):
            return None
        self._wall_pil = ImageOps.fit(art, (max(1, self.root.winfo_width()),
                                            max(1, self.root.winfo_height())),
                                      Image.LANCZOS, centering=(0.5, 0.5))
        return self._wall_pil

    def wallpaper_crop(self, x, y, width, height):
        """The slice of wallpaper behind a floating panel, for seamless corners."""
        art = self.wallpaper_image()
        if art is None:
            return None
        return art.crop((max(0, int(x)), max(0, int(y)),
                         max(1, int(x) + int(width)), max(1, int(y) + int(height))))

    def glass_over_backdrop(self, x, y, width, height, radius=22, tint=(26, 17, 25), alpha=240):
        """Rounded glass over the exact wallpaper behind it: real transparent corners."""
        if not HAVE_PIL:
            return None
        key = ("backdrop", int(x), int(y), int(width), int(height), int(radius), tint, alpha)
        if key in self._img_cache:
            return self._img_cache[key]
        crop = None if self.ahian_mode else self.wallpaper_crop(x, y, width, height)
        if crop is None or crop.size != (int(width), int(height)):
            crop = Image.new("RGB", (int(width), int(height)),
                             (20, 24, 34) if self.ahian_mode else (9, 9, 11))
        glass = self.glass_photo(width, height, radius, tint, alpha)
        if glass is None:
            return None
        merged = crop.convert("RGBA")
        merged.alpha_composite(ImageTk.getimage(glass))
        photo = ImageTk.PhotoImage(merged, master=self.root)
        self._img_cache[key] = photo
        return photo

    def draw_icon_tile(self, canvas, size, radius=12, tags=()):
        """Rounded glass plate used behind every app glyph."""
        photo = self.glass_photo(size, size, radius)
        if photo is not None:
            canvas.delete("tile")
            canvas.create_image(0, 0, image=photo, anchor="nw", tags=("tile",) + tuple(tags))
            canvas.tile = photo
            canvas.tag_lower("tile")

    def load_wallpaper(self):
        path = os.path.join(ASSETS, "smth-wallpaper.png")
        try:
            self.wallpaper = tk.PhotoImage(file=path)
        except (tk.TclError, OSError):
            self.wallpaper = None
        self.paint_desktop()

    def paint_desktop(self):
        c = self.canvas
        c.delete("desktop")
        w, h = max(1, c.winfo_width()), max(1, c.winfo_height())
        if self.ahian_mode:
            paint_ahian_wallpaper(c, w, h, tags=("desktop",))
        elif self.wallpaper is not None:
            # Tk scales by integer subsampling; crop the overflow to the window.
            factor = max(1, min(self.wallpaper.width() // w, self.wallpaper.height() // h) or 1)
            self._wall = self.wallpaper.subsample(factor, factor) if factor > 1 else self.wallpaper
            c.create_image(w // 2, h // 2, image=self._wall, tags="desktop")
            # A quiet obsidian band keeps labels legible wherever the art falls.
            c.create_rectangle(0, 0, w, h, fill="", outline="", tags="desktop")
        else:
            c.create_rectangle(0, 0, w, h, fill=OBSIDIAN, outline="", tags="desktop")
            c.create_polygon(0, h, w, h * 0.55, w, h * 0.72, 0, h, fill=MAROON_DEEP, outline="", tags="desktop")
        self.draw_shortcuts(w, h)
        c.tag_lower("desktop")
        if self.start_open:
            self.raise_start()

    def _grid_metrics(self):
        """The invisible desktop grid: 100 x 86 cells from (20, 20).

        Each cell holds one 80 x 64 glass tile with a 20 px gutter on every
        side, so shortcuts can never overlap or clip at any window size.
        """
        cell_w, cell_h, origin_x, origin_y = 100, 86, 20, 20
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        cols = max(1, int(max(1, width - origin_x - 80) // cell_w) + 1)
        rows = max(1, int(max(1, height - origin_y - 54 - 64) // cell_h) + 1)
        return cell_w, cell_h, origin_x, origin_y, cols, rows

    def snap_shortcut(self, name, x, y):
        """Resolve a drag to one free cell; occupied cells are never reused."""
        cell_w, cell_h, origin_x, origin_y, cols, rows = self._grid_metrics()
        x = max(origin_x, min(origin_x + (cols - 1) * cell_w, float(x)))
        y = max(origin_y, min(origin_y + (rows - 1) * cell_h, float(y)))
        col = max(0, min(cols - 1, round((x - origin_x) / cell_w)))
        row = max(0, min(rows - 1, round((y - origin_y) / cell_h)))
        occupied = set()
        for other, (ox, oy) in self.shortcut_positions.items():
            if other == name:
                continue
            occupied.add((round((ox - origin_x) / cell_w),
                          round((oy - origin_y) / cell_h)))
        start = row * cols + col
        for offset in range(cols * rows):
            cell = (start + offset) % (cols * rows)
            candidate = (cell % cols, cell // cols)
            if candidate not in occupied:
                col, row = candidate
                break
        return origin_x + col * cell_w, origin_y + row * cell_h

    def save_shortcuts(self):
        try:
            os.makedirs(os.path.dirname(self.layout_file), exist_ok=True)
            temp = self.layout_file + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump({n: list(p) for n, p in self.shortcut_positions.items()},
                          handle, indent=2)
            os.replace(temp, self.layout_file)
        except OSError:
            pass

    def draw_shortcuts(self, w, h):
        c = self.canvas
        entries = [a for a in APPS if a[0] in PINNED][:6]
        for i, (name, target, fallbacks, kind, glyph) in enumerate(entries):
            cols = max(1, (max(1, w) - 40) // 100)
            default_position = (20 + (i % cols) * 100, 20 + (i // cols) * 86)
            x, y = self.shortcut_positions.get(name, default_position)
            x, y = self.snap_shortcut(name, x, y)
            self.shortcut_positions[name] = (x, y)
            tag = f"shortcut-{i}"
            accent = "#B9A0FF" if self.ahian_mode else BLUSH
            photo = self.glass_photo(52, 52, 15)
            if photo is not None:
                c.create_image(x + 24, y + 2, image=photo, anchor="nw", tags=("desktop", tag))
                c.shortcut_photos = getattr(c, "shortcut_photos", {})
                c.shortcut_photos[tag] = photo
            draw_glyph(c, glyph, x + 50, y + 28, 24, accent, 1.5, tags=("desktop", tag))
            c.create_text(x + 50, y + 64, text=name, fill=accent, anchor="center",
                          font=(self.mono, 8), tags=("desktop", tag))
            c.tag_bind(tag, "<ButtonPress-1>", lambda e, n=name: self.begin_shortcut_drag(e, n))
            c.tag_bind(tag, "<B1-Motion>", self.drag_shortcut)
            c.tag_bind(tag, "<ButtonRelease-1>",
                       lambda e, t=target, k=kind, f=fallbacks: self.end_shortcut_drag(e, t, k, f))

    def begin_shortcut_drag(self, event, name):
        self.drag_state = {"name": name, "x": event.x, "y": event.y, "moved": False}
        return "break"

    def drag_shortcut(self, event):
        state = self.drag_state
        if not state:
            return "break"
        dx, dy = event.x - state["x"], event.y - state["y"]
        if abs(dx) + abs(dy) > 2:
            state["moved"] = True
        if state["moved"]:
            tag = next((f"shortcut-{i}" for i, app in enumerate([a for a in APPS if a[0] in PINNED][:6])
                        if app[0] == state["name"]), None)
            if tag:
                self.canvas.move(tag, dx, dy)
                old_x, old_y = self.shortcut_positions.get(
                    state["name"], (44, 34 + [a[0] for a in APPS if a[0] in PINNED][:6].index(state["name"]) * 74))
                self.shortcut_positions[state["name"]] = (old_x + dx, old_y + dy)
            state["x"], state["y"] = event.x, event.y
        return "break"

    # Drag releases resolve to one invisible grid cell; occupied cells are skipped.
    def end_shortcut_drag(self, event, target, kind, fallbacks):
        state = self.drag_state
        self.drag_state = None
        if state and state["moved"]:
            name = state["name"]
            x, y = self.shortcut_positions.get(name, (44, 34))
            nx, ny = self.snap_shortcut(name, x, y)
            tag = next((f"shortcut-{i}" for i, app in enumerate([a for a in APPS if a[0] in PINNED][:6])
                        if app[0] == name), None)
            if tag:
                self.canvas.move(tag, nx - x, ny - y)
            self.shortcut_positions[name] = (nx, ny)
            self.save_shortcuts()
        elif state and not state["moved"]:
            self.launch(target, kind, fallbacks)
        return "break"

    def build_taskbar(self):
        # One floating glass capsule, drawn on a canvas so its corners are real.
        self.taskbar = tk.Canvas(self.root, bg=OBSIDIAN, highlightthickness=0, bd=0)
        self.taskbar.place(x=12, rely=1.0, y=-58, relwidth=1, width=-24, height=46)
        self.taskbar.bind("<Configure>", lambda _e: self.paint_taskbar())
        self.paint_taskbar()

    def paint_taskbar(self):
        c = self.taskbar
        w, h = max(1, c.winfo_width()), max(1, c.winfo_height())
        c.delete("all")
        photo = self.glass_over_backdrop(c.winfo_x(), c.winfo_y(), w, h, 23,
                                         tint=(26, 17, 25), alpha=238)
        if photo is not None:
            c.create_image(0, 0, image=photo, anchor="nw")
            c.taskbar_photo = photo
        c.create_text(18, h // 2, text="SMTH", fill=BLUSH, anchor="w",
                      font=(self.display, 10, "bold"), tags=("start",))
        c.tag_bind("start", "<Button-1>", lambda _e: self.open_start(focus=True))
        x = 84
        for index, name in enumerate(PINNED[:5]):
            app = next((a for a in APPS if a[0] == name), None)
            if not app:
                continue
            tag = f"pin-{index}"
            tile = self.glass_photo(32, 32, 11, tint=(35, 23, 33), alpha=232)
            if tile is not None:
                c.create_image(x, h // 2 - 16, image=tile, anchor="nw", tags=(tag,))
                c.taskbar_tiles = getattr(c, "taskbar_tiles", {})
                c.taskbar_tiles[tag] = tile
            kind = "terminal" if app[3] == "smth_terminal" else app[4]
            draw_glyph(c, kind, x + 16, h // 2 - 1, 17, BLUSH, 1.5, tags=(tag,))
            if name in self.recent:
                c.create_oval(x + 13, h - 9, x + 19, h - 3, fill=BLUSH, outline="", tags=(tag,))
            c.tag_bind(tag, "<Button-1>", lambda _e, a=app: self.launch_pinned(a))
            x += 40
        now = datetime.datetime.now()
        c.create_text(w - 16, h // 2 - 7, text=now.strftime("%H:%M"), fill=BLUSH, anchor="e",
                      font=(self.mono, 10), tags=("clock",))
        c.create_text(w - 16, h // 2 + 8, text=now.strftime("%a %d %b").upper(), fill=BLUSH_DIM,
                      anchor="e", font=(self.mono, 7), tags=("date",))
        c.create_text(w - 78, h // 2, text=self.read_battery(), fill=BLUSH_DIM, anchor="e",
                      font=(self.mono, 8), tags=("battery",))

    def launch_pinned(self, app):
        if app[3] == "smth_terminal":
            self.launch(app[0], app[3])
        else:
            self.launch(app[1], app[3], app[2])
        self.paint_taskbar()

    def pinned_dot(self, canvas, name):
        canvas.delete("run")
        if name in self.recent:
            canvas.create_oval(15, 29, 19, 33, fill=BLUSH, outline="", tags="run")

    def build_start(self):
        self.panel = tk.Frame(self.root, bg=BODY, bd=0, highlightthickness=0)
        self.panel_bg = tk.Canvas(self.panel, bg=OBSIDIAN, highlightthickness=0, bd=0)
        self.panel_bg.place(x=0, y=0, relwidth=1, relheight=1)
        self.panel_bg.bind("<Configure>", lambda _e: self.paint_panel())
        body = tk.Frame(self.panel, bg=BODY)
        body.place(x=18, y=16, relwidth=1, width=-36, relheight=1, height=-32)

        head = tk.Frame(body, bg=BODY)
        head.pack(fill="x")
        tk.Label(head, text="SMTH", fg=BLUSH, bg=BODY,
                 font=(self.display, 14, "bold")).pack(side="left")
        tk.Label(head, text="START", fg=BLUSH_DIM, bg=BODY,
                 font=(self.mono, 7)).pack(side="right", pady=(8, 0))

        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self.filter_start())
        self.search_shell = tk.Canvas(body, height=42, bg=BODY, highlightthickness=0, bd=0)
        self.search_shell.pack(fill="x", pady=(10, 0))
        self.search = tk.Entry(self.search_shell, textvariable=self.query, bg="#1A131B", fg=BLUSH,
                               insertbackground=BLUSH, relief="flat", font=(self.mono, 10),
                               highlightthickness=0, bd=0)
        self._search_window = self.search_shell.create_window(16, 21, window=self.search,
                                                              anchor="w", width=200, height=28)
        self.search_shell.bind("<Configure>", self.resize_search)
        self.search.bind("<Return>", lambda *_: self.launch_first())
        self.search.bind("<Escape>", lambda *_: self.close_start())
        self.search.bind("<Down>", lambda *_: self.focus_list())

        tk.Label(body, text="PINNED", fg=BLUSH_DIM, bg=BODY,
                 font=(self.mono, 7)).pack(anchor="w", pady=(12, 4))
        self.pin_row = tk.Frame(body, bg=BODY)
        self.pin_row.pack(fill="x")
        for name in PINNED[:6]:
            app = next((a for a in APPS if a[0] == name), None)
            if not app: continue
            cell = tk.Frame(self.pin_row, bg=BODY, cursor="hand2")
            cell.pack(side="left", padx=(0, 5))
            icon = tk.Canvas(cell, width=40, height=40, bg=BODY, highlightthickness=0, bd=0)
            icon.pack()
            self.draw_icon_tile(icon, 40, 13)
            label = tk.Label(cell, text=name, fg=BLUSH, bg=BODY, font=(self.mono, 7))
            if app[3] == "smth_terminal":
                draw_glyph(icon, "terminal", 20, 19, 22, BLUSH, 1.5)
                for widget in (cell, icon, label):
                    widget.bind("<Button-1>", lambda _e, a=app: self.launch_start(a))
            else:
                draw_glyph(icon, app[4], 20, 19, 22, BLUSH, 1.5)
                for widget in (cell, icon, label):
                    widget.bind("<Button-1>", lambda _e, a=app: self.launch_start(a))
            label.pack()

        tk.Label(body, text="ALL APPLICATIONS", fg=BLUSH_DIM, bg=BODY,
                 font=(self.mono, 7)).pack(anchor="w", pady=(12, 2))
        self.all_frame = tk.Frame(body, bg=BODY)
        self.all_frame.pack(fill="both", expand=True)
        self.draw_all_apps()

        foot = tk.Frame(body, bg=BODY)
        foot.pack(fill="x", pady=(8, 0))
        self.status = tk.Label(foot, text="", fg=BLUSH_DIM, bg=BODY, anchor="w",
                               font=(self.mono, 8))
        self.status.pack(side="left", fill="x", expand=True)
        self.pill(foot, "SETTINGS", lambda: self.launch("ms-settings:", "scheme")).pack(side="right", padx=(4, 0))
        self.pill(foot, "POWER", self.power_menu).pack(side="right")

    def on_root_configure(self, event):
        if event.widget is not self.root:
            return
        self._wall_pil = None
        self.paint_taskbar()
        if getattr(self, "start_open", False):
            self.paint_panel()

    def paint_panel(self):
        """Rounded glass plate under the Start menu (the body sits inset on it)."""
        if not hasattr(self, "panel_bg"):
            return
        w = self.panel_bg.winfo_width()
        h = self.panel_bg.winfo_height()
        if w < 20 or h < 20:
            return
        photo = self.glass_over_backdrop(self.panel.winfo_x(), self.panel.winfo_y(), w, h, 24,
                                         tint=(30, 19, 28), alpha=244)
        self.panel_bg.delete("glass")
        if photo is not None:
            self.panel_bg.create_image(0, 0, image=photo, anchor="nw", tags="glass")
            self.panel_bg.glass_photo = photo

    def resize_search(self, event):
        w = max(80, event.width)
        self.search_shell.delete("glass")
        photo = self.glass_photo(w, 42, 21, tint=(28, 18, 26), alpha=240)
        if photo is not None:
            self.search_shell.create_image(0, 0, image=photo, anchor="nw", tags="glass")
            self.search_shell.glass_photo = photo
            self.search_shell.tag_lower("glass")
        self.search_shell.coords(self._search_window, 16, 21)
        self.search_shell.itemconfigure(self._search_window, width=max(40, w - 32))

    def pill(self, parent, label, command):
        width = tkfont.Font(font=(self.mono, 7)).measure(label) + 32
        canvas = tk.Canvas(parent, width=width, height=27, bg=BODY,
                           highlightthickness=0, bd=0, cursor="hand2")
        photo = self.glass_photo(width, 27, 13, tint=(34, 22, 32), alpha=235)
        if photo is not None:
            canvas.create_image(0, 0, image=photo, anchor="nw")
            canvas._photo = photo
        canvas.create_text(width / 2, 14, text=label, fill=BLUSH, font=(self.mono, 7))
        canvas.bind("<Button-1>", lambda _e: command())
        return canvas

    def draw_all_apps(self):
        for child in self.all_frame.winfo_children():
            child.destroy()
        self.filtered = [app[0] for app in APPS]
        self.selected_row = 0
        self.list_scroll = 0
        self.list_canvas = tk.Canvas(self.all_frame, bg=BODY, highlightthickness=0, bd=0)
        self.list_canvas.pack(fill="both", expand=True)
        self.list_canvas.bind("<Configure>", lambda _e: self.render_rows())
        self.list_canvas.bind("<Button-1>", self.on_row_click)
        self.list_canvas.bind("<Double-Button-1>", self.on_row_open)
        self.list_canvas.bind("<Return>", lambda _e: self.launch_selected())
        self.list_canvas.bind("<Down>", lambda _e: self.move_row(1))
        self.list_canvas.bind("<Up>", lambda _e: self.move_row(-1))
        self.list_canvas.bind("<MouseWheel>", self.on_list_wheel)
        self.render_rows()

    def render_rows(self):
        """Draw the application list as rounded glass rows, never a listbox."""
        if not hasattr(self, "list_canvas"):
            return
        c = self.list_canvas
        width = max(1, c.winfo_width())
        height = max(1, c.winfo_height())
        c.delete("all")
        row_h = 30
        visible = max(1, height // row_h)
        self.list_scroll = max(0, min(self.list_scroll, max(0, len(self.filtered) - visible)))
        plain = self.glass_photo(max(40, width - 4), row_h - 4, 13, tint=(30, 19, 28), alpha=180)
        chosen = self.glass_photo(max(40, width - 4), row_h - 4, 13, tint=(86, 24, 44), alpha=235)
        for offset, name in enumerate(self.filtered[self.list_scroll:self.list_scroll + visible]):
            y = offset * row_h
            photo = chosen if self.list_scroll + offset == self.selected_row else plain
            if photo is not None:
                c.create_image(2, y + 2, image=photo, anchor="nw")
                c.row_photos = getattr(c, "row_photos", {})
                c.row_photos[offset] = photo
            selected = self.list_scroll + offset == self.selected_row
            c.create_text(18, y + row_h / 2, text=name, anchor="w",
                          fill=BLUSH if selected else BLUSH_DIM, font=(self.mono, 9))

    def on_row_click(self, event):
        index = self.list_scroll + int(event.y // 30)
        if 0 <= index < len(self.filtered):
            self.selected_row = index
            self.render_rows()
            self.list_canvas.focus_set()
        return "break"

    def on_row_open(self, event):
        self.on_row_click(event)
        self.launch_selected()
        return "break"

    def move_row(self, delta):
        if not self.filtered:
            return "break"
        self.selected_row = max(0, min(len(self.filtered) - 1, self.selected_row + delta))
        visible = max(1, self.list_canvas.winfo_height() // 30)
        if self.selected_row < self.list_scroll:
            self.list_scroll = self.selected_row
        elif self.selected_row >= self.list_scroll + visible:
            self.list_scroll = self.selected_row - visible + 1
        self.render_rows()
        return "break"

    def on_list_wheel(self, event):
        step = -1 if getattr(event, "delta", 0) > 0 else 1
        self.list_scroll = max(0, self.list_scroll + step)
        self.render_rows()
        return "break"

    def filter_start(self):
        q = self.query.get().strip().lower()
        self.filtered = [app[0] for app in APPS if not q or q in app[0].lower()]
        self.selected_row = 0
        self.list_scroll = 0
        self.render_rows()
        for child in self.pin_row.winfo_children():
            child.pack_forget()
        if not q:
            for child in self.pin_row.winfo_children():
                child.pack(side="left", padx=(0, 5))

    # ---- start menu window state ---------------------------------------
    def toggle_start(self):
        self.close_start() if self.start_open else self.open_start()

    def open_start(self, focus=False):
        if self.start_open:
            if focus:
                self.search.focus_set()
            return
        self.start_open = True
        w, h = self.root.winfo_width(), self.root.winfo_height()
        panel_w = min(760, max(420, int(w * 0.52)))
        panel_h = min(520, max(300, h - 120))
        self._panel_h = panel_h
        self._wall_pil = None
        self.panel.place(x=12, y=h - 58 - panel_h + 14, width=panel_w, height=panel_h)
        self.panel.lift()
        self.paint_panel()
        self.slide(14, target=0)
        self.root.after(160, self.paint_panel)
        if focus:
            self.search.focus_set()

    def slide(self, offset, target, step=0):
        h = self.root.winfo_height()
        panel_h = getattr(self, "_panel_h", 420)
        y = int(h - 58 - panel_h + offset)
        self.panel.place_configure(y=y)
        if step < 5 and offset != target:
            nxt = offset + (target - offset) * 0.55
            if abs(nxt - target) < 1:
                nxt = target
            self.root.after(16, lambda: self.slide(nxt, target, step + 1))

    def close_start(self):
        if not self.start_open:
            return
        self.start_open = False
        self.panel.place_forget()
        self.search.delete(0, "end")
        self.query.set("")

    def raise_start(self):
        self.panel.lift()

    def on_escape(self, *_):
        if self.start_open:
            self.close_start()
        else:
            self.root.destroy()

    def on_desktop_click(self, event):
        if self.start_open and not (self.panel.winfo_x() <= event.x <= self.panel.winfo_x() + self.panel.winfo_width()
                                    and self.panel.winfo_y() <= event.y <= self.panel.winfo_y() + self.panel.winfo_height()):
            self.close_start()

    def focus_search(self):
        self.open_start(focus=True)

    def focus_list(self):
        if self.filtered:
            self.selected_row = 0
            self.list_canvas.focus_set()
            self.render_rows()

    # ---- apps -----------------------------------------------------------
    def launch_selected(self):
        name = self.filtered[self.selected_row] if self.filtered else ""
        app = next((a for a in APPS if a[0] == name), None)
        if app:
            self.launch_start(app)

    def launch_start(self, app):
        # Handle built-in terminal specially
        if app[3] == "smth_terminal":
            global smth_terminal_window
            if smth_terminal_window is None or not smth_terminal_window.win.winfo_exists():
                smth_terminal_window = TerminalWindow(self)
            else:
                smth_terminal_window.win.focus_force()
            self.close_start()
            return
        self.launch(app[1], app[3], app[2])
        self.close_start()

    def launch_first(self):
        q = self.query.get().strip().lower()
        app = next((a for a in APPS if q in a[0].lower()), None)
        if app:
            self.launch_start(app)
        elif q:
            self.status.config(text=f"No application matches “{q}”", fg=BLUSH_DIM)

    def launch(self, target, kind="exe", fallbacks=()):
        name = next((a[0] for a in APPS if a[1] == target), target)
        try:
            if kind == "smth_terminal":
                # Built-in SMTH Terminal
                global smth_terminal_window
                if smth_terminal_window is None or not smth_terminal_window.win.winfo_exists():
                    smth_terminal_window = TerminalWindow(self)
                else:
                    smth_terminal_window.win.focus_force()
                self.status.config(text="Opened SMTH Terminal", fg=BLUSH_DIM)
                return
            elif kind == "url":
                import webbrowser
                webbrowser.open(target)
            elif kind == "scheme":
                # Protocol handlers must go through the shell; webbrowser would
                # treat "ms-settings:" as an unknown URL and fail silently.
                os.startfile(target)
            else:
                subprocess.Popen([target], shell=False)
            if name not in self.recent:
                self.recent.insert(0, name)
                self.recent = self.recent[:5]
            self.status.config(text=f"Opened {name}", fg=BLUSH_DIM)
            self.paint_taskbar()
            return
        except (OSError, subprocess.SubprocessError) as first_error:
            for fallback in fallbacks:
                try:
                    if fallback.endswith(":"):
                        os.startfile(fallback)
                    else:
                        subprocess.Popen([fallback], shell=False)
                    self.status.config(text=f"Opened {fallback} (fallback for {name})", fg=BLUSH_DIM)
                    return
                except (OSError, subprocess.SubprocessError):
                    continue
            self.status.config(text=f"Could not open {name}: {first_error}", fg=BLUSH)

    def power_menu(self):
        from tkinter import messagebox
        if not messagebox.askyesno("Power", "Shut down Windows?\n\nCancel leaves the system running.",
                                   parent=self.root):
            self.status.config(text="Shutdown cancelled", fg=BLUSH_DIM)
            return
        try:
            subprocess.Popen(["shutdown", "/s", "/t", "0"], shell=False)
            self.status.config(text="Shutting down…", fg=BLUSH)
        except (OSError, subprocess.SubprocessError) as e:
            self.status.config(text=f"Shutdown failed: {e}", fg=BLUSH)

    def tick(self):
        now = datetime.datetime.now()
        try:
            self.taskbar.itemconfigure("clock", text=now.strftime("%H:%M"))
            self.taskbar.itemconfigure("date", text=now.strftime("%a %d %b").upper())
            self.taskbar.itemconfigure("battery", text=self.read_battery())
        except (AttributeError, tk.TclError):
            pass
        self.root.after(15000, self.tick)

    @staticmethod
    def read_battery():
        try:
            import ctypes.wintypes as wt
            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [("ACLineStatus", wt.BYTE), ("BatteryFlag", wt.BYTE),
                            ("BatteryLifePercent", wt.BYTE), ("Reserved1", wt.BYTE),
                            ("BatteryLifeTime", wt.DWORD), ("BatteryFullLifeTime", wt.DWORD)]
            status = SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                if status.BatteryLifePercent != 255:
                    return f"{status.BatteryLifePercent}%"
        except (OSError, AttributeError):
            pass
        return ""

    def _ahian_state(self):
        try:
            with open(self.ahian_state_file, encoding="utf-8") as handle:
                return handle.read().strip().lower() in ("1", "on", "true", "yes")
        except OSError:
            return False

    def finish_reveal(self):
        """Remove the overlay and leave the live desktop in place."""
        if self._ahian_state():
            self.activate_ahian_desktop()
        try:
            self.taskbar.place(x=12, rely=1.0, y=-58, relwidth=1, width=-24, height=46)
            self.taskbar.lift()
            self.paint_taskbar()
        except (AttributeError, tk.TclError):
            pass
        self.paint_desktop()

    def activate_ahian_desktop(self):
        """Switch the real desktop to AHIAN while the blue screen covers it."""
        self.ahian_mode = True
        self.paint_desktop()
        try:
            self.paint_taskbar()
        except (AttributeError, tk.TclError):
            pass

    def start_intro(self):
        disabled = "--no-animation" in sys.argv
        if os.environ.get("SMTH_NO_STARTUP_ANIMATION", "").strip().lower() in ("1", "on", "true", "yes"):
            disabled = True
        config = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SMTH", "startup-animation")
        try:
            with open(config, encoding="utf-8") as handle:
                if handle.read().strip().lower() in ("0", "off", "false", "no"):
                    disabled = True
        except OSError:
            pass
        self.ahian_mode = self._ahian_state()
        if disabled:
            if not self.ahian_mode:
                self.load_wallpaper()
            self.finish_reveal()
            return
        try:
            if self.ahian_mode:
                # The AHIAN desktop is already running underneath; the windows
                # are drawn over it and the countdown ends on it.
                self.paint_desktop()
                self.intro = AhianConstructionIntro(self)
            else:
                self.load_wallpaper()
                self.intro = ConstructionIntro(self.root, self.display, self.mono)
        except (tk.TclError, OSError):
            self.intro = None
            self.finish_reveal()


class ConstructionIntro:
    """The startup gesture: the SMTH logo fades in, holds, then fades out.

    Nothing else is drawn.  There are no cursors, no panels and no
    reconstruction scene; when the logo has faded out the window closes and
    the live desktop, which was never covered by a rendered copy, is already
    there.  Logo frames are pre-rendered with Pillow so the fade is smooth.
    """

    IN_MS = 620
    HOLD_MS = 980
    OUT_MS = 1560
    DURATION = OUT_MS / 1000.0

    def __init__(self, root, display_font, mono_font):
        self.root = root
        self.display = display_font
        self.mono = mono_font
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg=OBSIDIAN)
        try:
            self.win.attributes("-topmost", True)
            self.win.attributes("-alpha", 1.0)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self.win, bg=OBSIDIAN, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.started = time.monotonic()
        self.after_id = None
        self.closed = False
        self.logo_frames = self._logo_frames()
        self.win.bind("<Button-1>", lambda *_: self.close())
        self.canvas.bind("<Button-1>", lambda *_: self.close())
        self.win.bind("<Escape>", lambda *_: self.close())
        self.root.bind("<Configure>", self.reposition, add="+")
        self.reposition()
        try:
            self.win.update_idletasks()
            self.win.focus_force()
        except tk.TclError:
            pass
        self.tick()

    def _logo_frames(self):
        """The logo at 33 opacity steps; the only artwork the intro draws."""
        path = os.path.join(ASSETS, "logo.png")
        if not HAVE_PIL or not os.path.isfile(path):
            return []
        try:
            art = Image.open(path).convert("RGBA")
            art.thumbnail((148, 148), Image.LANCZOS)
            frames = []
            for index in range(33):
                frame = art.copy()
                scale = index / 32.0
                frame.putalpha(frame.getchannel("A").point(
                    lambda value, k=scale: int(value * k)))
                frames.append(ImageTk.PhotoImage(frame, master=self.root))
            return frames
        except (OSError, ValueError, tk.TclError):
            return []

    def reposition(self, *_):
        if self.closed:
            return
        try:
            self.root.update_idletasks()
            w = max(1, self.root.winfo_width())
            h = max(1, self.root.winfo_height())
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            self.win.geometry(f"{w}x{h}+{x}+{y}")
            self.canvas.configure(width=w, height=h)
        except tk.TclError:
            pass

    def tick(self):
        if self.closed:
            return
        elapsed = time.monotonic() - self.started
        self.draw(min(1.0, elapsed / self.DURATION))
        if elapsed >= self.DURATION:
            self.close()
        else:
            self.after_id = self.root.after(33, self.tick)

    def draw(self, p):
        elapsed_ms = p * self.OUT_MS
        if elapsed_ms < self.IN_MS:
            alpha = 1.0 - (1.0 - elapsed_ms / self.IN_MS) ** 3
        elif elapsed_ms < self.HOLD_MS:
            alpha = 1.0
        else:
            alpha = max(0.0, 1.0 - (elapsed_ms - self.HOLD_MS) / (self.OUT_MS - self.HOLD_MS))
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1 or h <= 1:
            return
        c.create_rectangle(0, 0, w, h, fill=OBSIDIAN, outline="")
        if self.logo_frames and alpha > 0.001:
            index = min(len(self.logo_frames) - 1, int(alpha * (len(self.logo_frames) - 1)))
            c.create_image(w / 2, h / 2, image=self.logo_frames[index])

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.after_id:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        try:
            self.root.focus_force()
        except tk.TclError:
            pass



def main():
    register_bundled_fonts()
    root = tk.Tk()
    SMTHLauncher(root)
    root.mainloop()



# ---- Terminal Window ----

class TerminalWindow:
    """Built-in SMTH Terminal with command support and Ahian mode."""

    def __init__(self, parent):
        self.parent = parent
        self.win = tk.Toplevel(parent.root)
        self.win.title("Terminal")
        self.win.geometry("600x400")
        self.win.minsize(400, 300)
        self.win.configure(bg=OBSIDIAN)
        self.win.transient(parent.root)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        # Terminal state
        self.output = tk.Text(
            self.win, bg=OBSIDIAN, fg=BLUSH, insertbackground=BLUSH,
            font=(parent.mono, 11), relief="flat", bd=0, wrap=tk.WORD,
            highlightthickness=0, state=tk.NORMAL
        )
        self.output.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 4))
        self.output.insert("1.0", "SMTH Terminal\nType 'help' for commands.\n\n")
        self.output.config(state=tk.DISABLED)
        self.output.bind("<Configure>", lambda e: self.output.yview_moveto(1))

        # Input frame
        input_frame = tk.Frame(self.win, bg=OBSIDIAN)
        input_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        self.input = tk.Entry(
            input_frame, bg=MAROON_DEEP, fg=BLUSH, insertbackground=BLUSH,
            font=(parent.mono, 11), relief="flat", bd=0,
            highlightthickness=1, highlightbackground=BLUSH_DIM,
            highlightcolor=BLUSH
        )
        self.input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8))
        self.input.bind("<Return>", lambda e: self.submit())
        self.input.focus_set()

        submit_btn = tk.Button(
            input_frame, text="Enter", command=self.submit,
            bg=OBSIDIAN, fg=BLUSH, activebackground=MAROON,
            activeforeground=BLUSH, relief="flat", bd=0,
            font=(parent.mono, 9), padx=12, cursor="hand2"
        )
        submit_btn.pack(side=tk.RIGHT)

        # Ahian state
        self.ahian_active = bool(parent.ahian_mode)
        self._ahian_intro = None
        if self.ahian_active:
            self.win.configure(bg=AHIAN_DEEP)
            self.output.configure(bg=AHIAN_DEEP, fg="#EDE7FF")
            self.input.configure(bg="#241A3D", fg="#EDE7FF")

    def close(self):
        # Closing Terminal must not turn off a desktop mode that is already active.
        self.win.destroy()

    def submit(self):
        cmd = self.input.get().strip()
        self.input.delete(0, "end")
        if not cmd:
            return

        # Display the command
        self._append(f"❯ {cmd}\n")

        # Process command
        response, is_ahian = get_terminal_response(cmd)
        if response is not None:
            self._append(f"{response}\n")
        elif cmd.lower() == "ahian":
            self.enter_ahian()
        elif cmd.lower() == "unahian":
            self.exit_ahian()
        else:
            self._append(f"command not found: {cmd}\n")

        try:
            self.output.yview_moveto(1)
        except tk.TclError:
            # AHIAN activation deliberately destroys the terminal window.
            pass

    def _append(self, text):
        self.output.config(state=tk.NORMAL)
        self.output.insert("end", text)
        self.output.config(state=tk.DISABLED)

    def enter_ahian(self):
        if self.ahian_active:
            self._append("AHIAN mode already active. Type 'unahian' to exit.\n")
            return

        self.ahian_active = True
        launcher = self.parent
        root = launcher.root
        # Persist the mode, but do not switch the desktop yet: act 1 runs over
        # the desktop that is on screen. The takeover switches the real
        # desktop behind the blue screen, so zero reveals the live AHIAN one.
        try:
            os.makedirs(os.path.dirname(launcher.ahian_state_file), exist_ok=True)
            with open(launcher.ahian_state_file, "w", encoding="utf-8") as handle:
                handle.write("1\n")
        except OSError:
            pass
        # Remove the terminal immediately so no text-entry widget is visible
        # during the takeover.
        try:
            self.win.destroy()
        except tk.TclError:
            pass

        def begin_construction():
            if not root.winfo_exists():
                return
            try:
                launcher._ahian_intro = AhianConstructionIntro(launcher)
            except Exception:
                launcher._ahian_intro = None

        root.after(120, begin_construction)

    def exit_ahian(self):
        if not self.ahian_active:
            self._append("Not in AHIAN mode. Type 'ahian' to enter.\n")
            return

        self.ahian_active = False
        try:
            intro = getattr(self.parent, "_ahian_intro", None)
            if intro is not None and not intro.closed:
                intro.close()
        except Exception:
            pass
        self.parent._ahian_intro = None
        self._ahian_intro = None
        self.parent.ahian_mode = False
        try:
            os.remove(self.parent.ahian_state_file)
        except OSError:
            pass
        self.parent.paint_desktop()
        self.win.configure(bg=OBSIDIAN)
        self.output.configure(bg=OBSIDIAN, fg=BLUSH)
        self.input.configure(bg=MAROON_DEEP, fg=BLUSH)
        self._append("AHIAN mode off — normal experience restored\n")
        self.input.config(state=tk.NORMAL, fg=BLUSH)
        self.input.delete(0, "end")
        self.input.focus_set()



def _mix(a, b, t):
    """Blend two #rrggbb colours; used instead of alpha for Tk canvases."""
    t = max(0.0, min(1.0, t))
    ar, ag, ab = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
    br, bg, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
    return "#%02x%02x%02x" % (
        int(ar + (br - ar) * t), int(ag + (bg - ag) * t), int(ab + (bb - ab) * t))


AHIAN_VOID = "#07080B"
AHIAN_PANEL = "#141822"
AH_WALL_PURPLE = "#07080B"
AH_WALL_TEAL = "#141822"
AHIAN_INK = "#E7ECF5"
AHIAN_COLS = 8
AHIAN_ROWS = 5


def ahian_tint(col, cols=AHIAN_COLS):
    return _mix(AHIAN_PURPLE, AHIAN_TEAL, (col + 0.5) / max(1, cols))


def _flow(u, v, phase=0.0):
    """One sample of the flowing AHIAN gradient, in #rrggbb.

    Mirrors ``flow_colour`` in the shared model: two slow diagonal waves bend a
    purple-to-teal ramp and a narrow band lifts it toward the bright inks.
    Phase 1.0 completes exactly one cycle, so the reveal's last frame matches
    the live desktop at phase 0.
    """
    u = max(0.0, min(1.0, u))
    v = max(0.0, min(1.0, v))
    wave = math.sin((u + v * 0.62) * math.tau + phase * math.tau) * 0.075
    wave += math.sin((u * 1.7 - v * 1.1) * math.tau - phase * math.tau * 2) * 0.035
    band = 0.5 + 0.5 * math.sin((u * 0.8 - v * 0.55) * math.tau - phase * math.tau)
    d = max(0.0, min(1.0, u * 0.58 + v * 0.42 + wave))
    d = d * d * (3 - 2 * d)
    wall = _mix(AH_WALL_PURPLE, AH_WALL_TEAL, d)
    accent = _mix(AHIAN_PURPLE, AHIAN_TEAL, max(0.0, min(1.0, u * 0.7 + v * 0.3)))
    return _mix(wall, accent, 0.035 + 0.075 * band)


def paint_ahian_wallpaper(canvas, w, h, tags=(), phase=0.0):
    """The live AHIAN wallpaper: flowing gradient plus a dot matrix.

    Shared by the desktop canvas and the reconstruction overlay so the final
    animation frame is pixel-identical to the desktop it reveals.
    """
    tile_w = max(1.0, w / AHIAN_COLS)
    tile_h = max(1.0, h / AHIAN_ROWS)
    for row in range(AHIAN_ROWS):
        for col in range(AHIAN_COLS):
            tint = ahian_tint(col)
            wall = _flow((col + 0.5) / AHIAN_COLS, (row + 0.5) / AHIAN_ROWS, phase)
            x0, y0 = col * tile_w, row * tile_h
            canvas.create_rectangle(
                x0, y0, x0 + tile_w + 1, y0 + tile_h + 1,
                fill=wall, outline="", tags=tags)
            sx, sy = tile_w / 4.0, tile_h / 4.0
            dot = _mix(AHIAN_VOID, tint, 0.55)
            for r in range(3):
                for c in range(3):
                    x = x0 + sx * (c + 1)
                    y = y0 + sy * (r + 1)
                    canvas.create_oval(x - 1, y - 1, x + 1, y + 1,
                                       fill=dot, outline="", tags=tags)


def _load_ahian_scene():
    """The shared AHIAN renderer: installed, bundled, or straight from the repo."""
    try:
        import ahian_scene
        return ahian_scene
    except Exception:
        pass
    try:
        import importlib.util
    except Exception:
        return None
    candidates = []
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.append(os.path.join(base, "ahian_scene.py"))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates += [
        os.path.join(here, "ahian_scene.py"),
        os.path.join(here, "..", "..", "config", "includes.chroot_after_packages",
                     "usr", "local", "lib", "smth", "ahian_scene.py"),
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            spec = importlib.util.spec_from_file_location("ahian_scene", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception:
            continue
    return None


def _load_photo_image():
    try:
        from PIL import ImageTk
        return ImageTk
    except Exception:
        return None


class AhianConstructionIntro:
    """The AHIAN takeover, drawn over the launcher's own live desktop.

    There is no second desktop, no temporary screenshot and no Toplevel: each
    frame is an RGBA canvas image placed on top of the real desktop.  Act 1 is
    transparent between the error windows, so the wallpaper, shortcuts and
    taskbar stay visible and untouched.  Act 2 is the opaque AH1AN screen;
    while it covers the display the launcher switches its real desktop to
    AHIAN.  At the countdown's zero the overlay is removed and that live
    desktop is revealed, fully functional.

    The frames come from ``ahian_scene``, the same renderer the ISO overlay
    uses.  Click, any key or Escape ends the takeover immediately; a missing
    renderer reveals the desktop rather than trapping the user.
    """

    def __init__(self, parent_launcher):
        self.parent = parent_launcher
        self.root = parent_launcher.root
        self.canvas = parent_launcher.canvas
        self.closed = True
        self.win = None
        self.after_id = None
        self.image_id = None
        self.photo = None
        self.renderer = None
        self.scene = None
        self.last_draw = -1.0
        self.size = None
        self.applied = bool(parent_launcher.ahian_mode)
        self.reduced = os.environ.get(
            "SMTH_REDUCE_MOTION", "").strip().lower() in ("1", "on", "true", "yes")
        self.module = _load_ahian_scene()
        self.image_tk = _load_photo_image()
        if self.module is None or self.image_tk is None:
            self._reveal()
            return
        self.duration = self.module.M.DURATION_MS / 1000.0
        self.started = time.monotonic()
        self.closed = False
        self.canvas.tag_bind("ahian-intro", "<Button-1>", lambda *_: self.close())
        self.root.bind("<Escape>", lambda *_: self.close(), add="+")
        self.root.bind("<Key>", lambda *_: self.close(), add="+")
        self.root.bind("<Configure>", self.reposition, add="+")
        self.reposition()
        self.tick()

    # ---- plumbing ----------------------------------------------------------
    def _reveal(self):
        try:
            self.parent.finish_reveal()
        except Exception:
            pass

    def _remove_image(self):
        if self.image_id is not None:
            try:
                self.canvas.delete(self.image_id)
            except tk.TclError:
                pass
            self.image_id = None

    def reposition(self, *_):
        if self.closed:
            return
        try:
            self.root.update_idletasks()
            width = max(320, self.root.winfo_width())
            height = max(240, self.root.winfo_height())
        except tk.TclError:
            return
        if self.size != (width, height):
            self.size = (width, height)
            try:
                self.scene = self.module.M.StartupScene(
                    width, height, reduced=self.reduced, profile="windows")
                self.renderer = self.module.SceneRenderer(
                    self.scene, font_dirs=(ASSETS,))
                self.last_draw = -1.0
            except Exception:
                self.scene = None
                self.renderer = None

    def _apply_desktop(self):
        """Switch the real desktop while the blue screen hides it."""
        if self.applied:
            return
        self.applied = True
        try:
            self.parent.taskbar.place_forget()
        except (AttributeError, tk.TclError):
            pass
        try:
            self.parent.activate_ahian_desktop()
        except Exception:
            pass

    def tick(self):
        if self.closed:
            return
        elapsed = time.monotonic() - self.started
        t_ms = min(self.duration * 1000.0, elapsed * 1000.0)
        if t_ms >= self.module.M.BLUE_START_MS + 900:
            self._apply_desktop()
        # 30 fps is plenty for this animation and keeps a weak GPU laptop cool.
        if elapsed - self.last_draw >= 0.030 or t_ms >= self.duration * 1000.0:
            self.draw(t_ms)
            self.last_draw = elapsed
        if t_ms >= self.duration * 1000.0:
            self.close()
        else:
            self.after_id = self.root.after(20, self.tick)

    def draw(self, t_ms):
        if self.renderer is None:
            return
        try:
            image = self.renderer.render(t_ms)
            self.photo = self.image_tk.PhotoImage(image, master=self.root)
            if self.image_id is None:
                self.image_id = self.canvas.create_image(
                    0, 0, anchor="nw", image=self.photo, tags=("ahian-intro",))
            else:
                self.canvas.itemconfig(self.image_id, image=self.photo)
            # The overlay always sits above the live desktop, even if a resize
            # repainted the desktop underneath it.
            self.canvas.tag_raise(self.image_id)
        except Exception:
            # Any renderer failure reveals the desktop instead of a black window.
            self.close()

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.after_id:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None
        self._remove_image()
        self._reveal()
