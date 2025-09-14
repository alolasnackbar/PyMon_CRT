import random
from constants import CRT_GREEN, DISK_IO_MAX_MBPS
import tkinter as tk

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

        # CPU/GPU/RAM widgets (tuple, bar at index 1)
        if isinstance(w, tuple) and len(w) == 5:
            _, bar, _, _, _ = w
            fill_bar_gradually(bar)

        # Disk I/O widget (tuple, read/write bars at index 2 & 3)
        elif widget_key == "Disk I/O" and isinstance(w, tuple) and len(w) == 5:
            _, _, io_read_bar, io_write_bar, _ = w
            fill_bar_gradually(io_read_bar, max_value=DISK_IO_MAX_MBPS)
            fill_bar_gradually(io_write_bar, max_value=DISK_IO_MAX_MBPS)

        # Sys Info & Time widget (dict of labels)
        elif isinstance(w, dict):
            for lbl in w.values():
                lbl.config(text="Loading...", foreground=CRT_GREEN)

    # Staggered animation for all widgets
    delay = 0
    for key in widgets.keys():
        root.after(delay, lambda k=key: animate_loading(k))
        delay += 600 + random.randint(0, 300)

    # After all animations finish, reset bars to real-time updates
    def end_loading():
        for key, w in widgets.items():
            if isinstance(w, tuple) and len(w) == 5:
                try:
                    # Reset bars to 0, actual update loop will take over
                    if key == "Disk I/O":
                        _, _, io_read_bar, io_write_bar, _ = w
                        io_read_bar["value"] = 0
                        io_write_bar["value"] = 0
                    else:
                        _, bar, _, _, _ = w
                        bar["value"] = 0
                except (tk.TclError, AttributeError):
                    # Gracefully handle any issues with a malformed widget
                    pass
            elif isinstance(w, dict):
                # Clear "Loading..." labels, actual data will fill in
                for lbl in w.values():
                    lbl.config(text="")

        if on_complete:
            on_complete()

    root.after(delay + 800, end_loading)
