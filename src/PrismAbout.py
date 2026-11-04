"""Standalone app identity."""
APP_NAME = 'Prism Converter'
APP_VERSION = "1.3.8"

def show_about(parent):
    from tkinter import messagebox
    messagebox.showinfo("About "+APP_NAME, APP_NAME+"\nVersion "+APP_VERSION, parent=parent)
