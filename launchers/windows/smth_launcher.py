"""SMTH Launcher for Windows.

A companion shell in the SMTH OS visual language: black surfaces, white text,
grey neutrals, red accent (#D71921), bundled Doto/Space Mono typography and a
drawn dot field. It launches real Windows apps and settings targets; it does not
pretend to be a bootable OS and it does not replace Explorer.

Every action reports its failure in the status bar instead of failing silently.
"""
import ctypes
import datetime
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import font as tkfont

BLACK = "#000000"
WHITE = "#FFFFFF"
GREY = "#8C8C8C"
RED = "#D71921"

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


# Each app: label, launcher target, fallback targets, kind.
# kind: "scheme" -> os.startfile, "exe" -> subprocess, "url" -> webbrowser
APPS = [
    ("Files", "explorer.exe", [], "exe"),
    ("Settings", "ms-settings:", [], "scheme"),
    ("Store", "ms-windows-store:", ["ms-windows-store://home"], "scheme"),
    ("Calculator", "calc.exe", [], "exe"),
    ("Terminal", "wt.exe", ["powershell.exe"], "exe"),
    ("Browser", "https://www.bing.com", [], "url"),
    ("Clock", "ms-clock:", [], "scheme"),
    ("Notepad", "notepad.exe", [], "exe"),
    ("Photos", "ms-photos:", [], "scheme"),
    ("Task Manager", "taskmgr.exe", [], "exe"),
    ("Display settings", "ms-settings:display", [], "scheme"),
    ("Sound settings", "ms-settings:sound", [], "scheme"),
]


