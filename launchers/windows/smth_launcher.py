import tkinter as tk
from tkinter import messagebox
import datetime, os, subprocess, sys, webbrowser

BLACK="#000000"; ORANGE="#FF7A00"; BLUE="#2F6BFF"; WHITE="#FFFFFF"
APPS=[
 ("Files","explorer.exe"),("Browser","https://www.google.com"),("Store","ms-windows-store:"),
 ("Settings","ms-settings:"),("Calculator","calc.exe"),("Terminal","wt.exe"),
 ("Photos","ms-photos:"),("Clock","ms-clock:")
]
class SMTHLauncher:
 def __init__(self,root):
  self.root=root; root.title("SMTH Launcher"); root.geometry("720x680"); root.configure(bg=BLACK); root.minsize(520,560)
  self.query=tk.StringVar(); self.query.trace_add("write",lambda *_:self.draw_apps())
  top=tk.Frame(root,bg=BLACK); top.pack(fill="x",padx=24,pady=(22,8))
  tk.Label(top,text="△ SMTH",fg=WHITE,bg=BLACK,font=("Segoe UI",22,"bold")).pack(side="left")
  self.clock=tk.Label(top,fg=ORANGE,bg=BLACK,font=("Consolas",13)); self.clock.pack(side="right")
  self.tick()
  tk.Label(root,text=datetime.datetime.now().strftime("%A, %d %B"),fg=WHITE,bg=BLACK,font=("Segoe UI",11)).pack(anchor="w",padx=26,pady=(0,18))
  e=tk.Entry(root,textvariable=self.query,bg=BLACK,fg=WHITE,insertbackground=ORANGE,relief="flat",font=("Segoe UI",13),highlightthickness=1,highlightbackground=BLUE); e.pack(fill="x",padx=24,ipady=12)
  tk.Label(root,text="YOUR APPS",fg=ORANGE,bg=BLACK,font=("Segoe UI",9,"bold")).pack(anchor="w",padx=26,pady=(22,10))
  self.grid=tk.Frame(root,bg=BLACK); self.grid.pack(fill="both",expand=True,padx=20)
  self.draw_apps()
  bottom=tk.Frame(root,bg=BLACK); bottom.pack(fill="x",padx=24,pady=16)
  tk.Button(bottom,text="SETTINGS",command=lambda:webbrowser.open("ms-settings:"),bg=BLACK,fg=WHITE,activebackground=ORANGE,relief="flat").pack(side="left")
  tk.Button(bottom,text="POWER",command=self.power,bg=BLACK,fg=WHITE,activebackground=ORANGE,relief="flat").pack(side="right")
 def tick(self):
  self.clock.config(text=datetime.datetime.now().strftime("%H:%M:%S")); self.root.after(1000,self.tick)
 def draw_apps(self):
  for w in self.grid.winfo_children(): w.destroy()
  matches=[a for a in APPS if self.query.get().lower() in a[0].lower()]
  for i,(name,target) in enumerate(matches):
   b=tk.Button(self.grid,text="◇\n"+name,command=lambda t=target:self.launch(t),bg=BLACK,fg=WHITE,activebackground=BLUE,activeforeground=WHITE,relief="solid",bd=1,highlightbackground=BLUE,font=("Segoe UI",12),width=15,height=4)
   b.grid(row=i//4,column=i%4,padx=6,pady=6,sticky="nsew")
  for c in range(4): self.grid.columnconfigure(c,weight=1)
 def launch(self,target):
  try:
   if target.startswith("http"): webbrowser.open(target)
   elif target.endswith(":"): os.startfile(target)
   else: subprocess.Popen(target,shell=False)
  except Exception as e: messagebox.showerror("SMTH Launcher",str(e))
 def power(self):
  if messagebox.askyesno("Power","Shut down Windows?"): os.system("shutdown /s /t 0")
if __name__=="__main__":
 root=tk.Tk(); SMTHLauncher(root); root.mainloop()
