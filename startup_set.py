import ttkbootstrap as tb
import tkinter as tk
from screeninfo import get_monitors
from ttkbootstrap.constants import *
from constants import * # Assuming constants.py is available
import os
import sys
import subprocess
import shutil
import json

CONFIG_FILE = "startup_config.txt"

# ==== Load README content for patch notes ====
def load_patch_notes():
    """Load patch notes from README.md file or use a default."""
    default_patch_notes = """
Current Patch Notes (Default):
- Version 0.0.7
- New: Live configuration saving - all changes save immediately
- New: Complete user customization persistence
- New: Enhanced config tab management with stay-in-tab functionality
- Fix: Monitor selection properly persists across restarts
- Fix: All thresholds (CPU, temp, latency) save instantly
- Enhanced: Real-time config updates with validation

Note: Check README.md for complete changelog and documentation.
"""

    try:
        if os.path.exists("README.md"):
            with open("README.md", "r", encoding="utf-8") as f:
                readme_content = f.read()

            # Extract a relevant section from README (look for version info or changelog)
            lines = readme_content.split('\n')
            patch_section = []
            in_changelog = False

            for line in lines:
                if any(keyword in line.lower() for keyword in ['version', 'changelog', 'update', 'patch', 'release']):
                    in_changelog = True
                    patch_section.append(line)
                elif in_changelog and line.strip():
                    # Stop if we encounter another major heading (e.g., starts with #)
                    if line.strip().startswith('#') and len(patch_section) > 5:
                        break
                    patch_section.append(line)
                    if len(patch_section) >= 15:  # Limit to prevent overflow
                        break
                elif in_changelog and not line.strip():
                    if len(patch_section) > 5:  # Stop if we have enough content
                        break

            if patch_section:
                return "Patch Notes from README.md:\n" + "\n".join(patch_section)

    except Exception as e:
        print(f"Error reading README.md: {e}")

    return default_patch_notes

# ==== Configuration Management ====
def load_config():
    """Load existing configuration, handling both old and new (JSON) formats."""
    default_config = {
        "monitor_index": 0,
        "process_count": 5,
        "cycle_enabled": False,
        "cycle_delay": 5,
        "focus_enabled": True,
        "cpu_threshold": 80,
        "temp_threshold": 75,
        "latency_threshold": 200,
        "colorblind_mode": False
    }

    try:
        with open(CONFIG_FILE, "r") as f:
            content = f.read().strip()
            try:
                # Try to load as JSON (new format)
                loaded_config = json.loads(content)
                if isinstance(loaded_config, dict):
                    # Ensure loaded values are of the correct type (e.g., monitor_index is int)
                    if "monitor_index" in loaded_config:
                         try:
                            loaded_config["monitor_index"] = int(loaded_config["monitor_index"])
                         except (ValueError, TypeError):
                             pass # Keep as-is or let default override

                    default_config.update(loaded_config)
            except json.JSONDecodeError:
                # Fallback: Old format - just monitor index (plain text)
                try:
                    default_config["monitor_index"] = int(content)
                except ValueError:
                    pass
    except FileNotFoundError:
        pass

    return default_config

def save_config(config):
    """Save configuration to file in JSON format."""
    try:
        with open(CONFIG_FILE, "w") as f:
            # Ensure monitor_index is an integer for consistent storage
            config["monitor_index"] = int(config["monitor_index"])
            json.dump(config, f, indent=2)
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")

# ==== Main GUI setup ====
root = tb.Window(themename="darkly")
root.title("AlohaSnackBar Hardware Monitor - Setup")

# Get screen dimensions and center the window
window_width = 1000
window_height = 600  # Slightly taller to accommodate new settings
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
position_top = int(screen_height / 2 - window_height / 2)
position_right = int(screen_width / 2 - window_width / 2)
root.geometry(f'{window_width}x{window_height}+{position_right}+{position_top}')
root.minsize(window_width, window_height)

# Fixed: Don't call StyleBuilder methods - use bootstyle parameters instead
style = tb.Style()
bg_color = style.lookup('TNotebook.Tab', 'background')
fg_color = style.lookup('TLabel', 'foreground')

# Load current configuration
current_config = load_config()

