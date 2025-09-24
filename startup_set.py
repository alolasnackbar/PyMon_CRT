import ttkbootstrap as tb
import tkinter as tk
from screeninfo import get_monitors
from ttkbootstrap.constants import *
from constants import *
import os
import sys
import subprocess
import shutil

# ==== Main GUI setup ====
root = tb.Window(themename="darkly")
root.title("AlohaSnackBar Hardware Monitor - Setup")

# Get screen dimensions and center the window
window_width = 1000
window_height = 450
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
position_top = int(screen_height / 2 - window_height / 2)
position_right = int(screen_width / 2 - window_width / 2)
root.geometry(f'{window_width}x{window_height}+{position_right}+{position_top}')
root.minsize(window_width, window_height)

style = tb.Style()
style.configure("TCheckbutton", font=FONT_INFOTXT)
bg_color = style.lookup('TNotebook.Tab', 'background')
fg_color = style.lookup('TLabel', 'foreground')

# Create a main frame to center all content
main_frame = tk.Frame(root, bg=bg_color)
main_frame.pack(expand=True, padx=20, pady=20, fill=BOTH)

## Section 1: Application Title
title_frame = tb.LabelFrame(main_frame, text="alolasnackbar", bootstyle="success")
title_frame.pack(fill="x", padx=5, pady=5)

app_title = tb.Label(
    title_frame,
    text="AlohaSnackBar Hardware Monitor",
    font=FONT_TITLE,
    foreground=CRT_GREEN,
    background=bg_color,
    bootstyle="inverse-primary"
)
app_title.pack(anchor="w", padx=10, pady=5)

tb.Separator(main_frame, orient="horizontal").pack(fill="x", padx=5, pady=10)

## Section 2 & 3: Side-by-Side Content
content_frame = tk.Frame(main_frame, bg=bg_color)
content_frame.pack(expand=True, fill=BOTH)

# Left side: Patch Notes
patch_notes_frame = tb.LabelFrame(content_frame, text="Release Version Details", bootstyle="success")
patch_notes_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(5, 10), pady=5)

patch_notes_text = """
Current Patch Notes:
- Version 0.0.5
- New: temp cpu/gpu added, crt_graphics applied
- New: config tab added for notebook customization 
- Fix: Improved fullscreen behavior on multi-monitor setups, 
- Adjusted: fine tuned and optimized gui widgets
- Deprecating: File menu will be moved into config tab for styling issues

________  unavailable until further notice __________
- temp cpu/gpu added, need more research on meters
- net stats limited
"""
patch_notes_label = tb.Label(
    patch_notes_frame,
    text=patch_notes_text,
    font=FONT_INFOTXT,
    foreground=CRT_GREEN,
    background=bg_color,
    justify="left"
)
patch_notes_label.pack(anchor="w", padx=10, pady=5)

# Right side: Settings and Controls
controls_frame = tb.LabelFrame(content_frame, text="Settings and Controls", bootstyle="success")
controls_frame.pack(side=RIGHT, fill=BOTH, expand=True, padx=(10, 5), pady=5)

# Variable to hold the selected monitor value
monitor_choice = tk.StringVar(value="0") # Default to current screen (index 0)

# Radio button for starting on the current display
start_options_label = tb.Label(
    controls_frame,
    text="Start on:",
    font=FONT_INFOTXT,
    foreground=CRT_GREEN,
    background=bg_color,
    bootstyle="inverse-primary"
)
start_options_label.pack(anchor="w", padx=10, pady=(10, 0))

default_radio = tb.Radiobutton(
    controls_frame,
    text="Current Display",
    value="0",
    variable=monitor_choice,
    bootstyle="success",
)
default_radio.pack(anchor="w", padx=10, pady=5)

# Get detected monitors and create radiobuttons
try:
    monitors = get_monitors()
    if monitors:
        for i, monitor in enumerate(monitors):
            display_text = f"Display {i + 1}"
            if monitor.is_primary:
                display_text += " (Primary)"
            radiobutton = tb.Radiobutton(
                controls_frame,
                text=display_text,
                value=str(i + 1),
                variable=monitor_choice,
                bootstyle="success",
            )
            radiobutton.pack(anchor="w", padx=10, pady=5)
    else:
        no_display_label = tb.Label(
            controls_frame,
            text="No displays detected. Defaulting to main display.",
            font=FONT_INFOTXT,
            foreground=fg_color
        )
        no_display_label.pack(anchor="w", padx=10, pady=5)
except Exception:
    no_display_label = tb.Label(
        controls_frame,
        text="An error occurred detecting displays. Defaulting to main display.",
        font=FONT_INFOTXT,
        foreground=fg_color
    )
    no_display_label.pack(anchor="w", padx=10, pady=5)

tb.Separator(controls_frame, orient="horizontal").pack(fill="x", padx=10, pady=10)

## Startup and Cleanup Logic

