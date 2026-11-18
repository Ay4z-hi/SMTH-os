"""SMTH Launcher for Windows.

A companion desktop shell in the SMTH OS visual language: maroon #701B35,
obsidian #09090B and blush #F2C6D2, the bundled Doto and Space Mono faces, a
custom wallpaper and a small original line-icon set. It launches real Windows
applications and settings targets; it does not replace Explorer.

Every action reports its failure in the status line instead of failing silently.
"""
import ctypes
import datetime
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
]

PINNED = ("Files", "Browser", "Terminal", "Settings", "Calculator", "Photos")


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

        self.canvas = tk.Canvas(root, bg=OBSIDIAN, highlightthickness=0, bd=0)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.canvas.bind("<Configure>", lambda _e: self.paint_desktop())
        self.canvas.bind("<Button-1>", self.on_desktop_click)

        self.build_taskbar()
        self.build_start()

        self.root.after(60, self.load_wallpaper)
        self.tick()
        self.intro = None
        self.root.after(120, self.start_intro)

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
        if self.wallpaper is not None:
            # Tk scales by integer subsampling; crop the overflow to the window.
            factor = max(1, min(self.wallpaper.width() // w, self.wallpaper.height() // h) or 1)
            self._wall = self.wallpaper.subsample(factor, factor) if factor > 1 else self.wallpaper
            img_w, img_h = self._wall.width(), self._wall.height()
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

    def draw_shortcuts(self, w, h):
        c = self.canvas
        entries = [a for a in APPS if a[0] in PINNED][:6]
        rows = min(len(entries), 6)
        for i, (name, target, fallbacks, kind, glyph) in enumerate(entries[:rows]):
            y = 34 + i * 74
            tag = f"shortcut-{i}"
            draw_glyph(c, glyph, 44, y + 20, 30, BLUSH, 1.7, tags=("desktop", tag))
            c.create_text(64, y + 46, text=name, fill=BLUSH, anchor="w",
                          font=(self.mono, 9), tags=("desktop", tag))
            c.tag_bind(tag, "<Button-1>", lambda _e, t=target, k=kind, f=fallbacks: self.launch(t, k, f))
        c.create_text(26, h - 78, text="SMTH OS", fill=BLUSH_DIM, anchor="sw",
                      font=(self.mono, 8), tags="desktop")

    def build_taskbar(self):
        bar = tk.Frame(self.root, bg=SURFACE, height=48)
        bar.place(relx=0, rely=1.0, relwidth=1.0, y=-48, height=48)
        edge = tk.Frame(self.root, bg=MAROON, height=1)
        edge.place(relx=0, rely=1.0, relwidth=1.0, y=-49, height=1)

        start = tk.Frame(bar, bg=SURFACE, cursor="hand2")
        start.pack(side="left", padx=(10, 4), pady=7)
        logo = tk.Canvas(start, width=22, height=22, bg=SURFACE, highlightthickness=0, bd=0)
        logo.pack(side="left")
        draw_glyph(logo, "fallback", 11, 11, 18, BLUSH, 1.4)
        tk.Label(start, text="SMTH", fg=BLUSH, bg=SURFACE,
                 font=(self.display, 10, "bold")).pack(side="left", padx=(6, 8))
        for widget in (start, logo):
            widget.bind("<Button-1>", lambda _e: self.toggle_start())

        search = tk.Frame(bar, bg=MAROON_DEEP, cursor="hand2",
                          highlightthickness=1, highlightbackground=BLUSH_DIM)
        search.pack(side="left", padx=4, pady=9, ipady=4)
        tk.Label(search, text="Search", fg=BLUSH_DIM, bg=MAROON_DEEP,
                 font=(self.mono, 9)).pack(side="left", padx=10)
        for widget in (search, *search.winfo_children()):
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
            draw_glyph(button, app[4], 15, 14, 18, BLUSH, 1.5)
            self.pinned_dot(button, name)
            button.bind("<Button-1>", lambda _e, a=app: self.launch(a[1], a[3], a[2]))

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
            draw_glyph(icon, app[4], 14, 14, 20, BLUSH, 1.5)
            label = tk.Label(cell, text=name, fg=BLUSH, bg=OBSIDIAN, font=(self.mono, 7))
            label.pack()
            for widget in (cell, icon, label):
                widget.bind("<Button-1>", lambda _e, a=app: self.launch_start(a))

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
        self.listbox.bind("<Double-Button-1>", lambda *_: self.launch_selected())
        self.listbox.bind("<Return>", lambda *_: self.launch_selected())

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
            if kind == "url":
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

    def start_intro(self):
        if "--no-animation" in sys.argv:
            return
        if os.environ.get("SMTH_NO_STARTUP_ANIMATION", "").strip().lower() in ("1", "on", "true", "yes"):
            return
        config = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SMTH", "startup-animation")
        try:
            with open(config, encoding="utf-8") as handle:
                if handle.read().strip().lower() in ("0", "off", "false", "no"):
                    return
        except OSError:
            pass
        try:
            self.intro = ConstructionIntro(self.root, self.display, self.mono)
        except tk.TclError:
            self.intro = None


class ConstructionIntro:
    """Short adaptation of the ISO startup construction, in the three palette inks."""

    DURATION = 3.4

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
                self.logo_photo = tk.PhotoImage(file=_logo)
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

    def draw(self, p):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1 or h <= 1:
            return
        c.create_rectangle(0, 0, w, h, fill=OBSIDIAN, outline="")
        step = 24
        for y in range(step, h, step):
            for x in range(step, w, step):
                hot = ((x // step) + (y // step)) % 9 == 0
                c.create_oval(x - 1, y - 1, x + 1, y + 1,
                              fill=MAROON if hot else "#141013", outline="")

        if p < 0.42:
            fade = min(1.0, p / 0.16) if p < 0.16 else max(0.0, 1 - (p - 0.30) / 0.12)
            if self.logo_photo is not None and fade > 0.02:
                c.create_image(w / 2, h / 2 - 10, image=self.logo_photo)

        if p >= 0.36:
            q = max(0.0, min(1.0, (p - 0.36) / 0.34))
            inset = 28
            bottom = h - 72
            c.create_line(inset, bottom, inset + (w - inset * 2) * q, bottom, fill=BLUSH, width=1)
            c.create_text(w - 18, h - 16, text="CLICK TO SKIP", anchor="se",
                          fill=BLUSH_DIM, font=(self.mono, 8))


def main():
    register_bundled_fonts()
    root = tk.Tk()
    SMTHLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
