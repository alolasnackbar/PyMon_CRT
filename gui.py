import ttkbootstrap as tb
from ttkbootstrap.constants import *
import threading
import queue
from screeninfo import get_monitors
import os
import sys
import subprocess
import time

from constants import *
from crt_graphics import CRTGrapher, ThreadedDataFetcher
from metrics_layout import build_metrics
from startup_loader import startup_loader
import monitor_core as core

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
FOCUS_OVERRIDE_DURATION = 10000  # 10 seconds in milliseconds

current_color_scheme = NORMAL_COLORS

# --- Startup & Configuration ---
def get_startup_monitor():
    """Reads the selected monitor index from the config file."""
    try:
        with open("startup_config.txt", "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0  # Default to current/primary monitor

def open_startup_settings():
    """Closes the current GUI and re-runs the startup settings script."""
    root.destroy()
    try:
        subprocess.run([sys.executable, "startup_set.py"], check=True)
    except FileNotFoundError:
        print("Error: startup_set.py not found.")
    except subprocess.CalledProcessError:
        print("Error: The setup script failed to run.")

# ==============================================================================
# ==== Color Blind Support Functions
# ==============================================================================
def update_color_scheme(colorblind_mode=False):
    """Updates the color scheme based on colorblind mode setting."""
    global current_color_scheme
    if colorblind_mode:
        current_color_scheme = COLORBLIND_COLORS
    else:
        current_color_scheme = NORMAL_COLORS

def get_color(color_type):
    """Gets color from current scheme."""
    return current_color_scheme.get(color_type, CRT_GREEN)

# ==============================================================================
# ==== Smart Tab Management
# ==============================================================================
def get_tab_count():
    """Returns the number of tabs in the notebook."""
    if "notebook" in widgets:
        return len(widgets["notebook"].tabs()) - 1
    return 0

def get_current_tab():
    """Returns the currently selected tab index."""
    if "notebook" in widgets:
        return widgets["notebook"].index(widgets["notebook"].select())
    return 0

def set_current_tab(index):
    """Sets the current tab by index."""
    if "notebook" in widgets:
        tab_count = get_tab_count()
        if 0 <= index < tab_count:
            widgets["notebook"].select(index)
            return True
    return False

def cycle_to_next_tab():
    """Cycles to the next tab in sequence."""
    global current_tab_index
    tab_count = get_tab_count()
    if tab_count > 0:
        current_tab_index = (current_tab_index + 1) % tab_count
        set_current_tab(current_tab_index)
        update_status(f"Tab {current_tab_index + 1}")

def smart_focus_check(cpu_usage=0, cpu_temp=None, gpu_temp=None, latency=None):
    """Checks if smart focus should activate based on system conditions."""
    global smart_focus_active, focus_override_time
    
    if "Config" not in widgets:
        return
    
    config = widgets["Config"]
    
    # Check if smart focus is enabled
    if not config.get("focus_enabled", tb.BooleanVar(value=True)).get():
        return
    
    # Don't override if we recently had a focus override
    current_time = time.time() * 1000
    if current_time - focus_override_time < FOCUS_OVERRIDE_DURATION:
        return
    
    focus_triggered = False
    target_tab = 0  # Default to System Info
    reason = ""
    
    # Check CPU usage threshold
    cpu_threshold = config.get("cpu_threshold", 80)
    if cpu_usage > cpu_threshold:
        target_tab = 1  # Processing Stats tab
        reason = f"CPU: {cpu_usage:.1f}%"
        focus_triggered = True
    
    # Check temperature thresholds
    temp_threshold = config.get("temp_threshold", 75)
    max_temp = None
    if cpu_temp is not None:
        max_temp = cpu_temp
    if gpu_temp is not None and (max_temp is None or gpu_temp > max_temp):
        max_temp = gpu_temp
        
    if max_temp and max_temp > temp_threshold:
        target_tab = 3  # Temperature Stats tab
        reason = f"Temp: {max_temp:.1f}°C"
        focus_triggered = True
    
    # Check network latency threshold
    latency_threshold = config.get("latency_threshold", 200)
    if latency and latency > latency_threshold:
        target_tab = 2  # Network Stats tab
        reason = f"Ping: {latency:.0f}ms"
        focus_triggered = True
    
    if focus_triggered and get_current_tab() != target_tab:
        set_current_tab(target_tab)
        smart_focus_active = True
        focus_override_time = current_time
        update_status(f"Alert: {reason}")

def auto_cycle_tabs():
    """Handles automatic tab cycling."""
    global auto_cycle_timer, last_cycle_time, smart_focus_active
    
    if "Config" not in widgets:
        root.after(5000, auto_cycle_tabs)  # Try again in 5 seconds
        return
    
    config = widgets["Config"]
    
    # Check if auto-cycling is enabled
    if not config.get("cycle_enabled", tb.BooleanVar(value=False)).get():
        root.after(1000, auto_cycle_tabs)  # Check again in 1 second
        return
    
    # Don't cycle if smart focus is active
    if smart_focus_active:
        smart_focus_active = False  # Reset after one cycle
        cycle_delay = config.get("cycle_delay", 5) * 1000
        root.after(cycle_delay, auto_cycle_tabs)
        return
    
    # Cycle to next tab
    cycle_to_next_tab()
    
    # Schedule next cycle
    cycle_delay = config.get("cycle_delay", 5) * 1000
    root.after(cycle_delay, auto_cycle_tabs)

def update_status(message):
    """Updates the status label in the config tab."""
    if "Config" in widgets and "status_label" in widgets["Config"]:
        # Truncate long messages to fit compact display
        max_length = 25
        if len(message) > max_length:
            message = message[:max_length-3] + "..."
        widgets["Config"]["status_label"].config(text=message)

# ==============================================================================
# ==== Main GUI Setup
# ==============================================================================
root = tb.Window(themename="darkly")
root.title("AlohaSnackBar Hardware Monitor")
root.minsize(580, 450) # Set a minimum size to maintain readability

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
            root.geometry(f"960x600+{monitor.x + 100}+{monitor.y + 100}")
    else:
        root.geometry("960x600")
except Exception:
    root.geometry("960x600")

# --- Configure Root Grid Weights for Resizing ---
for i in range(3):
    root.rowconfigure(i, weight=1)
for i in range(2):
    root.columnconfigure(i, weight=1)

style = tb.Style()

# ==============================================================================
# ==== Menu Bar
# ==============================================================================
main_menu = tb.Menu(root)
root.config(menu=main_menu)

file_menu = tb.Menu(main_menu, tearoff=0)
main_menu.add_cascade(label="Run", menu=file_menu)
file_menu.add_command(label="Check Update", command=lambda: print("Update check clicked"))
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

control_menu = tb.Menu(main_menu, tearoff=0)
main_menu.add_cascade(label="Control", menu=control_menu)
control_menu.add_command(label="Startup Settings", command=open_startup_settings)

help_menu = tb.Menu(main_menu, tearoff=0)
main_menu.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="WatDoing (Help)", command=lambda: print("Help clicked"))

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
# Store latest history data to enable redrawing on resize
latest_history = {}

