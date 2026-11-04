"""Launch Prism Converter, independently of the combined Prism application."""
import tkinter as tk
from tkinter import font as tkfont
from PrismAbout import APP_NAME,show_about

def main():
    root=tk.Tk();root.title(APP_NAME);root.geometry("1000x960");root.minsize(960,920)
    root.configure(background='#202020')
    families=set(tkfont.families(root))
    family="Ink Free" if "Ink Free" in families else "Segoe Print" if "Segoe Print" in families else "TkDefaultFont"
    for name in ("TkDefaultFont","TkTextFont","TkMenuFont","TkCaptionFont","TkSmallCaptionFont"):
        tkfont.nametofont(name,root=root).configure(family=family,size=13)
    from PrismConverterUI import Converter
    root._converter = app = Converter(root)
    root.iconphoto(True,app._header_logo)
    menu=tk.Menu(root);menu.add_command(label="About",command=lambda:show_about(root));root.configure(menu=menu)
    root.mainloop()

if __name__=="__main__":main()
