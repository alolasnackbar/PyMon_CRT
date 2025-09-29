import ttkbootstrap as tb
import tkinter as tk
from tkinter import scrolledtext
from screeninfo import get_monitors
from ttkbootstrap.constants import *
from constants import * # Assuming constants.py is available
import os
import sys
import subprocess
import shutil
import json
import threading
from datetime import datetime

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

            lines = readme_content.split('\n')
            patch_section = []
            in_changelog = False

            for line in lines:
                if any(keyword in line.lower() for keyword in ['version', 'changelog', 'update', 'patch', 'release']):
                    in_changelog = True
                    patch_section.append(line)
                elif in_changelog and line.strip():
                    if line.strip().startswith('#') and len(patch_section) > 5:
                        break
                    patch_section.append(line)
                    if len(patch_section) >= 15:
                        break
                elif in_changelog and not line.strip():
                    if len(patch_section) > 5:
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
                loaded_config = json.loads(content)
                if isinstance(loaded_config, dict):
                    if "monitor_index" in loaded_config:
                         try:
                            loaded_config["monitor_index"] = int(loaded_config["monitor_index"])
                         except (ValueError, TypeError):
                             pass

                    default_config.update(loaded_config)
            except json.JSONDecodeError:
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
            config["monitor_index"] = int(config["monitor_index"])
            json.dump(config, f, indent=2)
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")

# ==== Main GUI setup ====
root = tb.Window(themename="darkly")
root.iconbitmap('nohead_test.ico')
root.title("AlohaSnackBar Hardware Monitor - Setup")

window_width = 1069
window_height = 600
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
position_top = int(screen_height / 2 - window_height / 2)
position_right = int(screen_width / 2 - window_width / 2)
root.geometry(f'{window_width}x{window_height}+{position_right}+{position_top}')
root.minsize(window_width, window_height)

style = tb.Style()
bg_color = style.lookup('TNotebook.Tab', 'background')
fg_color = style.lookup('TLabel', 'foreground')

current_config = load_config()

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

left_container = tk.Frame(content_frame, bg=bg_color)
left_container.pack(side=LEFT, fill=BOTH, expand=True, padx=(5, 10), pady=5)

patch_notes_frame = tb.LabelFrame(left_container, text="Release Version Details", bootstyle="success")
patch_notes_frame.pack(fill=BOTH, expand=False, pady=(0, 5))

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

# Diagnostic Console
console_frame = tb.LabelFrame(left_container, text="Konsole", bootstyle="success")
console_frame.pack(fill=BOTH, expand=True, pady=(5, 0))

console_text = scrolledtext.ScrolledText(
    console_frame,
    wrap=tk.WORD,
    height=12,
    font=("Consolas", 9),
    bg="#1e1e1e",
    fg="#00ff00",
    insertbackground="#00ff00",
    state=tk.DISABLED
)
console_text.pack(fill=BOTH, expand=True, padx=5, pady=5)

# Configure text tags for colors
console_text.tag_config("green", foreground="#00ff00")
console_text.tag_config("yellow", foreground="#ffff00")
console_text.tag_config("red", foreground="#ff5555")
console_text.tag_config("cyan", foreground="#00ffff")
console_text.tag_config("magenta", foreground="#ff00ff")
console_text.tag_config("white", foreground="#ffffff")

# Right side: Settings and Controls
controls_frame = tb.LabelFrame(content_frame, text="Settings and Controls", bootstyle="success")
controls_frame.pack(side=RIGHT, fill=BOTH, expand=True, padx=(10, 5), pady=5)

## Console Helper Functions
def write_to_console(text, tag="white"):
    """Write text to the console with specified color tag"""
    console_text.config(state=tk.NORMAL)
    console_text.insert(tk.END, text, tag)
    console_text.see(tk.END)
    console_text.config(state=tk.DISABLED)
    root.update_idletasks()

def clear_console():
    """Clear the console output"""
    console_text.config(state=tk.NORMAL)
    console_text.delete(1.0, tk.END)
    console_text.config(state=tk.DISABLED)

