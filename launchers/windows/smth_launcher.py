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


def main():
    register_bundled_fonts()
    root = tk.Tk()
    SMTHLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
