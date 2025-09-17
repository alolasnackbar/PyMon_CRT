import ttkbootstrap as tb
from ttkbootstrap.constants import *
import threading
import queue
from screeninfo import get_monitors
import os
import sys
import subprocess

from constants import *
from crt_graphics import CRTGrapher, ThreadedDataFetcher
from metrics_layout import build_metrics
from startup_loader import startup_loader
import monitor_core as core

# --- Refresh Tiers ---
REFRESH_GUI_MS = 100
REFRESH_HEAVY_MS = REFRESH_MS * 5
REFRESH_SLOW_MS = REFRESH_MS * 2

# --- Global Settings ---
network_results = {"in_MB": 0, "out_MB": 0, "latency_ms": 0}
NETWORK_INTERFACE = None
PING_HOST = "8.8.8.8"
PING_COUNT = 3
data_queue = queue.Queue()

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

# ==== Main GUI Setup =============
root = tb.Window(themename="darkly")
root.title("AlohaSnackBar Hardware Monitor")

fullscreen = False  # Initialize here to use in startup geometry

# Set window position based on saved config
monitor_idx = get_startup_monitor()
try:
    monitors = get_monitors()
    if 0 < monitor_idx <= len(monitors):
        monitor = monitors[monitor_idx - 1]
        # Auto-fullscreen for smaller resolutions
        if monitor.width <= 960 and monitor.height <= 600:
            root.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
            root.overrideredirect(True)
            fullscreen = True
        else:
            root.geometry(f"960x600+{monitor.x + 100}+{monitor.y + 100}")
    else:
        root.geometry("960x600")
except Exception:
    root.geometry("960x600") # Fallback if get_monitors fails

# Configure root grid weights for resizing
for i in range(3):
    root.rowconfigure(i, weight=1)
for i in range(2):
    root.columnconfigure(i, weight=1)

style = tb.Style()

# ==== Menu Bar =============
main_menu = tb.Menu(root)
root.config(menu=main_menu)

# --- Sub-menus ---
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

# ==== Build Widgets & Graphics ============
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

# ==== Helper Functions =================
def get_temp_color(value):
    """Returns a color based on temperature thresholds."""
    if value is None: return CRT_GREEN
    if value < 75: return CRT_GREEN
    elif value < 90: return CRT_YELLOW
    else: return CRT_RED

def get_usage_color(value):
    """Returns a color based on usage percentage thresholds."""
    if value is None: return CRT_GREEN
    if value < 60: return CRT_GREEN
    elif value < 80: return CRT_YELLOW
    else: return CRT_RED

# ==== Fullscreen Management =============
prev_geometry = None

def get_current_monitor_geometry():
    """Finds the geometry of the monitor the window is currently on."""
    try:
        x, y = root.winfo_x(), root.winfo_y()
        for m in get_monitors():
            if m.x <= x < m.x + m.width and m.y <= y < m.y + m.height:
                return m.width, m.height, m.x, m.y
        # Fallback to primary if window is out of bounds
        primary = [m for m in get_monitors() if m.is_primary][0]
        return primary.width, primary.height, primary.x, primary.y
    except Exception:
        return 1920, 1080, 0, 0 # Generic fallback

def toggle_fullscreen(event=None):
    """Toggles the application's fullscreen state."""
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

# Bindings
root.bind("<F11>", toggle_fullscreen)
root.bind("<Escape>", lambda e: toggle_fullscreen())

# =================================================
# ==== GUI Update Loops ================
def _update_metric_display(key, history):
    """Updates a primary metric widget (CPU, GPU, RAM)."""
    val = history.get(key, [None])[-1]
    if val is None:
        return

    lbl, bar, cvs, maxv, overlay_lbl = widgets[key]
    lbl_color = get_usage_color(val)

    # --- Use fixed-width formatting to prevent widget shifting ---
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
            # 1. Calculate the center of the FILLED portion of the bar
            # new_relx is a value from 0.0 to 0.5
            new_relx = (val / 200) 
            
            # 2. Hide text if the bar is too empty to fit it, otherwise show it
            display_text = f"{val:.1f}%" if val > 15 else ""

            # 3. Update the label's color AND text
            overlay_lbl.config(
                text=display_text, 
                background=lbl_color, # Match the bar's color
                foreground="black"    # Use black text for contrast
            )

            # 4. Update the label's position to the new center
            overlay_lbl.place_configure(relx=new_relx)
    else: # GPU
        lbl.config(foreground=lbl_color, text=f"{key} Usage: {val:>5.1f}%")

    style.configure(bar._style_name, background=lbl_color)
    bar["value"] = val
    crt_grapher.draw_metric(cvs, history[key], maxv, color=lbl_color)