# Create a main frame to center all content
main_frame = tk.Frame(root, bg=bg_color)
main_frame.pack(expand=True, padx=20, pady=20, fill=BOTH)

## Section 1: Application Title
title_frame = tb.LabelFrame(main_frame, text="alohasnackbar", bootstyle="success")
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

# Left side: Patch Notes (now from README)
patch_notes_frame = tb.LabelFrame(content_frame, text="Release Version Details", bootstyle="success")
patch_notes_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(5, 10), pady=5)

# Load patch notes from README
patch_notes_text = load_patch_notes()

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

# Variable to hold the selected monitor value. The value is set based on loaded config.
# Note: Monitor index in config is 0 for Current Display, 1 for Display 1, 2 for Display 2, etc.
monitor_choice = tk.StringVar(value=str(current_config.get("monitor_index", 0)))

# Live saving function for monitor selection
def on_monitor_change(*args):
    """Save monitor selection immediately when changed."""
    current_config["monitor_index"] = int(monitor_choice.get())
    save_config(current_config)

# Bind the monitor choice to auto-save
monitor_choice.trace('w', on_monitor_change)

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

# Value 0 is reserved for "Current Display"
default_radio = tb.Radiobutton(
    controls_frame,
    text="Current Display",
    value="0",
    variable=monitor_choice,
    bootstyle="success",
)
default_radio.pack(anchor="w", padx=10, pady=5)

# Get detected monitors and create radiobuttons for specific displays
try:
    monitors = get_monitors()
    if monitors:
        # i starts at 0, display index is i + 1, and value is i + 1 (1 for Display 1, 2 for Display 2)
        for i, monitor in enumerate(monitors):
            # i + 1 is the display number/value for the radiobutton
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
            text="No external displays detected. Defaulting to main display.",
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

## Additional Configuration Settings (matching gui.py)
config_section_label = tb.Label(
    controls_frame,
    text="Additional Settings:",
    font=FONT_INFOTXT,
    foreground=CRT_GREEN,
    background=bg_color,
    bootstyle="inverse-primary"
)
config_section_label.pack(anchor="w", padx=10, pady=(5, 0))

# Create variables for additional config options
config_vars = {}
config_vars["cycle_enabled"] = tk.BooleanVar(value=current_config.get("cycle_enabled", False))
config_vars["focus_enabled"] = tk.BooleanVar(value=current_config.get("focus_enabled", True))
config_vars["colorblind_mode"] = tk.BooleanVar(value=current_config.get("colorblind_mode", False))
config_vars["process_count"] = tk.IntVar(value=current_config.get("process_count", 5))

# Live saving functions for additional settings
def create_config_saver(key):
    def save_setting(*args):
        current_config[key] = config_vars[key].get()
        save_config(current_config)
    return save_setting

# Bind all config variables to auto-save
for key in config_vars:
    config_vars[key].trace('w', create_config_saver(key))

# Add checkboxes for boolean settings
cycle_check = tb.Checkbutton(
    controls_frame,
    text="Enable auto tab cycling",
    variable=config_vars["cycle_enabled"],
    bootstyle="success"
)
cycle_check.pack(anchor="w", padx=15, pady=2)

focus_check = tb.Checkbutton(
    controls_frame,
    text="Enable smart focus alerts",
    variable=config_vars["focus_enabled"],
    bootstyle="success"
)
focus_check.pack(anchor="w", padx=15, pady=2)

colorblind_check = tb.Checkbutton(
    controls_frame,
    text="Colorblind-friendly mode",
    variable=config_vars["colorblind_mode"],
    bootstyle="success"
)
colorblind_check.pack(anchor="w", padx=15, pady=2)

# Add process count setting
process_frame = tk.Frame(controls_frame, bg=bg_color)
process_frame.pack(anchor="w", padx=15, pady=2)

process_label = tb.Label(process_frame, text="Process count:", font=("TkDefaultFont", 9))
process_label.pack(side="left")

process_spinbox = tb.Spinbox(
    process_frame,
    from_=1, to=20,
    textvariable=config_vars["process_count"],
    width=5,
    bootstyle="success"
)
process_spinbox.pack(side="left", padx=(5, 0))