# ==============================================================================
# ==== Helper Functions
# ==============================================================================
def get_temp_color(value):
    if value is None: return "default"
    if value < 50: return "success"
    elif value < 90: return "warning"
    else: return "danger"

def get_usage_color(value):
    if value is None: return get_color('success')
    if value < 60: return get_color('success')
    elif value < 80: return get_color('warning')
    else: return get_color('danger')

def get_net_color(value):
    # Colors for network speed (higher is better)
    if value is None or value < 1: return get_color('success')
    if value < 5: return get_color('warning')
    else: return get_color('danger')

def get_latency_color(value):
    # Colors for latency (lower is better)
    if value is None: return get_color('success')
    if value < 60: return get_color('success')
    elif value < 150: return get_color('warning')
    else: return get_color('danger')

# ==============================================================================
# ==== Configuration Change Handlers
# ==============================================================================
def on_colorblind_change():
    """Handles colorblind mode toggle."""
    if "Config" in widgets:
        colorblind_mode = widgets["Config"]["colorblind_mode"].get()
        update_color_scheme(colorblind_mode)
        update_status(f"ColorBlind: {'ON' if colorblind_mode else 'OFF'}")
        # Force a redraw of all colored elements
        if latest_history:
            # This will trigger color updates on next GUI refresh
            pass