class SMTHLauncher:
    def __init__(self, root):
        self.root = root
        root.title("SMTH Launcher")
        root.geometry("780x700")
        root.minsize(520, 560)
        root.configure(bg=BLACK)
        try:
            icon = os.path.join(ASSETS, "smth.ico")
            if os.path.isfile(icon):
                root.iconbitmap(icon)
        except (OSError, tk.TclError):
            pass
        root.bind("<Escape>", lambda *_: root.destroy())
        root.bind("<Control-f>", lambda *_: self.search.focus_set())

        self.mono = self.pick_font(("Space Mono", "Consolas", "Courier New"))
        self.display = self.pick_font(("Doto", "Space Mono", "Segoe UI"))

        self.canvas = tk.Canvas(root, bg=BLACK, highlightthickness=0, bd=0)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.canvas.bind("<Configure>", lambda _e: self.draw_dots())

        body = tk.Frame(root, bg=BLACK)
        body.place(relx=0, rely=0, relwidth=1, relheight=1)

        header = tk.Frame(body, bg=BLACK)
        header.pack(fill="x", padx=24, pady=(22, 6))
        tk.Label(header, text="SMTH", fg=WHITE, bg=BLACK,
                 font=(self.display, 22, "bold")).pack(side="left")
        self.clock = tk.Label(header, fg=RED, bg=BLACK, font=(self.mono, 13))
        self.clock.pack(side="right")
        self.battery = tk.Label(header, fg=GREY, bg=BLACK, font=(self.mono, 9))
        self.battery.pack(side="right", padx=(0, 14))

        self.date = tk.Label(body, fg=GREY, bg=BLACK, font=(self.mono, 9))
        self.date.pack(anchor="w", padx=26)

        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self.draw_apps())
        self.search = tk.Entry(body, textvariable=self.query, bg=BLACK, fg=WHITE,
                               insertbackground=RED, relief="flat", font=(self.mono, 12),
                               highlightthickness=1, highlightbackground=GREY,
                               highlightcolor=RED)
        self.search.pack(fill="x", padx=24, pady=(14, 0), ipady=10)
        self.search.bind("<Return>", lambda *_: self.launch_first())

        tk.Label(body, text="YOUR APPS", fg=RED, bg=BLACK,
                 font=(self.mono, 9)).pack(anchor="w", padx=26, pady=(20, 8))

        self.grid = tk.Frame(body, bg=BLACK)
        self.grid.pack(fill="both", expand=True, padx=20)

        self.status = tk.Label(body, text="", fg=GREY, bg=BLACK, anchor="w",
                               font=(self.mono, 9))
        self.status.pack(fill="x", padx=26, pady=(6, 0))

        footer = tk.Frame(body, bg=BLACK)
        footer.pack(fill="x", padx=24, pady=12)
        self.button(footer, "SETTINGS", lambda: self.launch("ms-settings:", "scheme")).pack(side="left")
        self.button(footer, "POWER", self.power_menu).pack(side="right")

        self.draw_apps()
        self.search.focus_set()
        self.tick()
        self.draw_dots()
        self.intro = None
        # Give the real launcher one frame to map before the construction
        # overlay covers it; the overlay fades away to reveal these widgets.
        self.root.after(120, self.start_intro)

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

    # ---- chrome ----
    def pick_font(self, candidates):
        available = set(tkfont.families(self.root))
        for name in candidates:
            if name in available:
                return name
        return "TkDefaultFont"

    def button(self, parent, label, command):
        return tk.Button(parent, text=label, command=command, bg=BLACK, fg=WHITE,
                         activebackground=RED, activeforeground=WHITE, relief="flat",
                         bd=0, highlightthickness=1, highlightbackground=GREY,
                         font=(self.mono, 9), padx=12, pady=6, cursor="hand2")

    def draw_dots(self):
        self.canvas.delete("dots")
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        step = 22
        for y in range(step, h, step):
            for x in range(step, w, step):
                hot = ((x // step) + (y // step)) % 7 == 0
                self.canvas.create_oval(x - 1, y - 1, x + 1, y + 1,
                                        fill=RED if hot else "#1d1d1d",
                                        outline="", tags="dots")
        self.canvas.tag_lower("dots")

    def tick(self):
        self.clock.config(text=datetime.datetime.now().strftime("%H:%M"))
        self.date.config(text=datetime.datetime.now().strftime("%A, %d %B").upper())
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

    # ---- apps ----
    def matches(self):
        q = self.query.get().strip().lower()
        return [a for a in APPS if not q or q in a[0].lower()]

    def draw_apps(self):
        for child in self.grid.winfo_children():
            child.destroy()
        items = self.matches()
        if not items:
            tk.Label(self.grid, text="No apps match", fg=GREY, bg=BLACK,
                     font=(self.mono, 10)).grid(row=0, column=0, pady=20)
            return
        # Responsive column count instead of a fixed four.
        width = max(self.grid.winfo_width(), 400)
        cols = max(2, min(6, width // 170))
        for i, (name, target, fallbacks, kind) in enumerate(items):
            tile = tk.Frame(self.grid, bg=BLACK, highlightthickness=1,
                            highlightbackground=GREY, bd=0)
            tile.grid(row=i // cols, column=i % cols, padx=5, pady=5, sticky="nsew")
            glyph = tk.Label(tile, text="◆", fg=RED, bg=BLACK, font=(self.display, 20))
            glyph.pack(pady=(12, 2))
            label = tk.Label(tile, text=name, fg=WHITE, bg=BLACK,
                             font=(self.mono, 9), wraplength=140)
            label.pack(pady=(0, 12))
            for widget in (tile, glyph, label):
                widget.bind("<Button-1>", lambda _e, t=target, k=kind, f=fallbacks: self.launch(t, k, f))
                widget.configure(cursor="hand2")
        for c in range(cols):
            self.grid.columnconfigure(c, weight=1)

    def launch_first(self):
        items = self.matches()
        if items:
            self.launch(items[0][1], items[0][3], items[0][2])

    def launch(self, target, kind="exe", fallbacks=()):
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
            self.status.config(text=f"Opened {target}", fg=GREY)
            return
        except (OSError, subprocess.SubprocessError) as first_error:
            for fallback in fallbacks:
                try:
                    if fallback.endswith(":"):
                        os.startfile(fallback)
                    else:
                        subprocess.Popen([fallback], shell=False)
                    self.status.config(text=f"Opened {fallback} (fallback for {target})", fg=GREY)
                    return
                except (OSError, subprocess.SubprocessError):
                    continue
            self.status.config(text=f"Could not open {target}: {first_error}", fg=RED)

    def power_menu(self):
        from tkinter import messagebox
        if not messagebox.askyesno("Power", "Shut down Windows?\n\nCancel leaves the system running.",
                                   parent=self.root):
            self.status.config(text="Shutdown cancelled", fg=GREY)
            return
        try:
            subprocess.Popen(["shutdown", "/s", "/t", "0"], shell=False)
            self.status.config(text="Shutting down…", fg=RED)
        except (OSError, subprocess.SubprocessError) as e:
            self.status.config(text=f"Shutdown failed: {e}", fg=RED)


class ConstructionIntro:
    """Short Windows/desktop adaptation of the ISO startup construction.

    It is a real Tk canvas, not a recording: independent cursors, selection
    boxes and the launcher panels are drawn each frame, then the overlay fades
    away to the already-live launcher below.  Click or Escape skips it.
    """
    DURATION = 5.6
    BLUE = "#2F6BFF"
    CYAN = "#00C2A8"
    PURPLE = "#7C4DFF"
    AMBER = "#FFAD29"
    COLOURS = (RED, BLUE, CYAN, PURPLE, WHITE, AMBER)

    def __init__(self, root, display_font, mono_font):
        self.root = root
        self.display = display_font
        self.mono = mono_font
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg=BLACK)
        try:
            self.win.attributes("-topmost", True)
            self.win.attributes("-alpha", 1.0)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self.win, bg=BLACK, highlightthickness=0, bd=0)
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
            self.root.after(45, lambda: fade(step + 1))

        fade()

    def draw(self, p):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1 or h <= 1:
            return
        c.create_rectangle(0, 0, w, h, fill=BLACK, outline="")
        step = 26
        for y in range(step, h, step):
            for x in range(step, w, step):
                hot = ((x // step) + (y // step)) % 11 == 0
                c.create_oval(x - 1, y - 1, x + 1, y + 1,
                              fill="#221d1d" if hot else "#0d0d0d", outline="")

        # 1. logo reveal (official logo only, no text)
        if p < 0.22:
            fade = min(1.0, p / 0.10) if p < 0.10 else max(0.0, 1 - (p - 0.14) / 0.08)
            if self.logo_photo is not None and fade > 0.02:
                c.create_image(w / 2, h / 2 - 12, image=self.logo_photo)

        # 2/3. panels and selection boxes
        if p >= 0.14:
            self.draw_panels(c, w, h, p)
            boxes = (
                (0.05, 0.025, 0.90, 0.075, 0.16, 0.32, self.BLUE, "TASKBAR"),
                (0.05, 0.145, 0.90, 0.075, 0.23, 0.40, self.CYAN, "SEARCH"),
                (0.05, 0.255, 0.90, 0.47, 0.30, 0.52, self.PURPLE, "APP GRID"),
                (0.26, 0.815, 0.48, 0.095, 0.38, 0.58, RED, "DOCK"),
            )
            for x, y, bw, bh, start, end, colour, label in boxes:
                q = max(0.0, min(1.0, (p - start) / (end - start)))
                if q > 0 and p < 0.86:
                    self.box(c, x * w, y * h, bw * w, bh * h, q, colour, label)

        # 4. independent cursors
        if 0.12 <= p <= 0.88:
            paths = (
                ((0.08, 0.02), (0.24, 0.06), (0.44, 0.16), (0.62, 0.30)),
                ((0.55, 0.00), (0.40, 0.12), (0.55, 0.34), (0.78, 0.26)),
                ((1.00, 0.18), (0.78, 0.24), (0.62, 0.44), (0.38, 0.36)),
                ((0.02, 0.58), (0.20, 0.52), (0.34, 0.68), (0.58, 0.60)),
                ((0.88, 0.90), (0.68, 0.76), (0.46, 0.86), (0.24, 0.78)),
            )
            for i, path in enumerate(paths):
                q = max(0.0, min(1.0, (p - 0.12 - i * 0.025) / 0.72))
                seg = q * (len(path) - 1)
                idx = min(len(path) - 2, int(seg))
                local = seg - idx
                x = (path[idx][0] + (path[idx + 1][0] - path[idx][0]) * local) * w
                y = (path[idx][1] + (path[idx + 1][1] - path[idx][1]) * local) * h
                colour = self.COLOURS[i]
                c.create_polygon(x, y, x, y + 17, x + 4.5, y + 13,
                                 x + 7.2, y + 19, x + 10, y + 17.8,
                                 x + 7.2, y + 11.6, x + 13, y + 11.6,
                                 fill=colour, outline=BLACK, width=1)
                c.create_text(x + 18, y + 15, text=("ARCH", "UI", "LAYOUT", "TYPE", "SYNC")[i],
                              fill=colour, anchor="nw", font=(self.mono, 7))
        c.create_text(w - 18, h - 14, text="CLICK TO SKIP", anchor="se",
                      fill=GREY, font=(self.mono, 8))

    def draw_panels(self, c, w, h, p):
        def panel(x, y, bw, bh, q, accent=GREY):
            if q <= 0:
                return
            x, y, bw, bh = x * w, y * h, bw * w * min(1, q), bh * h
            c.create_rectangle(x, y, x + bw, y + bh, fill=BLACK, outline=accent)
        q = min(1.0, (p - 0.18) / 0.20)
        panel(0.05, 0.03, 0.90, 0.065, q)
        c.create_text(0.075 * w, 0.062 * h, text="SMTH", anchor="w", fill=WHITE,
                      font=(self.display, 12, "bold"))
        c.create_text(0.925 * w, 0.062 * h, text="00:00", anchor="e", fill=RED,
                      font=(self.mono, 10))
        panel(0.05, 0.15, 0.90, 0.065, min(1, (p - 0.22) / 0.18))
        panel(0.05, 0.26, 0.90, 0.47, min(1, (p - 0.28) / 0.26))
        for row in range(2):
            for col in range(4):
                q = min(1.0, (p - 0.31 - (row * 4 + col) * 0.018) / 0.16)
                panel(0.075 + col * 0.215, 0.285 + row * 0.21, 0.18, 0.16, q, self.CYAN)
        panel(0.30, 0.82, 0.40, 0.075, min(1, (p - 0.38) / 0.18), RED)

    def box(self, c, x, y, w, h, progress, colour, label):
        c.create_rectangle(x, y, x + w, y + h, outline=colour, dash=(3, 3))
        perimeter = 2 * (w + h)
        drawn = perimeter * progress
        for x1, y1, x2, y2 in ((x, y, x + w, y), (x + w, y, x + w, y + h),
                               (x + w, y + h, x, y + h), (x, y + h, x, y)):
            length = abs(x2 - x1) + abs(y2 - y1)
            if drawn <= 0:
                break
            f = min(1.0, drawn / max(1.0, length))
            c.create_line(x1, y1, x1 + (x2 - x1) * f, y1 + (y2 - y1) * f,
                          fill=colour, width=2)
            drawn -= length
        c.create_text(x + 3, max(2, y - 10), text=label, anchor="sw",
                      fill=colour, font=(self.mono, 7))


def main():
    register_bundled_fonts()
    root = tk.Tk()
    SMTHLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