tb.Separator(controls_frame, orient="horizontal").pack(fill="x", padx=10, pady=10)

## Startup and Cleanup Logic

def get_target_file():
    """Determine the path and type of the file to execute (EXE takes precedence)."""
    script_path = os.path.abspath("gui.py")
    exe_path = os.path.abspath("gui.exe")

    if os.path.exists(exe_path):
        return exe_path, True # Path, is_exe
    elif os.path.exists(script_path):
        return script_path, False # Path, is_exe
    else:
        return None, None


def setup_startup_boot():
    """Sets up the application to run automatically on system boot."""
    target_path, is_exe = get_target_file()

    if target_path is None:
        tb.dialogs.Messagebox.show_error("Neither gui.py nor gui.exe found in current directory. Cannot set startup.", "Error")
        return

    if sys.platform.startswith('win'):
        try:
            startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            shortcut_path = os.path.join(startup_folder, "HardwareMonitor.bat")
            
            with open(shortcut_path, "w") as f:
                # Use 'start' to run without blocking the startup process
                if is_exe:
                    # For .exe files: simply execute the file
                    f.write(f'@echo off\ncd /d "{os.path.dirname(target_path)}"\nstart "" "{os.path.basename(target_path)}"\n')
                else:
                    # For .py files: use 'py' or 'python'
                    f.write(f'@echo off\ncd /d "{os.path.dirname(target_path)}"\nstart "" py "{os.path.basename(target_path)}"\n')
            
            file_type = ".exe" if is_exe else ".py"
            tb.dialogs.Messagebox.show_info(f"Startup configured! The app will start on boot.\nUsing: {file_type} from {os.path.dirname(target_path)}\nShortcut created at: {shortcut_path}", "Success")
            print(f"Successfully configured for Windows startup using {file_type}")
        except Exception as e:
            tb.dialogs.Messagebox.show_error(f"Failed to configure startup: {e}", "Error")
            print(f"Error setting up Windows startup: {e}")
            
    elif sys.platform.startswith('linux'):
        try:
            autostart_dir = os.path.join(os.path.expanduser('~'), '.config', 'autostart')
            if not os.path.exists(autostart_dir):
                os.makedirs(autostart_dir)
            desktop_file_path = os.path.join(autostart_dir, "hardware-monitor.desktop")
            
            if is_exe:
                # For compiled executables, the path is the command
                exec_command = target_path
            else:
                # For Python scripts, use the Python interpreter
                exec_command = f"{sys.executable} {target_path}"
                
            desktop_content = f"""[Desktop Entry]
Type=Application
Exec={exec_command}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name[en_US]=Hardware Monitor
Comment[en_US]=Monitors system hardware usage
"""
            with open(desktop_file_path, "w") as f:
                f.write(desktop_content)
            
            file_type = ".exe" if is_exe else ".py"
            tb.dialogs.Messagebox.show_info(f"Startup configured! The app will start on boot.\nUsing: {file_type}", "Success")
            print(f"Successfully configured for Linux startup using {file_type}")
        except Exception as e:
            tb.dialogs.Messagebox.show_error(f"Failed to configure startup: {e}", "Error")
            print(f"Error setting up Linux startup: {e}")
            
    elif sys.platform == 'darwin':
        try:
            plist_dir = os.path.join(os.path.expanduser('~'), 'Library', 'LaunchAgents')
            if not os.path.exists(plist_dir):
                os.makedirs(plist_dir)
            plist_path = os.path.join(plist_dir, "com.alohasnackbar.hwmonitor.plist")
            
            if is_exe:
                program_args = f"""    <array>
        <string>{target_path}</string>
    </array>"""
            else:
                program_args = f"""    <array>
        <string>{sys.executable}</string>
        <string>{target_path}</string>
    </array>"""
            
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.alohasnackbar.hwmonitor</string>
    <key>ProgramArguments</key>
{program_args}
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
            with open(plist_path, "w") as f:
                f.write(plist_content)
            
            file_type = ".exe" if is_exe else ".py"
            tb.dialogs.Messagebox.show_info(f"Startup configured! The app will start on boot.\nUsing: {file_type}", "Success")
            print(f"Successfully configured for macOS startup using {file_type}")
        except Exception as e:
            tb.dialogs.Messagebox.show_error(f"Failed to configure startup: {e}", "Error")
            print(f"Error setting up macOS startup: {e}")
    else:
        tb.dialogs.Messagebox.show_warning("Startup not configured. Unsupported OS.", "Warning")
        print("Warning: Unsupported operating system for startup configuration.")


