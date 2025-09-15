import ttkbootstrap as tb
import tkinter as tk
from screeninfo import get_monitors
from constants import *
import os
import sys
import subprocess

# ==== Main GUI setup ====
root = tb.Window(themename="darkly")
root.title("AlohaSnackBar Hardware Monitor - Setup")
root.geometry("600x400")

# Center the window on the screen
window_width = 600
window_height = 600
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
position_top = int(screen_height / 2 - window_height / 2)
position_right = int(screen_width / 2 - window_width / 2)
root.geometry(f'{window_width}x{window_height}+{position_right}+{position_top}')

style = tb.Style()
# Configure the font for TCheckbutton style
style.configure("TCheckbutton", font=FONT_INFOTXT)
# Get theme colors for consistent styling
bg_color = style.lookup('TNotebook.Tab', 'background')
fg_color = style.lookup('TLabel', 'foreground')

# Create a main frame to center all content
main_frame = tk.Frame(root, bg=bg_color)
main_frame.pack(expand=True, padx=20, pady=20)

# === Title and Patch Notes ===
app_title = tb.Label(
    main_frame,
    text="AlohaSnackBar Hardware Monitor",
    font=FONT_TITLE,
    foreground=fg_color,
    bootstyle="inverse-primary"
)
app_title.pack(pady=(0, 10))

patch_notes_text = """
Current Patch Notes:
- Version 0.0.45
- New: temp cpu/gpu added, need more research on meters
- New: gpu temps should be crossplatform linux/os amd nvd (not tested)
- Fix: Improved fullscreen behavior on multi-monitor setups, 
- Adjusted: fine tuned and optimized for usage
== unavailable until further notice ===
- temp cpu/gpu added, need more research on meters
- net stats limited
"""
patch_notes_label = tb.Label(
    main_frame,
    text=patch_notes_text,
    font=FONT_INFOTXT,
    foreground=fg_color,
    justify="center"
)
patch_notes_label.pack(pady=10)

# ---
# === Startup Options Section ===
options_frame = tk.Frame(main_frame, bg=bg_color)
options_frame.pack(pady=20)

start_options_label = tb.Label(
    options_frame,
    text="Start on:",
    font=FONT_INFOTXT,
    foreground=fg_color,
    bootstyle="inverse-primary"
)
start_options_label.pack(pady=(0, 10))

# Variable to hold the selected monitor value
monitor_choice = tk.StringVar(value="0") # Default to current screen (index 0)

# Radio button for starting on the current display
default_radio = tb.Radiobutton(
    options_frame,
    text="Current Display",
    value="0",
    variable=monitor_choice,
    bootstyle="round-toggle"
)
default_radio.pack(anchor="w", pady=5)

# Get detected monitors and create radiobuttons
try:
    monitors = get_monitors()
    if monitors:
        for i, monitor in enumerate(monitors):
            display_text = f"Display {i + 1}"
            if monitor.is_primary:
                display_text += " (Primary)"
            radiobutton = tb.Radiobutton(
                options_frame,
                text=display_text,
                value=str(i + 1),
                variable=monitor_choice,
                bootstyle="round-toggle"
            )
            radiobutton.pack(anchor="w", pady=5)
    else:
        no_display_label = tb.Label(
            options_frame,
            text="No displays detected. Defaulting to main display.",
            font=FONT_INFOTXT,
            foreground=fg_color
        )
        no_display_label.pack(pady=5)
except Exception:
    no_display_label = tb.Label(
        options_frame,
        text="An error occurred detecting displays. Defaulting to main display.",
        font=FONT_INFOTXT,
        foreground=fg_color
    )
    no_display_label.pack(pady=5)


# Checkbox for starting on computer boot
startup_checkbox = tb.Checkbutton(
    options_frame,
    text="Start on computer boot",
    bootstyle="round-toggle",
)
startup_checkbox.pack(anchor="w", pady=10)

# Function to save the selected monitor to a file
def save_and_close():
    selected_monitor = monitor_choice.get()
    try:
        with open("startup_config.txt", "w") as f:
            f.write(selected_monitor)
    except IOError as e:
        print(f"Error writing startup config file: {e}")
    root.destroy()
    try:
        # Run the gui.py script after the setup is complete
        subprocess.run([sys.executable, "gui.py"], check=True)
    except FileNotFoundError:
        print("Error: gui.py not found. Please ensure it's in the same directory.")
    except subprocess.CalledProcessError:
        print("Error: The GUI script failed to run.")

# Add a placeholder button to "start" the app after setup
start_button = tb.Button(
    main_frame,
    text="Start Monitor",
    bootstyle="success-outline",
    command=save_and_close,
)

start_button.pack(pady=(20, 0))

root.mainloop()