def update_gui():
    """Main high-frequency GUI update loop."""
    try:
        while not data_queue.empty():
            history = data_queue.get_nowait()
            crt_grapher.frame_count += 3

            # Update primary metrics
            for key in ["CPU", "RAM", "GPU"]:
                _update_metric_display(key, history)

            # Update Disk I/O graphics and labels
            read_mb = history.get("DISK_read", [0])[-1]
            write_mb = history.get("DISK_write", [0])[-1]
            crt_grapher.update_dual_io_labels(read_mb, write_mb)
            crt_grapher.draw_dual_io(history["DISK_read"], history["DISK_write"])
            
    except queue.Empty:
        pass
    finally:
        root.after(REFRESH_GUI_MS, update_gui)

def update_heavy_stats():
    """Worker thread for less frequent, more intensive stat updates."""
    def worker():
        try:
            # Fetch all data in the background
            cpu_info = core.get_cpu_info()
            gpu_info = core.get_gpu_info() or "N/A"
            disk_use = core.get_disk_summary()
            cpu_temp = core.get_cpu_temp()
            gpu_temp = core.get_gpu_temp()
            procs = core.get_top_processes(limit=5)
            load_avg = core.get_load_average()
            uptime = core.get_uptime()
            top_text = "PID      USER        VIRT      RES   CPU%   MEM%   NAME\n" + "\n".join(procs)

            # --- Apply updates to the GUI on the main thread ---
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

                # --- Network & Latency (from shared global) ---
                net_in = network_results['in_MB']
                net_out = network_results['out_MB']
                lat = network_results['latency_ms']
                info_labels["Net IN"].config(text=f"Net IN: {net_in:>6.2f} MB/s")
                info_labels["Net OUT"].config(text=f"Net OUT: {net_out:>6.2f} MB/s")
                lat_text = f"Latency: {lat:>5.1f} ms" if lat is not None else "Latency:   N/A"
                info_labels["Latency"].config(text=lat_text)
                
                # --- Processing Stats Tab ---
                cpu_labels = widgets["CPU Stats"]
                cpu_labels["Info"].config(text=f"CPU Load Avg: {load_avg}   Uptime: {uptime}")
                cpu_labels["Top Processes"].config(text=top_text)
                
                # --- Update Temperature Stats Tab (Safely) ---
                if "Temp Stats" in widgets:
                    temp_widgets = widgets["Temp Stats"]
                    
                    # Safely update CPU Meter if it exists
                    if "CPU Meter" in temp_widgets:
                        if cpu_temp is not None:
                            temp_widgets["CPU Meter"].configure(amountused=cpu_temp, subtext=f"{cpu_temp:.1f}°C", bootstyle=get_temp_color(cpu_temp))
                        else:
                            temp_widgets["CPU Meter"].configure(amountused=0, subtext="N/A", bootstyle="default")
                    
                    # Safely update GPU Meter if it exists
                    if "GPU Meter" in temp_widgets:
                        if gpu_temp is not None:
                            temp_widgets["GPU Meter"].configure(amountused=gpu_temp, subtext=f"{gpu_temp:.1f}°C", bootstyle=get_temp_color(gpu_temp))
                        else:
                            temp_widgets["GPU Meter"].configure(amountused=0, subtext="N/A", bootstyle="default")

            root.after(0, apply_updates)

        except Exception as e:
            print(f"Heavy stats worker error: {e}")
        finally:
            root.after(REFRESH_HEAVY_MS, update_heavy_stats)

    threading.Thread(target=worker, daemon=True).start()

def update_network_stats():
    """Worker thread for network stats."""
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
        finally:
            root.after(REFRESH_SLOW_MS, update_network_stats)
            
    threading.Thread(target=worker, daemon=True).start()


def update_time():
    """Updates the time and date display once per second."""
    date_lbl, time_lbl = widgets["Time & Uptime"]
    time_lbl.config(text=core.get_local_time())
    date_lbl.config(text=f"Date: {core.get_local_date()}")
    root.after(1000, update_time)

# =======================================================
# ==== Application Start ================================
def start_app():
    """Initializes all data fetching threads and GUI update loops."""
    data_fetcher = ThreadedDataFetcher(data_queue, interval=REFRESH_MS / 1000)
    data_fetcher.start()
    update_network_stats()
    update_heavy_stats()
    update_time()
    update_gui()

if __name__ == "__main__":
    # Run setup script on first launch
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    # Get monitor information from config file
    if not os.path.exists(os.path.join(script_dir, "startup_config.txt")):
        # Handle the case where the file doesn't exist (e.g., first launch)
        try:
            subprocess.run([sys.executable, os.path.join(script_dir, "startup_set.py")], check=True)
            # Exit if the user closes the setup window without saving
            if not os.path.exists(os.path.join(script_dir, "startup_config.txt")):
                sys.exit("Setup was not completed. Exiting.")
        except Exception as e:
            print(f"Could not run startup_set.py: {e}")
            sys.exit(1)

    startup_monitor_index = get_startup_monitor() 

    # Start the application with the animated loader
    startup_loader(root, widgets, style, on_complete=start_app)
    root.mainloop()