def setup_startup_boot():
    """Sets up the application to run automatically on system boot."""
    script_path = os.path.abspath("gui.py")
    if sys.platform.startswith('win'):
        try:
            startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            shortcut_path = os.path.join(startup_folder, "HardwareMonitor.bat")
            with open(shortcut_path, "w") as f:
                f.write(f'@echo off\ncd /d "{os.path.dirname(script_path)}"\nstart "" py "{os.path.basename(script_path)}"\n') #use for now
                #f.write(f'@echo off\ncd /d "{os.path.dirname(script_path)}"\nstart "" pythonw "{os.path.basename(script_path)}"\n')
                #f.write(f'@echo off\ncd /d "{os.path.dirname(script_path)}"\npy "{os.path.basename(script_path)}" && exit || PAUSE')
            print("Successfully configured for Windows startup.")
            tb.dialogs.Messagebox.show_info(f"Startup configured! The app will start on boot.\nShortcut created at: {shortcut_path}", "Success")
        except Exception as e:
            tb.dialogs.Messagebox.show_error(f"Failed to configure startup: {e}", "Error")
            print(f"Error setting up Windows startup: {e}")
    elif sys.platform.startswith('linux'):
        try:
            autostart_dir = os.path.join(os.path.expanduser('~'), '.config', 'autostart')
            if not os.path.exists(autostart_dir):
                os.makedirs(autostart_dir)
            desktop_file_path = os.path.join(autostart_dir, "hardware-monitor.desktop")
            desktop_content = f"""[Desktop Entry]
Type=Application
Exec={sys.executable} {script_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name[en_US]=Hardware Monitor
Comment[en_US]=Monitors system hardware usage
"""
            with open(desktop_file_path, "w") as f:
                f.write(desktop_content)
            print("Successfully configured for Linux startup.")
            tb.dialogs.Messagebox.show_info("Startup configured! The app will start on boot.", "Success")
        except Exception as e:
            tb.dialogs.Messagebox.show_error(f"Failed to configure startup: {e}", "Error")
            print(f"Error setting up Linux startup: {e}")
    elif sys.platform == 'darwin':
        try:
            plist_dir = os.path.join(os.path.expanduser('~'), 'Library', 'LaunchAgents')
            if not os.path.exists(plist_dir):
                os.makedirs(plist_dir)
            plist_path = os.path.join(plist_dir, "com.alohasnackbar.hwmonitor.plist")
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.alohasnackbar.hwmonitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
            with open(plist_path, "w") as f:
                f.write(plist_content)
            print("Successfully configured for macOS startup.")
            tb.dialogs.Messagebox.show_info("Startup configured! The app will start on boot.", "Success")
        except Exception as e:
            tb.dialogs.Messagebox.show_error(f"Failed to configure startup: {e}", "Error")
            print(f"Error setting up macOS startup: {e}")
    else:
        tb.dialogs.Messagebox.show_warning("Startup not configured. Unsupported OS.", "Warning")
        print("Warning: Unsupported operating system for startup configuration.")


def clear_startup_and_cache():
    """Removes startup configurations and data files."""
    if sys.platform.startswith('win'):
        try:
            startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            bat_path = os.path.join(startup_folder, "HardwareMonitor.bat")
            if os.path.exists(bat_path):
                os.remove(bat_path)
            print("Removed Windows startup file.")
        except Exception as e:
            print(f"Error removing Windows startup file: {e}")
    elif sys.platform.startswith('linux'):
        try:
            autostart_dir = os.path.join(os.path.expanduser('~'), '.config', 'autostart')
            desktop_file_path = os.path.join(autostart_dir, "hardware-monitor.desktop")
            if os.path.exists(desktop_file_path):
                os.remove(desktop_file_path)
            print("Removed Linux startup file.")
        except Exception as e:
            print(f"Error removing Linux startup file: {e}")
    elif sys.platform == 'darwin':
        try:
            plist_dir = os.path.join(os.path.expanduser('~'), 'Library', 'LaunchAgents')
            plist_path = os.path.join(plist_dir, "com.alohasnackbar.hwmonitor.plist")
            if os.path.exists(plist_path):
                os.remove(plist_path)
            print("Removed macOS startup file.")
        except Exception as e:
            print(f"Error removing macOS startup file: {e}")

    try:
        if os.path.exists("startup_config.txt"):
            os.remove("startup_config.txt")
            print("Removed startup_config.txt.")
    except Exception as e:
        print(f"Error removing local cache files: {e}")

    tb.dialogs.Messagebox.show_info("Startup configuration and local cache files have been removed.", "Cleanup Complete")

# Buttons for startup and cleanup
button_frame = tk.Frame(controls_frame, bg=bg_color)
button_frame.pack(fill="x", pady=(10, 5))

startup_button = tb.Button(
    button_frame,
    text="Set to Run on Boot",
    bootstyle="info-outline",
    command=setup_startup_boot
)
startup_button.pack(side=tk.LEFT, padx=5, fill="x", expand=True)

cleanup_button = tb.Button(
    button_frame,
    text="Clear Startup & Cache",
    bootstyle="warning-outline",
    command=clear_startup_and_cache
)
cleanup_button.pack(side=tk.LEFT, padx=5, fill="x", expand=True)

tb.Separator(controls_frame, orient="horizontal").pack(fill="x", padx=10, pady=10)

## Main App Button
def save_and_close():
    selected_monitor = monitor_choice.get()
    try:
        with open("startup_config.txt", "w") as f:
            f.write(selected_monitor)
    except IOError as e:
        print(f"Error writing startup config file: {e}")
    root.destroy()
    try:
        subprocess.run([sys.executable, "gui.py"], check=True)
    except FileNotFoundError:
        print("Error: gui.py not found. Please ensure it's in the same directory.")
    except subprocess.CalledProcessError:
        print("Error: The GUI script failed to run.")

start_button = tb.Button(
    controls_frame,
    text="Start Monitor",
    bootstyle="success-outline",
    command=save_and_close,
)
start_button.pack(fill="x", padx=10, pady=(0, 10))

root.mainloop()