def setup_config_bindings():
    """Sets up bindings for configuration changes."""
    if "Config" in widgets:
        config = widgets["Config"]
        # Bind colorblind mode change
        if "colorblind_mode" in config:
            config["colorblind_mode"].trace('w', lambda *args: on_colorblind_change())

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
        lbl.config(foreground=lbl_color, text=f"CPU Usage: {val:>5.1f}%   CPU Speed: {freq_text}")
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
        lbl.config(foreground=lbl_color, text=f"{key} Usage: {val:>5.1f}%")

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
            process_limit = 5  # Default
            if "Config" in widgets:
                process_limit = widgets["Config"].get("process_count", 5)
            
            # Fetch all data in the background
            cpu_info = core.get_cpu_info()
            gpu_info = core.get_gpu_info() or "N/A"
            disk_use = core.get_disk_summary()
            cpu_temp = core.get_cpu_temp()
            gpu_temp = core.get_gpu_temp()
            procs = core.get_top_processes(limit=process_limit)
            load_avg = core.get_load_average()
            uptime = core.get_uptime()
            top_text = "PID      USER          VIRT      RES   CPU%   MEM%   NAME\n" + "\n".join(procs)

            def apply_updates():
                # --- Sys Info Tab ---
                info_labels = widgets["Sys Info"]
                info_labels["CPU Model"].config(text=f"CPU Model: {cpu_info.get('model', 'N/A')}")
                cores = cpu_info.get('physical_cores', 'N/A')
                threads = cpu_info.get('logical_cores', 'N/A')
                info_labels["Cores"].config(text=f"{cores} CORES | {threads} THREADS")
                info_labels["GPU"].config(text=f"GPU: {gpu_info}")
                info_labels["DISK"].config(text=f"DISK USAGE: {disk_use}")
                info_labels["Uptime"].config(text=f"Uptime: {uptime}")

                # --- Network & Latency ---
                net_in = network_results['in_MB']
                net_out = network_results['out_MB']
                lat = network_results['latency_ms']
                info_labels["Net IN"].config(text=f"Net Download:{net_in:>6.2f} MB/s", foreground=get_net_color(net_in))
                info_labels["Net OUT"].config(text=f"Net Upload:  {net_out:>6.2f} MB/s", foreground=get_net_color(net_out))
                lat_text = f"Latency: {lat:>5.1f} ms" if lat is not None else "Latency:     N/A"
                info_labels["Latency"].config(text=lat_text, foreground=get_latency_color(lat))
                
                # --- Processing Stats Tab ---
                cpu_labels = widgets["CPU Stats"]
                cpu_labels["Info"].config(text=f"CPU Load Avg: {load_avg}   Uptime: {uptime}")
                cpu_labels["Top Processes"].config(text=top_text)
                
                # --- Temperature Stats Tab ---
                if "Temp Stats" in widgets:
                    temp_widgets = widgets["Temp Stats"]

                    if "GPU Meter" in temp_widgets and gpu_temp is not None:
                        color = get_temp_color(gpu_temp)
                        temp_widgets["GPU Meter"].configure(
                            amountused=gpu_temp,
                            bootstyle=color
                        )

                    if "CPU Meter" in temp_widgets and cpu_temp is not None:
                        color = get_temp_color(cpu_temp)
                        temp_widgets["CPU Meter"].configure(
                            amountused=cpu_temp,
                            bootstyle=color
                        )

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
# ==== Application Start
# ==============================================================================
def start_app():
    data_fetcher = ThreadedDataFetcher(data_queue, interval=REFRESH_MS / 1000)
    data_fetcher.start()
    update_network_stats()
    update_heavy_stats()
    update_time()
    update_gui()
    
    # Set up configuration bindings after widgets are created
    setup_config_bindings()
    
    # Start auto-cycling after a short delay
    root.after(2000, auto_cycle_tabs)
    
    # Initial status
    update_status("Started")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    if not os.path.exists("startup_config.txt"):
        print("First launch: running startup setup...")
        try:
            subprocess.run([sys.executable, "startup_set.py"], check=True)
            if not os.path.exists("startup_config.txt"):
                sys.exit("Setup was not completed. Exiting.")
        except Exception as e:
            print(f"Could not run startup_set.py: {e}")
            sys.exit(1)

    startup_loader(root, widgets, style, on_complete=start_app)
    root.mainloop()