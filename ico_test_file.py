import tkinter as tk, os, sys
def resource_path(rel_path):
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel_path)

root = tk.Tk()
try:
    root.iconbitmap(resource_path("nohead_test.ico"))
    print("ICON: loaded OK")
except Exception as e:
    print("ICON LOAD ERROR:", type(e).__name__, e)
root.destroy()