def log_console(message, level="info"):
    """Log a message to console with timestamp and color"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if level == "info":
        write_to_console(f"[{timestamp}] ", "cyan")
        write_to_console(f"{message}\n", "white")
    elif level == "success":
        write_to_console(f"[{timestamp}] ✓ ", "cyan")
        write_to_console(f"{message}\n", "green")
    elif level == "warning":
        write_to_console(f"[{timestamp}] ⚠ ", "cyan")
        write_to_console(f"{message}\n", "yellow")
    elif level == "error":
        write_to_console(f"[{timestamp}] ✗ ", "cyan")
        write_to_console(f"{message}\n", "red")

# Monitor selection
monitor_choice = tk.StringVar(value=str(current_config.get("monitor_index", 0)))

def on_monitor_change(*args):
    """Save monitor selection immediately when changed."""
    new_index = int(monitor_choice.get())
    old_index = current_config.get("monitor_index", 0)
    
    if new_index != old_index:
        current_config["monitor_index"] = new_index
        save_config(current_config)
        
        if new_index == 0:
            log_console(f"Monitor changed: Current Display", "success")
        else:
            log_console(f"Monitor changed: Display {new_index}", "success")

monitor_choice.trace('w', on_monitor_change)

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

# Get detected monitors
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

## Additional Configuration Settings
config_section_label = tb.Label(
    controls_frame,
    text="Additional Settings:",
    font=FONT_INFOTXT,
    foreground=CRT_GREEN,
    background=bg_color,
    bootstyle="inverse-primary"
)
config_section_label.pack(anchor="w", padx=10, pady=(5, 0))

config_vars = {}
config_vars["cycle_enabled"] = tk.BooleanVar(value=current_config.get("cycle_enabled", False))
config_vars["focus_enabled"] = tk.BooleanVar(value=current_config.get("focus_enabled", True))
config_vars["colorblind_mode"] = tk.BooleanVar(value=current_config.get("colorblind_mode", False))
config_vars["process_count"] = tk.IntVar(value=current_config.get("process_count", 5))

def create_config_saver(key):
    def save_setting(*args):
        new_value = config_vars[key].get()
        old_value = current_config.get(key)
        
        if new_value != old_value:
            current_config[key] = new_value
            save_config(current_config)
            
            if isinstance(new_value, bool):
                status = "enabled" if new_value else "disabled"
                log_console(f"'{key}' {status}", "success")
            else:
                log_console(f"'{key}' = {new_value}", "success")
    
    return save_setting

for key in config_vars:
    config_vars[key].trace('w', create_config_saver(key))

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

## Diagnostic Functions
def run_diagnostic():
    """Run hardware diagnostic and display results in console"""
    clear_console()
    write_to_console("="*60 + "\n", "cyan")
    write_to_console("HARDWARE DETECTION DIAGNOSTIC\n", "cyan")
    write_to_console("="*60 + "\n\n", "cyan")
    
    if not os.path.exists("debug_core.py"):
        write_to_console("✗ Error: debug_core.py not found!\n", "red")
        write_to_console("  Please ensure debug_core.py is in the same directory.\n\n", "yellow")
        return
    
    def diagnostic_thread():
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            
            try:
                import debug_core
                from importlib import reload
                reload(debug_core)
            except ImportError as e:
                write_to_console(f"✗ Cannot import debug_core: {e}\n", "red")
                return
            
            write_to_console("[MODULE CHECK]\n", "magenta")
            write_to_console("-"*60 + "\n", "white")
            
            result = debug_core.run_diagnostics()
            
            output_lines = result.get_plain_text().split('\n')
            for line in output_lines:
                if line.startswith('✓'):
                    write_to_console(line + '\n', "green")
                elif line.startswith('⚠'):
                    write_to_console(line + '\n', "yellow")
                elif line.startswith('✗'):
                    write_to_console(line + '\n', "red")
                elif line.startswith('['):
                    write_to_console(line + '\n', "magenta")
                elif line.startswith('='):
                    write_to_console(line + '\n', "cyan")
                elif line.startswith('-'):
                    write_to_console(line + '\n', "white")
                else:
                    write_to_console(line + '\n', "white")
            
            write_to_console("\n✓ Diagnostic complete!\n", "green")
            
        except Exception as e:
            write_to_console(f"\n✗ Error running diagnostic: {e}\n", "red")
    
    thread = threading.Thread(target=diagnostic_thread, daemon=True)
    thread.start()

def show_monitor_info():
    """Display detailed monitor information in console"""
    write_to_console("\n" + "="*60 + "\n", "cyan")
    write_to_console("MONITOR INFORMATION\n", "cyan")
    write_to_console("="*60 + "\n\n", "cyan")
    
    try:
        monitors = get_monitors()
        if monitors:
            write_to_console(f"Total monitors: {len(monitors)}\n\n", "green")
            
            for i, monitor in enumerate(monitors):
                write_to_console(f"[Display {i + 1}]\n", "magenta")
                write_to_console(f"  Resolution: {monitor.width} x {monitor.height}\n", "white")
                write_to_console(f"  Position: X={monitor.x}, Y={monitor.y}\n", "white")
                write_to_console(f"  Primary: {'Yes' if monitor.is_primary else 'No'}\n", "green" if monitor.is_primary else "white")
                if hasattr(monitor, 'name'):
                    write_to_console(f"  Name: {monitor.name}\n", "white")
                write_to_console("\n", "white")
            
            current_index = current_config.get("monitor_index", 0)
            if current_index == 0:
                write_to_console("Selected: Current Display (auto)\n", "yellow")
            else:
                write_to_console(f"Selected: Display {current_index}\n", "yellow")
                
        else:
            write_to_console("No monitors detected\n", "red")
            
    except Exception as e:
        write_to_console(f"Error: {e}\n", "red")
    
    write_to_console("="*60 + "\n", "cyan")

## Startup and Cleanup Logic
def get_target_file():
    """Determine the path and type of the file to execute (EXE takes precedence)."""
    script_path = os.path.abspath("gui.py")
    exe_path = os.path.abspath("gui.exe")

    if os.path.exists(exe_path):
        return exe_path, True
    elif os.path.exists(script_path):
        return script_path, False
    else:
        return None, None

def setup_startup_boot():
    """Sets up the application to run automatically on system boot."""
    log_console("Configuring startup...", "info")
    target_path, is_exe = get_target_file()

    if target_path is None:
        log_console("Error: gui.py/gui.exe not found", "error")
        tb.dialogs.Messagebox.show_error("Neither gui.py nor gui.exe found in current directory. Cannot set startup.", "Error")
        return

    if sys.platform.startswith('win'):
        try:
            startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            shortcut_path = os.path.join(startup_folder, "HardwareMonitor.bat")
            
            with open(shortcut_path, "w") as f:
                if is_exe:
                    f.write(f'@echo off\ncd /d "{os.path.dirname(target_path)}"\nstart "" "{os.path.basename(target_path)}"\n')
                else:
                    f.write(f'@echo off\ncd /d "{os.path.dirname(target_path)}"\nstart "" py "{os.path.basename(target_path)}"\n')
            
            file_type = ".exe" if is_exe else ".py"
            log_console(f"Startup configured ({file_type})", "success")
            tb.dialogs.Messagebox.show_info(f"Startup configured! The app will start on boot.\nUsing: {file_type} from {os.path.dirname(target_path)}\nShortcut created at: {shortcut_path}", "Success")
        except Exception as e:
            log_console(f"Error: {e}", "error")
            tb.dialogs.Messagebox.show_error(f"Failed to configure startup: {e}", "Error")
            
    elif sys.platform.startswith('linux'):
        try:
            autostart_dir = os.path.join(os.path.expanduser('~'), '.config', 'autostart')
            if not os.path.exists(autostart_dir):
                os.makedirs(autostart_dir)
            desktop_file_path = os.path.join(autostart_dir, "hardware-monitor.desktop")
            
            if is_exe:
                exec_command = target_path
            else:
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
            log_console(f"Startup configured ({file_type})", "success")
            tb.dialogs.Messagebox.show_info(f"Startup configured! The app will start on boot.\nUsing: {file_type}", "Success")
        except Exception as e:
            log_console(f"Error: {e}", "error")
            tb.dialogs.Messagebox.show_error(f"Failed to configure startup: {e}", "Error")
            
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
            log_console(f"Startup configured ({file_type})", "success")
            tb.dialogs.Messagebox.show_info(f"Startup configured! The app will start on boot.\nUsing: {file_type}", "Success")
        except Exception as e:
            log_console(f"Error: {e}", "error")
            tb.dialogs.Messagebox.show_error(f"Failed to configure startup: {e}", "Error")
    else:
        log_console("Unsupported OS", "warning")
        tb.dialogs.Messagebox.show_warning("Startup not configured. Unsupported OS.", "Warning")

def clear_startup_and_cache():
    """Removes startup configurations and data files."""
    log_console("Clearing config...", "info")
    cleared_startup = False
    
    if sys.platform.startswith('win'):
        try:
            startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            bat_path = os.path.join(startup_folder, "HardwareMonitor.bat")
            if os.path.exists(bat_path):
                os.remove(bat_path)
                log_console("Removed startup file", "success")
                cleared_startup = True
        except Exception as e:
            log_console(f"Error: {e}", "error")
            
    elif sys.platform.startswith('linux'):
        try:
            autostart_dir = os.path.join(os.path.expanduser('~'), '.config', 'autostart')
            desktop_file_path = os.path.join(autostart_dir, "hardware-monitor.desktop")
            if os.path.exists(desktop_file_path):
                os.remove(desktop_file_path)
                log_console("Removed startup file", "success")
                cleared_startup = True
        except Exception as e:
            log_console(f"Error: {e}", "error")
            
    elif sys.platform == 'darwin':
        try:
            plist_dir = os.path.join(os.path.expanduser('~'), 'Library', 'LaunchAgents')
            plist_path = os.path.join(plist_dir, "com.alohasnackbar.hwmonitor.plist")
            if os.path.exists(plist_path):
                os.remove(plist_path)
                log_console("Removed startup file", "success")
                cleared_startup = True
        except Exception as e:
            log_console(f"Error: {e}", "error")

    cleared_cache = False
    try:
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            log_console(f"Removed {CONFIG_FILE}", "success")
            cleared_cache = True
    except Exception as e:
        log_console(f"Error: {e}", "error")
        
    if cleared_startup or cleared_cache:
        tb.dialogs.Messagebox.show_info("Startup configuration and local cache files have been removed.", "Cleanup Complete")
    else:
        tb.dialogs.Messagebox.show_info("No startup configuration or local cache files were found to remove.", "Cleanup Complete")

# Buttons
button_frame = tk.Frame(controls_frame, bg=bg_color)
button_frame.pack(fill="x", pady=(10, 5))

startup_button = tb.Button(
    button_frame,
    text="Set Startup at Boot",
    bootstyle="info-outline",
    command=setup_startup_boot
)
startup_button.pack(side=tk.LEFT, padx=5, fill="x", expand=True)

cleanup_button = tb.Button(
    button_frame,
    text="Clear Startup Config",
    bootstyle="warning-outline",
    command=clear_startup_and_cache
)
cleanup_button.pack(side=tk.LEFT, padx=5, fill="x", expand=True)

# Diagnostic and Monitor Info buttons
diag_button_frame = tk.Frame(controls_frame, bg=bg_color)
diag_button_frame.pack(fill="x", pady=(5, 5))

diagnostic_button = tb.Button(
    diag_button_frame,
    text="Debug Detected Hardware",
    bootstyle="danger-outline",
    command=run_diagnostic
)
diagnostic_button.pack(side=tk.LEFT, padx=(10, 5), fill="x", expand=True)

monitor_info_button = tb.Button(
    diag_button_frame,
    text="Display out",
    bootstyle="light-outline",
    command=show_monitor_info
)
monitor_info_button.pack(side=tk.LEFT, padx=(5, 10), fill="x", expand=True)

tb.Separator(controls_frame, orient="horizontal").pack(fill="x", padx=10, pady=10)

## Main App Button
def save_and_close():
    """Save configuration and start the main application."""
    log_console("Starting monitor...", "info")
    
    root.destroy()
    
    target_path, is_exe = get_target_file()
    
    if target_path:
        try:
            if is_exe:
                subprocess.run([target_path], check=True)
            else:
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