import ttkbootstrap as tb
import tkinter as tk
from screeninfo import get_monitors
from constants import *
import os
import sys
import subprocess
import shutil

# ==== Main GUI setup ====
root = tb.Window(themename="darkly")
root.title("AlohaSnackBar Hardware Monitor - Setup")

# Get screen dimensions and center the window
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

## Title and Patch Notes

app_title = tb.Label(
    main_frame,
    text="AlohaSnackBar Hardware Monitor",
    font=FONT_TITLE,
    foreground=CRT_GREEN,
    background=bg_color,
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
    foreground=CRT_GREEN,
    background=bg_color,
    justify="center"
)
patch_notes_label.pack(pady=10)

## Startup Options

options_frame = tk.Frame(main_frame, bg=bg_color)
options_frame.pack(pady=20)

start_options_label = tb.Label(
    options_frame,
    text="Start on:",
    font=FONT_INFOTXT,
    foreground=CRT_GREEN,
    background=bg_color,
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
    bootstyle="success",
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
                bootstyle="success",
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

## Startup and Cleanup Logic

def setup_startup_boot():
    """Sets up the application to run automatically on system boot."""
    script_path = os.path.abspath("gui.py")
    if sys.platform.startswith('win'):
        try:
            startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            shortcut_path = os.path.join(startup_folder, "HardwareMonitor.bat")
            with open(shortcut_path, "w") as f:
                f.write(f'python "{script_path}"')
            print("Successfully configured for Windows startup.")
            tb.dialogs.Messagebox.show_info("Startup configured! The app will start on boot.", "Success")
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

# Create a frame to hold the two buttons
button_frame = tk.Frame(options_frame, bg=bg_color)
button_frame.pack(pady=10)

# The buttons are packed side-by-side using the `side=LEFT` and `padx` options
startup_button = tb.Button(
    button_frame,
    text="Set to Run on Boot",
    bootstyle="info-outline",
    command=setup_startup_boot
)
startup_button.pack(side=tk.LEFT, padx=5)

cleanup_button = tb.Button(
    button_frame,
    text="Clear Startup & Cache",
    bootstyle="warning-outline",
    command=clear_startup_and_cache
)
cleanup_button.pack(side=tk.LEFT, padx=5)

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
    main_frame,
    text="Start Monitor",
    bootstyle="success-outline",
    command=save_and_close,
)
start_button.pack(pady=(20, 0))

root.mainloop()