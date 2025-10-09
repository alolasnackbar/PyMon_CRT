import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import threading
import queue
from screeninfo import get_monitors
import os
import sys
import subprocess
import time
import json # <-- Added

from constants import *
from crt_graphics import CRTGrapher, ThreadedDataFetcher
from metrics_layout import build_metrics
from startup_loader import startup_loader
import monitor_core as core
from PIL import Image, ImageTk

# ===== NETWORK TAB INTEGRATION =====
from network_tab_module import NetworkTabController, load_game_servers
# ===================================

# --- Configuration Dictionary to hold all settings ---
CONFIG = {}
CONFIG_FILE = "startup_config.txt"

# --- Globals ---
data_queue = queue.Queue()
network_results = {"in_MB": 0, "out_MB": 0, "latency_ms": 0}
last_resize_time = 0
RESIZE_DEBOUNCE_MS = 100 # Prevents excessive redrawing during resize

# Auto-cycling and smart focus globals
auto_cycle_timer = None
last_cycle_time = 0
current_tab_index = 0
smart_focus_active = False
focus_override_time = 0
FOCUS_OVERRIDE_DURATION = 10000 # 10 seconds in milliseconds
config_tab_was_manually_selected = False
MAIN_TABS_COUNT = 4 # Only cycle through first 4 tabs (excluding config)
current_color_scheme = {} # Will be set by load_config and update_color_scheme

# ===== NETWORK TAB CONTROLLER GLOBAL =====
network_controller = None
# =========================================

# -- relative path function for packaging
def resource_path(rel_path):
    """Return path to resource (works for script and PyInstaller onedir)."""
    if getattr(sys, "frozen", False):
        # When bundled by PyInstaller, the exe is in the same folder we want
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel_path)

# --- Refactored Startup & Configuration ---
def load_config():
    """Reads the configuration from the JSON file."""
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
    
    global CONFIG, current_color_scheme
    CONFIG = default_config.copy()
    # Assuming NORMAL_COLORS is imported from constants
    current_color_scheme = NORMAL_COLORS 
    
    try:
        with open(CONFIG_FILE, "r") as f:
            content = f.read().strip()
            try:
                # New format: JSON
                loaded_config = json.loads(content)
                if isinstance(loaded_config, dict):
                    CONFIG.update(loaded_config)
            except json.JSONDecodeError:
                # Old format: just monitor index (plain text)
                try:
                    CONFIG["monitor_index"] = int(content)
                except ValueError:
                    pass
    except FileNotFoundError:
        pass # Use defaults
        
    update_color_scheme(CONFIG["colorblind_mode"])

