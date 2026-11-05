"""Launch Prism Converter, independently of the combined Prism application."""
import tkinter as tk
import sys
from tkinter import font as tkfont,ttk
from PrismAbout import APP_NAME,show_about

def main():
    root=tk.Tk();root.title(APP_NAME);root.geometry("1000x960");root.minsize(960,920)
    root.configure(background='#202020')
    # Native Windows ttk themes ignore our custom field backgrounds.
    # Select a fully stylable theme before creating any app controls.
    style=ttk.Style(root);style.theme_use("clam")
    style.configure(".",background='#202020',foreground='#eeeeee')
    style.configure("TEntry",fieldbackground='#202020',foreground='#eeeeee',insertcolor='#eeeeee')
    style.configure("TCombobox",fieldbackground='#202020',foreground='#eeeeee',background='#2d2d2d',arrowcolor='#c4c4c4')
    root.option_add("*TCombobox*Listbox.background",'#202020')
    root.option_add("*TCombobox*Listbox.foreground",'#eeeeee')
    root.option_add("*TCombobox*Listbox.selectBackground",'#c4c4c4')
    root.option_add("*TCombobox*Listbox.selectForeground",'#202020')
    def theme_window(window):
        if sys.platform!="win32":return
        try:
            import ctypes
            from ctypes import wintypes
            get_parent=ctypes.windll.user32.GetParent
            get_parent.argtypes=[wintypes.HWND];get_parent.restype=wintypes.HWND
            hwnd=get_parent(window.winfo_id())
            attribute=ctypes.windll.dwmapi.DwmSetWindowAttribute
            attribute.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
            for key,value in ((20,1),(35,2105376),(36,15658734),(34,8750469)):
                setting=ctypes.c_int(value);attribute(hwnd,key,ctypes.byref(setting),ctypes.sizeof(setting))
        except (AttributeError,OSError,tk.TclError):pass
    root._prism_theme_window=theme_window
    root.bind("<Map>",lambda event:root.after_idle(lambda:theme_window(root)) if event.widget is root else None,add="+")
    families=set(tkfont.families(root))
    family="Ink Free" if "Ink Free" in families else "Segoe Print" if "Segoe Print" in families else "TkDefaultFont"
    for name in ("TkDefaultFont","TkTextFont","TkMenuFont","TkCaptionFont","TkSmallCaptionFont"):
        tkfont.nametofont(name,root=root).configure(family=family,size=13)
    from PrismConverterUI import Converter
    root._converter = app = Converter(root,about_command=lambda:show_about(root))
    root.iconphoto(True,app._header_logo)
    root.mainloop()

if __name__=="__main__":main()
