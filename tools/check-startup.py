"""Verify the standalone launcher without loading excluded features."""
import runpy,sys,tkinter as tk
from pathlib import Path
sys.path.insert(0,str(Path("src").resolve()))
def check(root):
    root.update()
    assert not any(name.startswith(("amulet","PrismReplay","PrismWorld","ReplayEntities")) for name in sys.modules)
    assert root.title().startswith("Prism ")
    root.destroy()
tk.Tk.mainloop=check
runpy.run_path("src/main.py",run_name="__main__")
print("Standalone launcher passed; no replay dependencies loaded.")
