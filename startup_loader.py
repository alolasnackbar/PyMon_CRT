import random
import tkinter as tk
from tkinter import ttk
from constants import *

# # NOTE: These constants and the `Meter` widget would need to be defined elsewhere.
# # Assuming 'CRT_GREEN' and 'DISK_IO_MAX_MBPS' are defined as constants.
# CRT_GREEN = "green"
# DISK_IO_MAX_MBPS = 100

def end_loading(widgets, on_complete=None):
    """
    Clears initial 'Loading...' states from all widgets and calls an
    optional on_complete function when finished.
    """
    for key, w_group in widgets.items():
        # Handles progress bars stored in tuples (e.g., CPU, RAM)
        if isinstance(w_group, tuple) and len(w_group) == 5:
            try:
                if key == "Disk I/O":
                    _, _, io_read_bar, io_write_bar, _ = w_group
                    io_read_bar["value"] = 0
                    io_write_bar["value"] = 0
                else:
                    _, bar, _, _, _ = w_group
                    bar["value"] = 0
            except (tk.TclError, AttributeError):
                # Gracefully handle if a widget was destroyed
                pass

        # Handles widgets stored in dictionaries
        elif isinstance(w_group, dict):
            if key == "Temp Stats":
                # This key points to a dictionary of Meter widgets.
                # Meters are reset using .configure() with specific options.
                for meter in w_group.values():
                    try:
                        meter.configure(amountused=0) # subtext="N/A"
                    except (tk.TclError, AttributeError):
                        pass
            else:
                # All other dictionaries contain standard Label widgets.
                # Labels are cleared by setting their text to an empty string.
                for lbl in w_group.values():
                    try:
                        lbl.config(text="")
                    except (tk.TclError, AttributeError):
                        pass

    # Call the completion callback function if it exists
    if on_complete:
        on_complete()

def startup_loader(root, widgets, style, on_complete=None):
    """
    Animate CRT-green loading bars and labels for all widgets on startup.
    Bars gradually fill and remain green until the loading finishes,
    then revert to real-time updates.
    """
    def fill_bar_gradually(bar, max_value=100, duration=800, steps=20):
        """Gradually fill a progress bar."""
        step_delay = duration // steps

        def step(i=0):
            try:
                if i <= steps:
                    val = (i / steps) * max_value
                    bar["value"] = val
                    style.configure(bar._style_name, background=CRT_GREEN)
                    root.after(step_delay, step, i + 1)
                else:
                    bar["value"] = max_value  # ensure full at the end
            except (tk.TclError, AttributeError):
                # Gracefully handle cases where the widget is not a progress bar
                pass
        step()

    def animate_loading(widget_key):
        w = widgets[widget_key]

        # Handles progress bars (CPU, GPU, RAM)
        if isinstance(w, tuple) and len(w) == 5:
            _, bar, _, _, _ = w
            fill_bar_gradually(bar)
        
        # Handles disk I/O bars
        elif widget_key == "Disk I/O" and isinstance(w, tuple) and len(w) == 5:
            _, _, io_read_bar, io_write_bar, _ = w
            fill_bar_gradually(io_read_bar, max_value=DISK_IO_MAX_MBPS)
            fill_bar_gradually(io_write_bar, max_value=DISK_IO_MAX_MBPS)
        
        # Handles dictionaries (labels and meters)
        elif isinstance(w, dict):
            if widget_key == "Temp Stats":
                # Animate Meter widgets
                for meter in w.values():
                    try:
                        # Set subtext and a loading amount for visual feedback
                        meter.configure(amountused=50)#subtext="Loading..."
                    except (tk.TclError, AttributeError):
                        pass
            else:
                # Animate Label widgets
                for lbl in w.values():
                    try:
                        lbl.config(text="Loading...", foreground=CRT_GREEN)
                    except (tk.TclError, AttributeError):
                        pass

    # Staggered animation for all widgets
    delay = 0
    for key in widgets.keys():
        root.after(delay, lambda k=key: animate_loading(k))
        delay += 600 + random.randint(0, 300)

    # After all animations finish, call the standalone end_loading function.
    # The `lambda` is used to pass arguments to the function call.
    root.after(delay + 800, lambda: end_loading(widgets, on_complete))
