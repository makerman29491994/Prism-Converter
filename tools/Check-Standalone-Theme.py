"""Regression for white Windows-native fields in the standalone launcher."""
import runpy,sys,tkinter as tk
from pathlib import Path
from tkinter import ttk,messagebox
sys.path.insert(0,str(Path("src").resolve()))
from PrismAbout import APP_VERSION
original_init=tk.Tk.__init__
def native_start(self,*args,**kwargs):
    original_init(self,*args,**kwargs)
    style=ttk.Style(self)
    if "vista" in style.theme_names():style.theme_use("vista")
tk.Tk.__init__=native_start
def descendants(widget):
    for child in widget.winfo_children():yield child;yield from descendants(child)
def check(root):
    root.update();style=ttk.Style(root)
    assert style.theme_use()=="clam"
    assert str(root.cget("menu"))=="", "Native white menu bar returned"
    fields=[w for w in descendants(root) if isinstance(w,(ttk.Entry,ttk.Combobox))]
    assert fields
    for field in fields:
        for state in ((),("readonly",),("focus",)):
            assert style.lookup(field.cget("style"),"fieldbackground",state=state)=='#202020'
            assert style.lookup(field.cget("style"),"foreground",state=state)=='#eeeeee'
    about=next(w for w in descendants(root) if getattr(w,"text",None)=="About")
    assert root._converter.frame.winfo_rooty()-root.winfo_rooty()<=16,'Empty top bar returned'
    assert about.winfo_rooty()-root.winfo_rooty()<=20,'About should share the compact header'
    calls=[];messagebox.showinfo=lambda *args,**kwargs:calls.append(args)
    about.invoke();assert calls and APP_VERSION in calls[0][1]
    for size in ("1000x960","960x920"):
        root.geometry(size);root.update()
        for widget in descendants(root):
            if isinstance(widget,tk.Canvas) and hasattr(widget,"text"):
                assert widget.winfo_rooty()+widget.winfo_height()<=root.winfo_rooty()+root.winfo_height(),widget.text
    root.destroy()
tk.Tk.mainloop=check
runpy.run_path("src/main.py",run_name="__main__")
print("Standalone Windows theme passed: native-theme override, readable fields in all states, dark About control and window bounds.")