def clear_startup_and_cache():
    """Removes startup configurations and data files."""
    cleared_startup = False
    
    # 1. Clear OS-specific startup files
    if sys.platform.startswith('win'):
        try:
            startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            bat_path = os.path.join(startup_folder, "HardwareMonitor.bat")
            if os.path.exists(bat_path):
                os.remove(bat_path)
                print("Removed Windows startup file.")
                cleared_startup = True
        except Exception as e:
            print(f"Error removing Windows startup file: {e}")
            
    elif sys.platform.startswith('linux'):
        try:
            autostart_dir = os.path.join(os.path.expanduser('~'), '.config', 'autostart')
            desktop_file_path = os.path.join(autostart_dir, "hardware-monitor.desktop")
            if os.path.exists(desktop_file_path):
                os.remove(desktop_file_path)
                print("Removed Linux startup file.")
                cleared_startup = True
        except Exception as e:
            print(f"Error removing Linux startup file: {e}")
            
    elif sys.platform == 'darwin':
        try:
            plist_dir = os.path.join(os.path.expanduser('~'), 'Library', 'LaunchAgents')
            plist_path = os.path.join(plist_dir, "com.alohasnackbar.hwmonitor.plist")
            if os.path.exists(plist_path):
                os.remove(plist_path)
                print("Removed macOS startup file.")
                cleared_startup = True
        except Exception as e:
            print(f"Error removing macOS startup file: {e}")

    # 2. Clear local configuration/cache file
    cleared_cache = False
    try:
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            print(f"Removed {CONFIG_FILE}.")
            cleared_cache = True
    except Exception as e:
        print(f"Error removing local cache file: {e}")
        
    if cleared_startup or cleared_cache:
        tb.dialogs.Messagebox.show_info("Startup configuration and local cache files have been removed.", "Cleanup Complete")
    else:
        tb.dialogs.Messagebox.show_info("No startup configuration or local cache files were found to remove.", "Cleanup Complete")

# Buttons for startup and cleanup
button_frame = tk.Frame(controls_frame, bg=bg_color)
button_frame.pack(fill="x", pady=(10, 5))

startup_button = tb.Button(
    button_frame,
    text="Set Startup Boot",
    bootstyle="info-outline",
    command=setup_startup_boot
)
startup_button.pack(side=tk.LEFT, padx=5, fill="x", expand=True)

cleanup_button = tb.Button(
    button_frame,
    text="Clear Config",
    bootstyle="warning-outline",
    command=clear_startup_and_cache
)
cleanup_button.pack(side=tk.LEFT, padx=5, fill="x", expand=True)

tb.Separator(controls_frame, orient="horizontal").pack(fill="x", padx=10, pady=10)

## Main App Button
def save_and_close():
    """Save configuration and start the main application."""
    # Configuration is already saved by the trace callbacks, so we just start the app
    
    # Destroy the setup window
    root.destroy()
    
    # Run the main application (gui.exe takes precedence)
    target_path, is_exe = get_target_file()
    
    if target_path:
        try:
            if is_exe:
                # Run the compiled executable directly
                subprocess.run([target_path], check=True)
            else:
                # Run the Python script using the interpreter
                subprocess.run([sys.executable, target_path], check=True)
        except FileNotFoundError:
            print("Error: The main application file was not found.")
        except subprocess.CalledProcessError as e:
            print(f"Error: The main application failed to run. Process returned {e.returncode}.")
        except Exception as e:
            print(f"An unexpected error occurred while trying to run the main application: {e}")
    else:
        print("Error: Cannot start the monitor. Neither gui.py nor gui.exe found.")


start_button = tb.Button(
    controls_frame,
    text="Start Monitor",
    bootstyle="success-outline",
    command=save_and_close,
)
start_button.pack(fill="x", padx=10, pady=(0, 10))

root.mainloop()