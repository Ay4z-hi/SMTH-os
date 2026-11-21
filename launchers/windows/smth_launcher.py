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

OBSIDIAN = "#09090B"
MAROON = "#701B35"
BLUSH = "#F2C6D2"
SURFACE = "#0D0B0F"          # obsidian lifted one step for the taskbar
BLUSH_DIM = "#8A7078"        # blush at low emphasis, still within the palette
MAROON_DEEP = "#3A0F1D"
AHIAN_PURPLE = "#7C4DFF"      # improved mode, deliberately outside the palette
AHIAN_DEEP = "#1B1430"
AHIAN_TEAL = "#2BD9C4"

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
        self.reveal_pending = self._ahian_state()

        self.canvas = tk.Canvas(root, bg=OBSIDIAN, highlightthickness=0, bd=0)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.canvas.bind("<Configure>", lambda _e: self.paint_desktop())
        self.canvas.bind("<Button-1>", self.on_desktop_click)

        self.build_taskbar()
        self.build_start()
        if self.reveal_pending:
            # No live taskbar may appear before the reconstruction starts.
            self.taskbar.place_forget()
            self.taskbar_edge.place_forget()

        # Start the overlay before loading any wallpaper. Loading it first
        # exposed the finished wallpaper for a frame before AHIAN cursors ran.
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
        if self.reveal_pending:
            # Nothing of the live desktop may show before the reveal starts.
            c.create_rectangle(0, 0, w, h, fill=AHIAN_VOID, outline="", tags="desktop")
            c.tag_lower("desktop")
            return
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
        """The invisible desktop grid: 112 x 84 cells from (24, 24)."""
        cell_w, cell_h, origin_x, origin_y = 112, 84, 24, 24
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        cols = max(1, int(max(1, width - origin_x - 96) // cell_w) + 1)
        rows = max(1, int(max(1, height - origin_y - 72 - 78) // cell_h) + 1)
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
            cols = max(1, (max(1, w) - 48) // 112)
            default_position = (24 + (i % cols) * 112, 24 + (i // cols) * 84)
            x, y = self.shortcut_positions.get(name, default_position)
            x, y = self.snap_shortcut(name, x, y)
            self.shortcut_positions[name] = (x, y)
            tag = f"shortcut-{i}"
            accent = "#B9A0FF" if self.ahian_mode else BLUSH
            draw_glyph(c, glyph, x, y + 20, 30, accent, 1.7, tags=("desktop", tag))
            c.create_text(x + 20, y + 46, text=name, fill=accent, anchor="w",
                          font=(self.mono, 9), tags=("desktop", tag))
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
        bar = tk.Frame(self.root, bg=SURFACE, height=48)
        bar.place(relx=0, rely=1.0, relwidth=1.0, y=-48, height=48)
        edge = tk.Frame(self.root, bg=MAROON, height=1)
        edge.place(relx=0, rely=1.0, relwidth=1.0, y=-49, height=1)
        self.taskbar = bar
        self.taskbar_edge = edge

        start = tk.Frame(bar, bg=SURFACE, cursor="hand2")
        start.pack(side="left", padx=(10, 4), pady=7)
        logo = tk.Canvas(start, width=30, height=30, bg=SURFACE, highlightthickness=0, bd=0)
        logo.pack(side="left")
        draw_glyph(logo, "fallback", 15, 15, 24, BLUSH, 1.6)
        # The logo opens search; there is no separate Search button.
        for widget in (start, logo):
            widget.bind("<Button-1>", lambda _e: self.open_start(focus=True))

        self.pinned_bar = tk.Frame(bar, bg=SURFACE)
        self.pinned_bar.pack(side="left", padx=8)
        for name in PINNED[:5]:
            app = next((a for a in APPS if a[0] == name), None)
            if not app: continue
            button = tk.Canvas(self.pinned_bar, width=30, height=30, bg=SURFACE,
                               highlightthickness=0, bd=0, cursor="hand2")
            button.smth_name = name
            button.pack(side="left", padx=1)
            if app[3] == "smth_terminal":
                # Draw terminal glyph for built-in terminal
                draw_glyph(button, "terminal", 15, 14, 18, BLUSH, 1.5)
                button.bind("<Button-1>", lambda _e, a=app: self.launch(a[0], a[3]))
            else:
                draw_glyph(button, app[4], 15, 14, 18, BLUSH, 1.5)
                button.bind("<Button-1>", lambda _e, a=app: self.launch(a[1], a[3], a[2]))
            self.pinned_dot(button, name)

        tray = tk.Frame(bar, bg=SURFACE)
        tray.pack(side="right", padx=(4, 12))
        self.battery = tk.Label(tray, fg=BLUSH_DIM, bg=SURFACE, font=(self.mono, 8))
        self.battery.pack(side="right", padx=(10, 0))
        clock_box = tk.Frame(tray, bg=SURFACE)
        clock_box.pack(side="right")
        self.clock = tk.Label(clock_box, fg=BLUSH, bg=SURFACE, font=(self.mono, 10))
        self.clock.pack(anchor="e")
        self.date = tk.Label(clock_box, fg=BLUSH_DIM, bg=SURFACE, font=(self.mono, 8))
        self.date.pack(anchor="e")

    def pinned_dot(self, canvas, name):
        canvas.delete("run")
        if name in self.recent:
            canvas.create_oval(13, 27, 17, 31, fill=BLUSH, outline="", tags="run")

    def build_start(self):
        self.panel = tk.Frame(self.root, bg=OBSIDIAN, highlightthickness=1,
                              highlightbackground=MAROON, bd=0)
        body = tk.Frame(self.panel, bg=OBSIDIAN)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        head = tk.Frame(body, bg=OBSIDIAN)
        head.pack(fill="x")
        tk.Label(head, text="SMTH", fg=BLUSH, bg=OBSIDIAN,
                 font=(self.display, 14, "bold")).pack(side="left")
        tk.Label(head, text="START", fg=BLUSH_DIM, bg=OBSIDIAN,
                 font=(self.mono, 7)).pack(side="right", pady=(8, 0))

        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self.filter_start())
        self.search = tk.Entry(body, textvariable=self.query, bg=MAROON_DEEP, fg=BLUSH,
                               insertbackground=BLUSH, relief="flat", font=(self.mono, 10),
                               highlightthickness=1, highlightbackground=BLUSH_DIM,
                               highlightcolor=BLUSH)
        self.search.pack(fill="x", pady=(10, 0), ipady=6)
        self.search.bind("<Return>", lambda *_: self.launch_first())
        self.search.bind("<Escape>", lambda *_: self.close_start())
        self.search.bind("<Down>", lambda *_: self.focus_list())

        tk.Label(body, text="PINNED", fg=BLUSH_DIM, bg=OBSIDIAN,
                 font=(self.mono, 7)).pack(anchor="w", pady=(12, 4))
        self.pin_row = tk.Frame(body, bg=OBSIDIAN)
        self.pin_row.pack(fill="x")
        for name in PINNED[:6]:
            app = next((a for a in APPS if a[0] == name), None)
            if not app: continue
            cell = tk.Frame(self.pin_row, bg=OBSIDIAN, cursor="hand2")
            cell.pack(side="left", padx=(0, 4))
            icon = tk.Canvas(cell, width=28, height=28, bg=OBSIDIAN, highlightthickness=0, bd=0)
            icon.pack()
            label = tk.Label(cell, text=name, fg=BLUSH, bg=OBSIDIAN, font=(self.mono, 7))
            if app[3] == "smth_terminal":
                # Draw terminal glyph for built-in terminal
                draw_glyph(icon, "terminal", 14, 14, 20, BLUSH, 1.5)
                for widget in (cell, icon, label):
                    widget.bind("<Button-1>", lambda _e, a=app: self.launch_start(a))
            else:
                draw_glyph(icon, app[4], 14, 14, 20, BLUSH, 1.5)
                for widget in (cell, icon, label):
                    widget.bind("<Button-1>", lambda _e, a=app: self.launch_start(a))
            label.pack()

        tk.Label(body, text="ALL APPLICATIONS", fg=BLUSH_DIM, bg=OBSIDIAN,
                 font=(self.mono, 7)).pack(anchor="w", pady=(12, 2))
        self.all_frame = tk.Frame(body, bg=OBSIDIAN)
        self.all_frame.pack(fill="both", expand=True)
        self.draw_all_apps()

        foot = tk.Frame(body, bg=OBSIDIAN)
        foot.pack(fill="x", pady=(8, 0))
        self.status = tk.Label(foot, text="", fg=BLUSH_DIM, bg=OBSIDIAN, anchor="w",
                               font=(self.mono, 8))
        self.status.pack(side="left", fill="x", expand=True)
        self.pill(foot, "SETTINGS", lambda: self.launch("ms-settings:", "scheme")).pack(side="right", padx=(4, 0))
        self.pill(foot, "POWER", self.power_menu).pack(side="right")

    def pill(self, parent, label, command):
        return tk.Button(parent, text=label, command=command, bg=OBSIDIAN, fg=BLUSH,
                         activebackground=MAROON, activeforeground=BLUSH, relief="flat",
                         bd=0, highlightthickness=1, highlightbackground=BLUSH_DIM,
                         font=(self.mono, 7), padx=10, pady=4, cursor="hand2")

    def draw_all_apps(self):
        for child in self.all_frame.winfo_children():
            child.destroy()
        self.listbox = tk.Listbox(self.all_frame, bg=OBSIDIAN, fg=BLUSH, selectbackground=MAROON,
                                  selectforeground=BLUSH, relief="flat", bd=0,
                                  highlightthickness=0, font=(self.mono, 9), activestyle="none")
        scroll = tk.Scrollbar(self.all_frame, command=self.listbox.yview, width=6,
                              bg=SURFACE, troughcolor=OBSIDIAN, activebackground=MAROON,
                              relief="flat", bd=0)
        self.listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)
        for app in APPS:
            self.listbox.insert("end", f"  {app[0]}")
        # Bind double-click and Enter to launch
        self.listbox.bind("<Double-Button-1>", lambda *_: self.launch_selected())
        self.listbox.bind("<Return>", lambda *_: self.launch_selected())
        # Also launch on double-click via listbox binding
        self.listbox.bind("<Double-1>", lambda e: self.launch_selected())

    def filter_start(self):
        q = self.query.get().strip().lower()
        self.listbox.delete(0, "end")
        for app in APPS:
            if not q or q in app[0].lower():
                self.listbox.insert("end", f"  {app[0]}")
        for child in self.pin_row.winfo_children():
            child.pack_forget()
        if not q:
            for child in self.pin_row.winfo_children():
                child.pack(side="left", padx=(0, 4))

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
        self.panel.place(x=12, y=h - 58 - panel_h + 14, width=panel_w, height=panel_h)
        self.panel.lift()
        self.slide(14, target=0)
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
        if self.listbox.size():
            self.listbox.focus_set()
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(0)

    # ---- apps -----------------------------------------------------------
    def launch_selected(self):
        selection = self.listbox.curselection()
        name = self.listbox.get(selection[0]).strip() if selection else ""
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
            for child in self.pinned_bar.winfo_children():
                self.pinned_dot(child, getattr(child, "smth_name", ""))
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
        self.clock.config(text=now.strftime("%H:%M"))
        self.date.config(text=now.strftime("%a %d %b").upper())
        self.battery.config(text=self.read_battery())
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
        """Put the live desktop (and its taskbar) back under the overlay."""
        self.reveal_pending = False
        if self.ahian_mode:
            try:
                self.taskbar.place(relx=0, rely=1.0, relwidth=1.0, y=-48, height=48)
                self.taskbar_edge.place(relx=0, rely=1.0, relwidth=1.0, y=-49, height=1)
                self.taskbar.lift()
                self.taskbar_edge.lift()
            except (AttributeError, tk.TclError):
                pass
        self.paint_desktop()

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
            self.reveal_pending = False
            if not self.ahian_mode:
                self.load_wallpaper()
            self.finish_reveal()
            return
        try:
            if self.ahian_mode:
                self.reveal_pending = True
                self.paint_desktop()
                self.intro = AhianConstructionIntro(self)
            else:
                self.load_wallpaper()
                self.intro = ConstructionIntro(self.root, self.display, self.mono)
        except (tk.TclError, OSError):
            self.intro = None
            self.finish_reveal()


class ConstructionIntro:
    """Short adaptation of the ISO startup construction, in the three palette inks."""

    DURATION = 9.6

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
        self.logo_photo = None
        try:
            _logo = os.path.join(ASSETS, "logo.png")
            if os.path.isfile(_logo):
                original_logo = tk.PhotoImage(file=_logo)
                self.logo_photo = original_logo.subsample(3, 3)
        except tk.TclError:
            self.logo_photo = None
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

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.after_id:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass

        def fade(step=0):
            if step >= 6:
                try:
                    self.win.destroy()
                except tk.TclError:
                    pass
                try:
                    self.root.focus_force()
                except tk.TclError:
                    pass
                return
            try:
                self.win.attributes("-alpha", max(0.0, 1.0 - step / 6))
            except tk.TclError:
                try:
                    self.win.destroy()
                except tk.TclError:
                    pass
                return
            self.root.after(40, lambda: fade(step + 1))

        fade()

    @staticmethod
    def _fade_colour(colour, background, amount):
        amount = max(0.0, min(1.0, amount))
        a = tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
        b = tuple(int(background[i:i + 2], 16) for i in (1, 3, 5))
        values = [round(b[i] + (a[i] - b[i]) * amount) for i in range(3)]
        return "#" + "".join(f"{value:02X}" for value in values)

    def draw(self, p):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1 or h <= 1:
            return
        # AHIAN's purple-to-teal wallpaper is revealed progressively.
        wallpaper_mix = min(1.0, max(0.0, p * 1.4))
        purple_rgb = (124, 77, 255)
        teal_rgb = (0, 194, 168)
        for y in range(0, h, 12):
            for x in range(0, w, 12):
                mix = min(1.0, max(0.0, (x / max(1, w) * 0.58 + y / max(1, h) * 0.42)))
                target = tuple(round(purple_rgb[i] * (1 - mix) + teal_rgb[i] * mix) for i in range(3))
                colour = tuple(round(v * wallpaper_mix) for v in target)
                c.create_rectangle(x, y, x + 12, y + 12,
                                   fill="#%02X%02X%02X" % colour, outline="")
        step = 24
        for y in range(step, h, step):
            for x in range(step, w, step):
                hot = ((x // step) + (y // step)) % 9 == 0
                c.create_oval(x - 1, y - 1, x + 1, y + 1,
                              fill="#33E5CC" if hot else "#201A35", outline="")

        if p < 0.42:
            fade = min(1.0, p / 0.16) if p < 0.16 else max(0.0, 1 - (p - 0.30) / 0.12)
            if self.logo_photo is not None and fade > 0.02:
                c.create_image(w / 2, h / 2 - 10, image=self.logo_photo)

        if p >= 0.36:
            q = max(0.0, min(1.0, (p - 0.36) / 0.56))
            fade = max(0.0, min(1.0, (1.0 - q) / 0.12)) if q > 0.88 else 1.0
            task_y = h - 62
            # Layout guides are drawn first, then panels grow into their measured bounds.
            if q > 0.04:
                c.create_rectangle(12, task_y, w - 12, h - 10, outline="#00C2A8")
            if q > 0.16:
                c.create_rectangle(30, 42, 30 + int(w * 0.24 * min(1, (q - 0.16) / 0.35)),
                                   42 + int((h - 125) * min(1, (q - 0.16) / 0.35)),
                                   outline="#00C2A8")
            if q > 0.24:
                c.create_rectangle(int(w * 0.35), int(h * 0.16),
                                   int(w * 0.35 + w * 0.60 * min(1, (q - 0.24) / 0.42)),
                                   int(h * 0.16 + h * 0.58 * min(1, (q - 0.24) / 0.42)),
                                   outline="#7C4DFF")
            if q > 0.30:
                c.create_rectangle(30, 42, 30 + int(w * 0.24), h - 83,
                                   fill="#171020", outline="#2BD9C4")
                c.create_rectangle(int(w * 0.35), int(h * 0.16),
                                   int(w * 0.95), int(h * 0.74),
                                   fill="#100D18", outline="#7C4DFF")
                c.create_rectangle(12, task_y, w - 12, h - 10,
                                   fill="#100D18", outline="#2BD9C4")
                for i in range(6):
                    if q > 0.42 + i * 0.035:
                        x, y = 52 + (i % 2) * 54, 64 + (i // 2) * 58
                        c.create_rectangle(x, y, x + 22, y + 22,
                                           fill=("#7C4DFF", "#00C2A8")[i % 2], outline="")
            paths = [
                [(0.02, -0.04), (0.25, 0.30), (0.42, 0.18), (0.78, 0.24)],
                [(1.04, 0.22), (0.78, 0.42), (0.54, 0.32), (0.62, 0.72)],
                [(0.42, -0.04), (0.34, 0.34), (0.18, 0.52), (0.12, 0.82)],
                [(-0.04, 0.72), (0.28, 0.70), (0.52, 0.82), (0.88, 0.82)],
                [(0.84, 1.04), (0.72, 0.72), (0.82, 0.42), (0.92, 0.20)],
                [(0.18, 1.04), (0.32, 0.76), (0.42, 0.50), (0.36, 0.26)],
                [(1.04, 0.90), (0.78, 0.78), (0.62, 0.54), (0.44, 0.46)],
            ]
            colours = ["#7C4DFF", "#00C2A8", "#9E75FF", "#33E5CC", "#5738A0", "#65EBD5", "#B69AFF"]
            for i, points in enumerate(paths):
                local = max(0.0, min(1.0, (q - i * 0.025) / 0.86))
                if local <= 0 or q > 0.96:
                    continue
                segf = local * (len(points) - 1)
                seg = min(len(points) - 2, int(segf))
                u = segf - seg
                u = 1 - (1 - u) ** 3
                ax, ay = points[seg]
                bx, by = points[seg + 1]
                x, y = (ax + (bx - ax) * u) * w, (ay + (by - ay) * u) * h
                c.create_oval(x - 3, y - 3, x + 3, y + 3, fill=colours[i], outline="")
                c.create_polygon(x, y, x, y + 18, x + 5, y + 13, x + 9, y + 20,
                                 x + 12, y + 18, x + 8, y + 12, x + 15, y + 12,
                                 fill=colours[i], outline="#000000")
            c.create_text(w - 18, h - 16, text="CLICK TO SKIP", anchor="se",
                          fill=BLUSH_DIM, font=(self.mono, 8))


def main():
    register_bundled_fonts()
    root = tk.Tk()
    SMTHLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()


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
        launcher.ahian_mode = True
        try:
            os.makedirs(os.path.dirname(launcher.ahian_state_file), exist_ok=True)
            with open(launcher.ahian_state_file, "w", encoding="utf-8") as handle:
                handle.write("1\n")
        except OSError:
            pass
        launcher.paint_desktop()
        # Remove the terminal immediately. The reconstruction starts only after
        # a 2.5-second clean pause, with no terminal or text-entry widget visible.
        try:
            self.win.destroy()
        except tk.TclError:
            pass

        def begin_construction():
            if not root.winfo_exists() or not launcher.ahian_mode:
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


AHIAN_VOID = "#07060D"
AHIAN_PANEL = "#150F25"
AH_WALL_PURPLE = "#2A174D"
AH_WALL_TEAL = "#054740"
AHIAN_INK = "#EDE7FF"
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


class AhianConstructionIntro:
    """AHIAN desktop reconstruction overlay (~9 s), the same timeline as the
    Linux ISO and the Android launcher.

    0-1 s  dark field with purple/teal fragments
    1-3 s  the wallpaper assembles from dot-matrix geometric tiles
    3-5 s  taskbar segments, clock and widgets draw themselves in
    5-7 s  desktop icons materialise in their real positions, a window builds
           and dissolves again
    7-9 s  the finished desktop is revealed; the overlay is already sitting on
           the real launcher, so nothing reloads or flashes behind it.

    There are no cursors in this sequence.
    """

    DURATION = 9.0
    ICONS = (("Files", "folder"), ("Browser", "globe"), ("Terminal", "terminal"),
             ("Settings", "gear"), ("Calculator", "calc"), ("Photos", "photo"))
    RING_STARTS = (1.05, 1.40, 1.75, 2.10)

    def __init__(self, parent_launcher):
        self.parent = parent_launcher
        self.root = parent_launcher.root
        self.mono = parent_launcher.mono
        self.closed = True
        if os.environ.get("SMTH_REDUCE_MOTION", "").strip().lower() in ("1", "on", "true", "yes"):
            try:
                parent_launcher.finish_reveal()
            except Exception:
                pass
            return
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.configure(bg=AHIAN_VOID)
        try:
            self.win.attributes("-topmost", True)
            self.win.attributes("-alpha", 1.0)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self.win, bg=AHIAN_VOID, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.started = time.monotonic()
        self.after_id = None
        self.closed = False
        # Deterministic fragments, so the reveal looks designed, not random.
        rng = __import__("random").Random(1107)
        self.fragments = [
            (rng.uniform(0.02, 0.98), rng.uniform(0.02, 0.98),
             rng.uniform(-0.012, 0.012), rng.uniform(-0.020, -0.006),
             rng.choice((AHIAN_PURPLE, AHIAN_TEAL, "#9E75FF", "#33E5CC")))
            for _ in range(36)
        ]
        self.root.bind("<Configure>", self.reposition, add="+")
        self.reposition()
        self.tick()

    def reposition(self, *_):
        if self.closed:
            return
        try:
            self.root.update_idletasks()
            w = max(1, self.root.winfo_width())
            h = max(1, self.root.winfo_height())
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
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
            self.parent.finish_reveal()
        except Exception:
            pass

        def fade(step=0):
            if step >= 8:
                try:
                    self.win.destroy()
                except tk.TclError:
                    pass
                try:
                    self.parent.finish_reveal()
                except Exception:
                    pass
                return
            try:
                self.win.attributes("-alpha", max(0.0, 1.0 - step / 8.0))
            except tk.TclError:
                try:
                    self.win.destroy()
                except tk.TclError:
                    pass
                return
            self.root.after(36, lambda: fade(step + 1))

        try:
            self.parent.finish_reveal()
        except Exception:
            pass
        fade()

    # ---- helpers ------------------------------------------------------------
    @staticmethod
    def _ease(v):
        v = max(0.0, min(1.0, v))
        return 1.0 - (1.0 - v) ** 3

    def _draw_wallpaper(self, c, w, h, t):
        tile_w = w / AHIAN_COLS
        tile_h = h / AHIAN_ROWS
        for row in range(AHIAN_ROWS):
            for col in range(AHIAN_COLS):
                order = (col / max(1, AHIAN_COLS - 1)) * 0.58 + \
                        (row / max(1, AHIAN_ROWS - 1)) * 0.42
                start = 1.0 + order * 1.4
                progress = (t - start) / 0.48
                if progress <= 0:
                    continue
                a = self._ease(progress)
                tint = ahian_tint(col)
                wall = _flow((col + 0.5) / AHIAN_COLS, (row + 0.5) / AHIAN_ROWS,
                             min(1.0, t / self.DURATION))
                x0, y0 = col * tile_w, row * tile_h
                c.create_rectangle(
                    x0, y0, x0 + tile_w + 1, y0 + tile_h + 1,
                    fill=_mix(AHIAN_VOID, wall, a), outline="")
                if a > 0.55:
                    sx, sy = tile_w / 4.0, tile_h / 4.0
                    dot = _mix(AHIAN_VOID, tint, 0.55 * a)
                    for r in range(3):
                        for cc in range(3):
                            x = x0 + sx * (cc + 1)
                            y = y0 + sy * (r + 1)
                            c.create_oval(x - 1, y - 1, x + 1, y + 1,
                                          fill=dot, outline="")

    def _draw_rings(self, c, w, h, t):
        cx, cy = w * 0.5, h * 0.48
        base = min(w, h)
        for i, start in enumerate(self.RING_STARTS):
            progress = (t - start) / 1.25
            if progress <= 0 or progress >= 1:
                continue
            radius = base * (0.05 + 0.42 * (progress * progress * (3 - 2 * progress)))
            outline = _mix(AHIAN_VOID, _mix(AHIAN_PURPLE, AHIAN_TEAL, i / 3.0),
                           (1 - progress) * 0.42)
            c.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                          outline=outline, width=1)

    def _draw_fragments(self, c, w, h, t):
        if t > 3.4:
            return
        alpha = max(0.0, min(1.0, t / 0.42)) * max(0.0, min(1.0, (3.4 - t) / 0.9))
        for fx, fy, vx, vy, colour in self.fragments:
            x = (fx + vx * t) % 1.0
            y = (fy + vy * t) % 1.0
            c.create_oval(x * w - 2, y * h - 2, x * w + 2, y * h + 2,
                          fill=_mix(AHIAN_VOID, colour, 0.5 * alpha), outline="")

    def _draw_chrome(self, c, w, h, t):
        # ---- taskbar -------------------------------------------------------
        bar_top = h - 49
        progress = self._ease((t - 3.0) / 0.62)
        if progress > 0:
            c.create_rectangle(0, bar_top, w, h,
                               fill=_mix(AHIAN_VOID, AHIAN_PANEL, 0.92 * progress),
                               outline="")
            c.create_line(0, bar_top, w * progress, bar_top,
                          fill=_mix(AHIAN_VOID, AHIAN_PURPLE, 0.9))
            # text
            c.create_text(14, bar_top + 24, text="SMTH", anchor="w",
                          fill=_mix(AHIAN_VOID, AHIAN_INK, progress),
                          font=(self.mono, 9))
            c.create_text(w - 14, bar_top + 16,
                          text=datetime.datetime.now().strftime("%H:%M"), anchor="e",
                          fill=_mix(AHIAN_VOID, AHIAN_TEAL, progress),
                          font=(self.mono, 9))
            c.create_text(w - 14, bar_top + 32,
                          text=datetime.datetime.now().strftime("%a %d %b").upper(),
                          anchor="e", fill=_mix(AHIAN_VOID, "#8C879C", progress),
                          font=(self.mono, 7))
            # segments assemble in order
            fractions = (0.085, 0.095, 0.095, 0.095, 0.11, 0.16)
            x = 8
            usable = w - 16
            for i, fraction in enumerate(fractions):
                seg = max(18, usable * fraction)
                seg_progress = max(0.0, min(1.0, (t - (3.0 + i * 0.11)) / 0.36))
                if seg_progress > 0:
                    colour = (AHIAN_PURPLE, AHIAN_TEAL, "#9E75FF")[i % 3]
                    c.create_rectangle(
                        x, bar_top + 9, x + seg * seg_progress, h - 9,
                        fill=_mix(AHIAN_VOID, colour, 0.55 * seg_progress),
                        outline="")
                x += seg + 8
        # ---- desktop icons, at the launcher's real positions ----------------
        for i, (name, _glyph) in enumerate(self.ICONS):
            start = 5.0 + i * 0.14
            local = max(0.0, min(1.0, (t - start) / 0.38))
            if local <= 0:
                continue
            a = self._ease(local)
            # Same grid as draw_shortcuts(), so the icons land exactly where
            # the live desktop draws them when the overlay fades.
            cols = max(1, (max(1, w) - 48) // 112)
            x = 24 + (i % cols) * 112
            y = 24 + (i // cols) * 84
            tint = (AHIAN_PURPLE, AHIAN_TEAL, "#9E75FF",
                    "#33E5CC", "#5738A0", AHIAN_PURPLE)[i % 6]
            # dot-matrix app mark
            for r in range(3):
                for cc in range(3):
                    if (r + cc + i) % 4 == 3:
                        continue
                    gx = x - 5 + cc * 5
                    yy = y + 8 + r * 5
                    c.create_oval(gx - 1, yy - 1, gx + 1, yy + 1,
                                  fill=_mix(AHIAN_VOID, tint, 0.9 * a), outline="")
            c.create_text(x + 20, y + 46, text=name, anchor="w",
                          fill=_mix(AHIAN_VOID, AHIAN_INK, a),
                          font=(self.mono, 9))
        # ---- one window builds itself, then dissolves ----------------------
        local = max(0.0, min(1.0, (t - 5.28) / 0.9))
        fade = max(0.0, min(1.0, (6.9 - t) / 0.42)) if t > 6.5 else 1.0
        if local > 0 and fade > 0:
            a = self._ease(local) * fade
            x0, y0 = w * 0.29, h * 0.17
            x1, y1 = w * 0.73, h * 0.69
            c.create_rectangle(x0, y0, x1, y1,
                               fill=_mix(AHIAN_VOID, AHIAN_PANEL, 0.9 * a),
                               outline=_mix(AHIAN_VOID, AHIAN_PURPLE, 0.6 * a))
            c.create_rectangle(x0, y0, x1, y0 + 28,
                               fill=_mix(AHIAN_VOID, "#000000", 0.55 * a), outline="")
            for i, colour in enumerate((AHIAN_PURPLE, AHIAN_TEAL, "#9E75FF")):
                c.create_oval(x0 + 14 + i * 14 - 3, y0 + 11,
                              x0 + 14 + i * 14 + 3, y0 + 17,
                              fill=_mix(AHIAN_VOID, colour, a), outline="")
            c.create_text(x0 + 66, y0 + 14, text="SMTH / WINDOW", anchor="w",
                          fill=_mix(AHIAN_VOID, AHIAN_INK, a),
                          font=(self.mono, 8))
            c.create_text(x0 + 18, y0 + 52, text="DESKTOP RECONSTRUCTION", anchor="w",
                          fill=_mix(AHIAN_VOID, AHIAN_INK, a),
                          font=(self.mono, 9))
            for i in range(4):
                yy = y0 + 74 + i * 20
                if yy > y1 - 70:
                    break
                c.create_rectangle(
                    x0 + 18, yy, x0 + 18 + (x1 - x0 - 36) * (0.78 - i * 0.12), yy + 4,
                    fill=_mix(AHIAN_VOID, AHIAN_TEAL if i == 0 else AHIAN_PURPLE,
                              (0.5 if i == 0 else 0.22) * a), outline="")
            base = y1 - 18
            for i in range(14):
                height = 56 * (0.22 + 0.7 * ((i * 7) % 11) / 10)
                bx = x0 + 18 + i * ((x1 - x0 - 36) / 16)
                c.create_rectangle(
                    bx, base - height, bx + (x1 - x0 - 36) / 26,
                    base, fill=_mix(AHIAN_VOID,
                                    AHIAN_TEAL if i % 3 == 0 else "#9E75FF",
                                    (0.55 if i % 3 == 0 else 0.25) * a), outline="")

    def draw(self, p):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1 or h <= 1:
            return
        t = p * self.DURATION
        c.create_rectangle(0, 0, w, h, fill=AHIAN_VOID, outline="")
        self._draw_wallpaper(c, w, h, t)
        self._draw_rings(c, w, h, t)
        self._draw_fragments(c, w, h, t)
        self._draw_chrome(c, w, h, t)