def save_config():
    """Saves the current CONFIG dictionary to the JSON file."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(CONFIG, f, indent=2)
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")

def get_startup_monitor():
    """Reads the selected monitor index from the global CONFIG."""
    return CONFIG.get("monitor_index", 0)

def open_startup_settings():
    """Closes the current GUI and re-runs the startup settings script."""
    root.destroy()
    
    # Get the directory where the executable/script is located
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        app_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Look for startup_set in the same directory as this executable
    exe_path = os.path.join(app_dir, "startup_set.exe")
    script_path = os.path.join(app_dir, "startup_set.py")
    
    if os.path.exists(exe_path):
        target_path = exe_path
        args = [target_path]
    elif os.path.exists(script_path):
        target_path = script_path
        args = [sys.executable, target_path]
    else:
        print(f"Error: Neither startup_set.py nor startup_set.exe found in {app_dir}")
        return

    try:
        subprocess.run(args, check=True)
    except FileNotFoundError:
        print(f"Error: {target_path} not found.")
    except subprocess.CalledProcessError:
        print("Error: The setup script failed to run.")

# ==============================================================================
# ==== Color Blind Support Functions
# ==============================================================================
def update_color_scheme(colorblind_mode=False):
    """Updates the color scheme based on colorblind mode setting."""
    global current_color_scheme
    # Check if FONT_INFOTXT and other necessary constants exist
    if 'NORMAL_COLORS' in globals() and 'COLORBLIND_COLORS' in globals():
        if colorblind_mode:
            current_color_scheme = COLORBLIND_COLORS
        else:
            current_color_scheme = NORMAL_COLORS
    else:
        # Fallback if constants.py is not loaded correctly
        current_color_scheme = {'success': CRT_GREEN, 'warning': 'yellow', 'danger': 'red'}

def get_color(color_type):
    """Gets color from current scheme."""
    return current_color_scheme.get(color_type, CRT_GREEN)

# ==============================================================================
# ==== Smart Tab Management
# ==============================================================================
def get_tab_count():
    """Returns the number of tabs in the notebook."""
    if "notebook" in widgets:
        return len(widgets["notebook"].tabs())
    return 0

def get_current_tab():
    """Returns the currently selected tab index."""
    if "notebook" in widgets:
        return widgets["notebook"].index(widgets["notebook"].select())
    return 0

def set_current_tab(index):
    """Sets the current tab by index."""
    global config_tab_was_manually_selected
    if "notebook" in widgets:
        tab_count = get_tab_count()
        if 0 <= index < tab_count:
            widgets["notebook"].select(index)
            # Track if config tab (index 4) was manually selected
            if index == 4:  # Config tab
                config_tab_was_manually_selected = True
            else:
                config_tab_was_manually_selected = False
            return True
    return False

def cycle_to_next_tab():
    """Cycles to the next tab in sequence (only main 4 tabs)."""
    global current_tab_index, config_tab_was_manually_selected
    
    # Don't cycle if user is on config tab and hasn't switched away
    current_tab = get_current_tab()
    if current_tab == 4 and config_tab_was_manually_selected: # Config tab
        update_status("Staying on config tab")
        return
    
    # Only cycle through main 4 tabs (0-3)
    current_tab_index = (current_tab_index + 1) % MAIN_TABS_COUNT
    set_current_tab(current_tab_index)
    update_status(f"Cycled to tab {current_tab_index + 1}")

def smart_focus_check(cpu_usage=0, cpu_temp=None, gpu_temp=None, latency=None):
    """Checks if smart focus should activate based on system conditions (only main 4 tabs)."""
    global smart_focus_active, focus_override_time, config_tab_was_manually_selected
    
    # Get config values from global CONFIG dictionary
    focus_enabled = CONFIG.get("focus_enabled", True)
    cpu_threshold = CONFIG.get("cpu_threshold", 80)
    temp_threshold = CONFIG.get("temp_threshold", 75)
    latency_threshold = CONFIG.get("latency_threshold", 200)

    if not focus_enabled:
        return
    
    # Don't override if user is on config tab and hasn't switched away
    current_tab = get_current_tab()
    if current_tab == 4 and config_tab_was_manually_selected: # Config tab
        return
    
    # Don't override if we recently had a focus override
    current_time = time.time() * 1000
    if current_time - focus_override_time < FOCUS_OVERRIDE_DURATION:
        return
    
    focus_triggered = False
    target_tab = 0 # Default to System Info
    reason = ""
    
    # Check CPU usage threshold
    if cpu_usage > cpu_threshold:
        target_tab = 1 # Processing Stats tab
        reason = f"High CPU: {cpu_usage:.1f}%"
        focus_triggered = True
    
    # Check temperature thresholds
    max_temp = None
    if cpu_temp is not None:
        max_temp = cpu_temp
    if gpu_temp is not None and (max_temp is None or gpu_temp > max_temp):
        max_temp = gpu_temp
        
    if max_temp and max_temp > temp_threshold:
        target_tab = 3 # Temperature Stats tab
        reason = f"High temp: {max_temp:.1f}°C"
        focus_triggered = True
    
    # Check network latency threshold
    if latency is not None and latency > latency_threshold:
        target_tab = 2 # Network Stats tab
        reason = f"High latency: {latency:.0f}ms"
        focus_triggered = True
    
    # Only switch if target is within main 4 tabs and different from current
    if focus_triggered and target_tab < MAIN_TABS_COUNT and get_current_tab() != target_tab:
        set_current_tab(target_tab)
        smart_focus_active = True
        focus_override_time = current_time
        update_status(f"Alert: {reason}")

def auto_cycle_tabs():
    """Handles automatic tab cycling (only main 4 tabs)."""
    global auto_cycle_timer, last_cycle_time, smart_focus_active, config_tab_was_manually_selected
    
    # Get config values from global CONFIG dictionary
    cycle_enabled = CONFIG.get("cycle_enabled", False)
    cycle_delay_sec = CONFIG.get("cycle_delay", 5)
    
    # Check if auto-cycling is enabled
    if not cycle_enabled:
        root.after(1000, auto_cycle_tabs) # Check again in 1 second
        return
    
    # Don't cycle if smart focus is active
    if smart_focus_active:
        smart_focus_active = False # Reset after one cycle
        cycle_delay_ms = cycle_delay_sec * 1000
        root.after(cycle_delay_ms, auto_cycle_tabs)
        return
    
    # Don't cycle if user is on config tab and hasn't switched away
    current_tab = get_current_tab()
    if current_tab == 4 and config_tab_was_manually_selected: # Config tab
        cycle_delay_ms = cycle_delay_sec * 1000
        root.after(cycle_delay_ms, auto_cycle_tabs)
        return
    
    # Cycle to next tab (only main 4 tabs)
    cycle_to_next_tab()
    
    # Schedule next cycle
    cycle_delay_ms = cycle_delay_sec * 1000
    root.after(cycle_delay_ms, auto_cycle_tabs)

def update_status(message):
    """Updates the status label in the config tab."""
    if "Config" in widgets and "status_label" in widgets["Config"]:
        # Compact status messages for the new layout
        max_length = 20
        if len(message) > max_length:
            message = message[:max_length-3] + "..."
        widgets["Config"]["status_label"].config(text=message)

# ==============================================================================
# ==== Live Configuration Change Handlers
# ==============================================================================
def on_config_change(config_key):
    """Generic handler for live configuration changes that immediately saves to file."""
    def handler(*args):
        if "Config" in widgets and config_key in widgets["Config"]:
            widget_var = widgets["Config"][config_key]
            if hasattr(widget_var, 'get'):
                new_value = widget_var.get()
                CONFIG[config_key] = new_value
                save_config()  # Save immediately to file
                
                # Special handling for colorblind mode
                if config_key == "colorblind_mode":
                    update_color_scheme(new_value)
                    mode_text = "enabled" if new_value else "disabled"
                    update_status(f"Color blind {mode_text}")
                else:
                    update_status(f"{config_key} updated")
    return handler

def on_threshold_change(config_key):
    """Handler for threshold values (CPU, temp, latency) with validation."""
    def handler(*args):
        if "Config" in widgets and config_key in widgets["Config"]:
            widget_var = widgets["Config"][config_key]
            if hasattr(widget_var, 'get'):
                try:
                    new_value = int(widget_var.get())
                    # Basic validation for thresholds
                    if config_key == "cpu_threshold" and (new_value < 1 or new_value > 100):
                        new_value = max(1, min(100, new_value))
                        widget_var.set(new_value)
                    elif config_key == "temp_threshold" and (new_value < 20 or new_value > 120):
                        new_value = max(20, min(120, new_value))
                        widget_var.set(new_value)
                    elif config_key == "latency_threshold" and (new_value < 1 or new_value > 5000):
                        new_value = max(1, min(5000, new_value))
                        widget_var.set(new_value)
                    
                    CONFIG[config_key] = new_value
                    save_config()  # Save immediately to file
                    update_status(f"{config_key} set to {new_value}")
                except (ValueError, tk.TclError):
                    # Invalid input - revert to current config value
                    widget_var.set(CONFIG.get(config_key, 80))
    return handler

def setup_config_bindings():
    """Sets up bindings and loads initial values for configuration controls with live saving."""
    if "Config" in widgets:
        config_frame = widgets["Config"]
        
        # 1. Load initial values from global CONFIG dictionary
        
        # Boolean variables with live change tracking
        bool_configs = [
            ("colorblind_mode", False),
            ("cycle_enabled", False), 
            ("focus_enabled", True)
        ]
        
        for key, default in bool_configs:
            if key in config_frame and hasattr(config_frame[key], 'set'):
                config_frame[key].set(CONFIG.get(key, default))
                # Bind live change handler
                config_frame[key].trace('w', on_config_change(key))
        
        # Integer variables with live change tracking
        int_configs = [
            ("cycle_delay", 5),
            ("process_count", 5)
        ]
        
        for key, default in int_configs:
            if key in config_frame and hasattr(config_frame[key], 'set'):
                config_frame[key].set(CONFIG.get(key, default))
                # Bind live change handler
                config_frame[key].trace('w', on_config_change(key))
        
        # Threshold variables with validation and live change tracking
        threshold_configs = [
            ("cpu_threshold", 80),
            ("temp_threshold", 75),
            ("latency_threshold", 200)
        ]
        
        for key, default in threshold_configs:
            if key in config_frame and hasattr(config_frame[key], 'set'):
                config_frame[key].set(CONFIG.get(key, default))
                # Bind threshold change handler with validation
                config_frame[key].trace('w', on_threshold_change(key))
        
        # 2. Bind the Apply Settings button to open startup_set.py
        if "apply_button" in config_frame:
            config_frame["apply_button"].configure(command=open_startup_settings)
            
        # 3. Initialize color scheme based on loaded config
        if "colorblind_mode" in config_frame and hasattr(config_frame["colorblind_mode"], 'get'):
            update_color_scheme(CONFIG.get("colorblind_mode", False))

# ==============================================================================
# ==== Main GUI Setup
# ==============================================================================
# Load configuration before setting up the window to get monitor index
load_config()

root = tb.Window(themename="darkly")
# safe icon loading:
try:
    icon_file = resource_path("nohead_test.ico")
    if os.path.exists(icon_file):
        root.iconbitmap(icon_file)
    else:
        # fallback: try PNG via Pillow and iconphoto (more flexible)
        try:
            from PIL import Image, ImageTk
            png = resource_path("nohead_test.png")
            if os.path.exists(png):
                root._icon_img = ImageTk.PhotoImage(Image.open(png))
                root.iconphoto(False, root._icon_img)
        except Exception:
            # silent fallback to default icon
            pass
except tk.TclError as e:
    # Do not crash the app; print a warning instead
    print("Warning: failed to set window icon:", e)
    
root.title("AlohaSnackBar Hardware Monitor")
root.iconbitmap(resource_path('nohead_test.ico'))
root.minsize(580, 450) # Set minimum size to maintain readability

# --- Initial Geometry ---
fullscreen = False
monitor_idx = get_startup_monitor()
try:
    monitors = get_monitors()
    if 0 < monitor_idx <= len(monitors):
        monitor = monitors[monitor_idx - 1]
        if monitor.width <= 960 and monitor.height <= 600:
            root.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
            root.overrideredirect(True)
            fullscreen = True
        else:
            # Center on the selected monitor if not setting fullscreen
            w, h = 960, 600
            x = monitor.x + (monitor.width - w) // 2
            y = monitor.y + (monitor.height - h) // 2
            root.geometry(f"{w}x{h}+{x}+{y}")
    else:
        # Default centering if monitor_idx is 0 or invalid
        w, h = 960, 600
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")
except Exception:
    root.geometry("960x600")

style = tb.Style()

# # ==============================================================================
# # ==== Menu Bar DEPRECATED FOR NOW BUT KEEP JUST IN CASE
# # ==============================================================================
# main_menu = tb.Menu(root)
# root.config(menu=main_menu)

# file_menu = tb.Menu(main_menu, tearoff=0)
# main_menu.add_cascade(label="Run", menu=file_menu)
# file_menu.add_command(label="Check Update", command=lambda: print("Update check clicked"))
# file_menu.add_separator()
# file_menu.add_command(label="Exit", command=root.quit)

# control_menu = tb.Menu(main_menu, tearoff=0)
# main_menu.add_cascade(label="Control", menu=control_menu)
# control_menu.add_command(label="Startup Settings", command=open_startup_settings)

# help_menu = tb.Menu(main_menu, tearoff=0)
# main_menu.add_cascade(label="Help", menu=help_menu)
# help_menu.add_command(label="WatDoing (Help)", command=lambda: print("Help clicked"))

# ==============================================================================
# ==== Build Widgets & Graphics
# ==============================================================================
widgets = build_metrics(root, style)

disk_io_widgets = widgets["Disk I/O"]
crt_grapher = CRTGrapher(
    canvas=widgets["CPU"][2],
    io_canvas=disk_io_widgets[4],
    max_io=DISK_IO_MAX_MBPS,
    style=style,
    io_read_bar=disk_io_widgets[2],
    io_write_bar=disk_io_widgets[3],
    io_read_lbl=disk_io_widgets[0],
    io_write_lbl=disk_io_widgets[1]
)

# Set up temperature CRT components
if "Temp Stats" in widgets:
    temp_widgets = widgets["Temp Stats"]
    crt_grapher.set_temp_components(
        temp_canvas=temp_widgets.get("Canvas"),
        temp_cpu_lbl=temp_widgets.get("CPU_Label"),
        temp_gpu_lbl=temp_widgets.get("GPU_Label")
    )

# Store latest history data to enable redrawing on resize
latest_history = {}

# ==============================================================================
# ==== Helper Functions
# ==============================================================================
def get_temp_color(value):
    # Uses CONFIG for dynamic threshold
    temp_threshold = CONFIG.get("temp_threshold", 75)
    if value is None: return "default"
    if value < temp_threshold * 0.75: return get_color('success')
    elif value < temp_threshold: return get_color('warning')
    else: return get_color('danger')

def get_usage_color(value):
    # Uses CONFIG for dynamic threshold
    cpu_threshold = CONFIG.get("cpu_threshold", 80)
    if value is None: return get_color('success')
    if value < cpu_threshold * 0.75: return get_color('success')
    elif value < cpu_threshold: return get_color('warning')
    else: return get_color('danger')

def parse_cpu_from_process_line(line):
    """Extract CPU percentage from a process line.
    Expected format: PID USER VIRT RES CPU% MEM% NAME
    Example: 1234 user 100.5M 50.2M 45.3 2.1 chrome.exe
    """
    try:
        parts = line.split()
        if len(parts) >= 7:  # Ensure we have enough columns
            cpu_str = parts[4]  # CPU% is the 5th column (index 4)
            return float(cpu_str)
    except (ValueError, IndexError):
        pass
    return 0.0

def get_net_color(value):
    # Colors for network speed (higher is better)
    if value is None or value < 1: return get_color('success')
    if value < 5: return get_color('warning')
    else: return get_color('danger')

def get_latency_color(value):
    # Uses CONFIG for dynamic threshold
    latency_threshold = CONFIG.get("latency_threshold", 200)
    # Colors for latency (lower is better)
    if value is None: return get_color('success')
    if value < latency_threshold * 0.3: return get_color('success')
    elif value < latency_threshold: return get_color('warning')
    else: return get_color('danger')


# ==============================================================================
# ==== Fullscreen & Resize Management
# ==============================================================================
prev_geometry = None

def get_current_monitor_geometry():
    try:
        x, y = root.winfo_x(), root.winfo_y()
        for m in get_monitors():
            if m.x <= x < m.x + m.width and m.y <= y < m.y + m.height:
                return m.width, m.height, m.x, m.y
        primary = [m for m in get_monitors() if m.is_primary][0]
        return primary.width, primary.height, primary.x, primary.y
    except Exception:
        return 1920, 1080, 0, 0

def toggle_fullscreen(event=None):
    global fullscreen, prev_geometry
    fullscreen = not fullscreen
    if fullscreen:
        prev_geometry = root.geometry()
        w, h, x, y = get_current_monitor_geometry()
        root.overrideredirect(True)
        root.geometry(f"{w}x{h}+{x}+{y}")
    else:
        root.overrideredirect(False)
        if prev_geometry:
            root.geometry(prev_geometry)

def handle_resize(event):
    """Debounces resize events and redraws graphs."""
    global last_resize_time
    # This check ensures we're not resizing a widget, but the main window
    if event.widget != root:
        return
        
    current_time = time.time() * 1000
    if (current_time - last_resize_time) > RESIZE_DEBOUNCE_MS:
        last_resize_time = current_time
        # Redraw graphs with the latest data if it exists
        if latest_history and hasattr(crt_grapher, 'redraw_all'):
            crt_grapher.redraw_all(latest_history)

# --- Bindings ---
root.bind("<F11>", toggle_fullscreen)
root.bind("<Escape>", lambda e: toggle_fullscreen())
root.bind("<Configure>", handle_resize)

# ==============================================================================
# ==== GUI Update Loops
# ==============================================================================
def _update_metric_display(key, history):
    val = history.get(key, [None])[-1]
    if val is None: return

    lbl, bar, cvs, maxv, overlay_lbl = widgets[key]
    lbl_color = get_usage_color(val)

    if key == "CPU":
        freq_tuple = core.get_cpu_freq()
        freq_text = f"{freq_tuple[0]:>4.2f} GHz" if freq_tuple and freq_tuple[0] else " N/A "
        lbl.config(foreground=lbl_color, text=f"CPU Usage: {val:>5.1f}%  CPU Speed: {freq_text}")
    elif key == "RAM":
        ram_info = core.get_ram_info()
        used = ram_info.get('used', 0)
        avail = ram_info.get('available', 0)
        lbl.config(foreground=lbl_color, text=f"RAM used {used:>5.2f} GB / free {avail:>5.2f} GB")
        if overlay_lbl:
            new_relx = (val / 200)
            display_text = f"{val:.1f}%" if val > 15 else ""
            overlay_lbl.config(text=display_text, background=lbl_color, foreground="black")
            overlay_lbl.place_configure(relx=new_relx)
    else: # GPU
        gpu_clocks = core.get_gpu_clock_speed()
        lbl.config(foreground=lbl_color, text=f"{key} Usage: {val:>5.1f}%  GPU Speed: {gpu_clocks} MHz")

    style.configure(bar._style_name, background=lbl_color)
    bar["value"] = val
    crt_grapher.draw_metric(cvs, history[key], maxv, color=lbl_color)

def update_gui():
    global latest_history
    try:
        while not data_queue.empty():
            history = data_queue.get_nowait()
            latest_history = history # Save for resizing
            crt_grapher.frame_count += 3

            for key in ["CPU", "RAM", "GPU"]:
                _update_metric_display(key, history)

            read_mb = history.get("DISK_read", [0])[-1]
            write_mb = history.get("DISK_write", [0])[-1]
            crt_grapher.update_dual_io_labels(read_mb, write_mb)
            crt_grapher.draw_dual_io(history.get("DISK_read", []), history.get("DISK_write", []))
            
            # Update temperature CRT display with error handling
            try:
                cpu_temp_list = history.get("CPU_temp", [])
                gpu_temp_list = history.get("GPU_temp", [])
                
                cpu_temp_current = cpu_temp_list[-1] if cpu_temp_list else None
                gpu_temp_current = gpu_temp_list[-1] if gpu_temp_list else None
                
                if cpu_temp_current is not None or gpu_temp_current is not None:
                    crt_grapher.update_dual_temp_labels(cpu_temp_current, gpu_temp_current)
                    crt_grapher.draw_dual_temp(cpu_temp_list, gpu_temp_list)
            except (IndexError, AttributeError) as e:
                pass
            
            # Trigger smart focus check with current values
            cpu_usage = history.get("CPU", [0])[-1]
            cpu_temp = core.get_cpu_temp()
            gpu_temp = core.get_gpu_temp()
            latency = network_results.get('latency_ms')
            smart_focus_check(cpu_usage, cpu_temp, gpu_temp, latency)
            
    except queue.Empty:
        pass
    finally:
        root.after(REFRESH_GUI_MS, update_gui)

def update_heavy_stats():
    def worker():
        try:
            # Get process count from config
            process_limit = CONFIG.get("process_count", 5)
            
            # Fetch all data in the background
            cpu_info = core.get_cpu_info()
            freq_tuple = core.get_cpu_freq()
            gpu_info = core.get_gpu_info() or "N/A"
            disk_use = core.get_disk_summary()
            cpu_temp = core.get_cpu_temp()
            gpu_temp = core.get_gpu_temp()
            gpu_clocks = core.get_gpu_clock_speed()
            procs = core.get_top_processes(limit=process_limit)
            load_avg = core.get_load_average()
            uptime = core.get_uptime()

            def apply_updates():
                # --- Sys Info Tab ---
                info_labels = widgets["Sys Info"]
                info_labels["CPU Model"].config(text=f"CPU Model: {cpu_info.get('model', 'N/A')}")
                cores = cpu_info.get('physical_cores', 'N/A')
                threads = cpu_info.get('logical_cores', 'N/A')
                turbo_pct = ((freq_tuple[0] - freq_tuple[2]) / freq_tuple[2]) * 100
                info_labels["Cores"].config(text=f"{freq_tuple[2]} BASE SPEED | {turbo_pct:+.1f}% CORE MAX | {cores} CORES | {threads} THREADS")
                info_labels["GPU"].config(text=f"GPU: {gpu_info} | {gpu_clocks} Mhz")
                info_labels["DISK"].config(text=f"DISK USAGE: {disk_use}")
                info_labels["Uptime"].config(text=f"Uptime: {uptime}")

                # --- Network & Latency ---
                net_in = network_results['in_MB']
                net_out = network_results['out_MB']
                lat = network_results['latency_ms']

                # ===== NETWORK TAB INTEGRATION: Only update if in normal mode =====
                if info_labels.get("LatencyMode", "normal") == "normal":
                    info_labels["NetPrefix"].config(
                        text = f"Net Down/Upload:", 
                        foreground=get_latency_color(lat)
                    )
                    info_labels["Net IN"].config(
                        text=f"{net_in:.2f}🡫",
                        foreground=get_net_color(net_in)
                    )
                    info_labels["Net OUT"].config(
                        text=f"{net_out:.2f}🡩",
                        foreground=get_net_color(net_out)
                    )
                    info_labels["NetSuffix"].config(
                        text = f"MBs", 
                        foreground=get_latency_color(lat)
                    )

                    lat_text = f"Latency: {lat:>5.1f} ms" if lat is not None else "Latency:     N/A"
                    info_labels["Latency"].config(
                        text=lat_text,
                        foreground=get_latency_color(lat)
                    )
                # ==================================================================
                                
                # --- Processing Stats Tab (COLORIZED VERSION) ---
                cpu_labels = widgets["CPU Stats"]
                cpu_labels["Info"].config(text=f"CPU Load Avg: {load_avg}   Uptime: {uptime}")

                # Colorize the process list using Text widget
                proc_widget = cpu_labels["Top Processes"]
                proc_widget.configure(state="normal")
                proc_widget.delete("1.0", "end")

                # Insert header without color
                header = "PID      USER      VIRT  RES   CPU%   MEM%   NAME\n"
                proc_widget.insert("end", header)

                # Insert each process line with color based on CPU usage
                for proc_line in procs:
                    cpu_pct = parse_cpu_from_process_line(proc_line)
                    color = get_usage_color(cpu_pct)
                    
                    # Create unique tag for this line
                    tag_name = f"cpu_{cpu_pct}_{id(proc_line)}"
                    proc_widget.insert("end", proc_line + "\n", tag_name)
                    proc_widget.tag_config(tag_name, foreground=color)

                proc_widget.configure(state="disabled")
                
                # --- Temperature Stats Tab ---
                if "Temp Stats" in widgets:
                    temp_widgets = widgets["Temp Stats"]

                    if "Temp_Label" in temp_widgets:
                        cpu_text = f"{cpu_temp:.0f}°C" if cpu_temp is not None else "... °C"
                        gpu_text = f"{gpu_temp:.0f}°C" if gpu_temp is not None else "... °C"

                        temp_widgets["Temp_Label"].configure(state="normal")
                        temp_widgets["Temp_Label"].delete("1.0", "end")

                        temp_widgets["Temp_Label"].insert("end", f"CPU: {cpu_text}", "cpu")
                        temp_widgets["Temp_Label"].insert("end", " | ")
                        temp_widgets["Temp_Label"].insert("end", f"GPU: {gpu_text}", "gpu")

                        temp_widgets["Temp_Label"].tag_config("cpu", foreground=CRT_GREEN)
                        temp_widgets["Temp_Label"].tag_config("gpu", foreground="white")

                        temp_widgets["Temp_Label"].configure(state="disabled")

            root.after(0, apply_updates)
        except Exception as e:
            print(f"Heavy stats worker error: {e}")
        finally:
            root.after(REFRESH_HEAVY_MS, update_heavy_stats)
    threading.Thread(target=worker, daemon=True).start()

def update_network_stats():
    def worker():
        global network_results
        try:
            # Assuming NETWORK_INTERFACE, PING_HOST, and PING_COUNT are imported from constants
            net_in, net_out, avg_latency = core.net_usage_latency(
                interface=NETWORK_INTERFACE,
                ping_host_addr=PING_HOST,
                ping_count=PING_COUNT
            )
            network_results = {"in_MB": net_in, "out_MB": net_out, "latency_ms": avg_latency}
        except Exception as e:
            print(f"Network stats error: {e}")
            network_results = {"in_MB": 0.0, "out_MB": 0.0, "latency_ms": None}
        finally:
            root.after(REFRESH_SLOW_MS, update_network_stats)
    threading.Thread(target=worker, daemon=True).start()

def update_time():
    date_lbl, time_lbl = widgets["Time & Uptime"]
    time_lbl.config(text=core.get_local_time())
    date_lbl.config(text=f"Date: {core.get_local_date()}")
    root.after(1000, update_time)

# ==============================================================================
# ==== NETWORK TAB INTEGRATION HELPER
# ==============================================================================
def integrate_network_tab():
    """
    Integrates the network tab server ping functionality into the existing GUI.
    Should be called after widgets are built but before starting update loops.
    """
    global network_controller
    
    try:
        # Get the Sys Info tab's info_labels dictionary
        if "Sys Info" not in widgets:
            print("Warning: 'Sys Info' not found in widgets. Cannot integrate network tab.")
            return None
        
        info_labels = widgets["Sys Info"]
        
        # Find the Network Stats tab frame
        f_net = None
        if "NetFrame" in info_labels:
            # Get the parent of NetFrame which should be the tab frame
            f_net = info_labels["NetFrame"].master
        
        if f_net is None:
            print("Warning: Could not find Network Stats tab frame. Cannot integrate network tab.")
            return None
        
        # --- Add Server Ping UI Components ---
        # Separator
        separator1 = tb.Separator(f_net, orient="horizontal")
        separator1.grid(row=2, column=0, sticky="ew", padx=4, pady=6)

        # Server Selection Row
        server_select_frame = tb.Frame(f_net)
        server_select_frame.grid(row=3, column=0, sticky="ew", padx=4, pady=2)
        server_select_frame.columnconfigure(1, weight=1)

        # Server dropdown label
        server_combo_label = tb.Label(
            server_select_frame,
            text="Server:",
            anchor="w",
            font=FONT_NETTXT,
            foreground=CRT_GREEN
        )
        server_combo_label.grid(row=0, column=0, sticky="w", padx=(0, 4))

        selected_server = tk.StringVar()
        server_combo = tb.Combobox(
            server_select_frame,
            textvariable=selected_server,
            values=[],
            state="readonly",
            font=("Courier", 9),
            width=30
        )
        server_combo.grid(row=0, column=1, sticky="ew", padx=(0, 4))

        # Ping button
        ping_btn = tb.Button(
            server_select_frame,
            text="Ping",
            bootstyle="success-outline",
            width=8
        )
        ping_btn.grid(row=0, column=2, sticky="e", padx=(0, 2))

        # Config button
        config_btn = tb.Button(
            server_select_frame,
            text="⚙",
            bootstyle="success-outline",
            width=3
        )
        config_btn.grid(row=0, column=3, sticky="e")

        # Status label
        ping_status_lbl = tb.Label(
            f_net,
            text="Select server and click Ping to test",
            anchor="w",
            font=("Courier", 9),
            foreground="#888888"
        )
        ping_status_lbl.grid(row=4, column=0, sticky="w", padx=4, pady=2)

        # Results frame
        results_frame = tb.Frame(f_net)
        results_frame.grid(row=5, column=0, sticky="nsew", padx=4, pady=2)
        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)
        f_net.rowconfigure(5, weight=1)

        # Results text widget
        results_text = tk.Text(
            results_frame,
            height=10,
            font=("Courier", 9),
            bg="#1a1a1a",
            fg=CRT_GREEN,
            insertbackground=CRT_GREEN,
            state=tk.DISABLED,
            wrap=tk.WORD,
            relief="sunken",
            borderwidth=1
        )
        results_text.grid(row=0, column=0, sticky="nsew")

        # Scrollbar
        results_scrollbar = tb.Scrollbar(results_frame, command=results_text.yview)
        results_scrollbar.grid(row=0, column=1, sticky="ns")
        results_text.config(yscrollcommand=results_scrollbar.set)

        # Store references
        info_labels["ServerCombo"] = server_combo
        info_labels["SelectedServer"] = selected_server
        info_labels["PingButton"] = ping_btn
        info_labels["PingStatus"] = ping_status_lbl
        info_labels["ResultsText"] = results_text
        info_labels["ConfigButton"] = config_btn
        info_labels["LatencyMode"] = "normal"
        info_labels["LatencyRevertTimer"] = None
        
        # Create controller
        controller = NetworkTabController(root, info_labels)
        
        # Wire up commands
        ping_btn.config(command=controller.run_server_ping_test)
        config_btn.config(command=controller.open_server_config)
        
        # Load servers
        controller.load_servers()
        
        print("Network tab integration successful!")
        return controller
        
    except Exception as e:
        print(f"Warning: Could not integrate network tab: {e}")
        import traceback
        traceback.print_exc()
        return None

# ==============================================================================
# ==== Application Start
# ==============================================================================
def start_app():
    global network_controller
    
    # Assuming REFRESH_MS is imported from constants
    data_fetcher = ThreadedDataFetcher(data_queue, interval=REFRESH_MS / 1000)
    data_fetcher.start()
    update_network_stats()
    update_heavy_stats()
    update_time()
    update_gui()
    
    # Set up configuration bindings after widgets are created
    setup_config_bindings()
    
    # ===== INTEGRATE NETWORK TAB =====
    network_controller = integrate_network_tab()
    # =================================
    
    # Start auto-cycling after a short delay
    root.after(2000, auto_cycle_tabs)
    
    # Initial status
    update_status("Monitoring active")

# ==============================================================================
# ==== Application Close Handler
# ==============================================================================
def on_app_close():
    """Clean shutdown of all components."""
    global network_controller
    
    if network_controller:
        network_controller.shutdown()
    
    root.destroy()

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Check for config file and run setup if not found
    if not os.path.exists(CONFIG_FILE):
        print("First launch: running startup setup...")
        try:
            # Get the directory where the executable/script is located
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
            
            exe_path = os.path.join(app_dir, "startup_set.exe")
            script_path = os.path.join(app_dir, "startup_set.py")
            
            if os.path.exists(exe_path):
                args = [exe_path]
            elif os.path.exists(script_path):
                args = [sys.executable, script_path]
            else:
                sys.exit(f"Error: startup_set not found in {app_dir}. Exiting.")
            
            subprocess.run(args, check=True)
            
            # EXIT HERE - Don't continue running this instance
            sys.exit(0)  # <-- ADD THIS LINE
            
        except Exception as e:
            print(f"Could not run setup script: {e}")
            sys.exit(1)

    # This only runs if CONFIG_FILE exists (not first launch)
    
    # Set up close handler
    root.protocol("WM_DELETE_WINDOW", on_app_close)
    
    startup_loader(root, widgets, style, on_complete=start_app)
    root.mainloop()