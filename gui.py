import ttkbootstrap as tb
from ttkbootstrap.constants import *
import threading
import queue
import pygetwindow as gw
import ctypes
from screeninfo import get_monitors

from constants import *
from crt_graphics import CRTGrapher, ThreadedDataFetcher
from metrics_layout import build_metrics
from startup_loader import startup_loader
import monitor_core as core

# refresh tiers
REFRESH_GUI_MS = 100 # GUI refresh rate
REFRESH_HEAVY_MS = REFRESH_MS * 5 # Sysinfo/Processes (heavy)
REFRESH_SLOW_MS = REFRESH_MS * 2 # Added for network updates

# ==== Global settings ====
network_results = {"in_MB": 0, "out_MB": 0, "latency_ms": 0}
NETWORK_INTERFACE = None
PING_HOST = "8.8.8.8"
PING_COUNT = 3

# Thread-safe queue for communication
data_queue = queue.Queue()

# ==== Main GUI setup ====
root = tb.Window(themename="darkly")
root.title("AlohaSnackBar Hardware Monitor")
root.geometry("960x600")

# Configure root grid weights
for i in range(3):
    root.rowconfigure(i, weight=1)
for i in range(2):
    root.columnconfigure(i, weight=1)

style = tb.Style()

# ==== Build Metrics ====
widgets = build_metrics(root, style)

# Initialize the CRTGrapher instance
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

# ==== Helper functions ====
def get_usage_color(value):
    if value < 60: return CRT_GREEN
    elif value < 80: return CRT_YELLOW
    else: return CRT_RED

# ==== Background network update ====
def update_network_stats():
    global network_results
    try:
        net_in, net_out, avg_latency = core.net_usage_latency(
            interface=NETWORK_INTERFACE,
            ping_host_addr=PING_HOST,
            ping_count=PING_COUNT
        )
        network_results["in_MB"] = net_in
        network_results["out_MB"] = net_out
        network_results["latency_ms"] = avg_latency
    except Exception as e:
        print("Network stats error:", e)

def schedule_network_update():
    threading.Thread(target=update_network_stats, daemon=True).start()
    root.after(REFRESH_SLOW_MS, schedule_network_update)

# ==== Fullscreen Utilities ====
fullscreen = False
prev_geometry = None

def get_current_monitor_geometry():
    x = root.winfo_x() + root.winfo_width() // 2
    y = root.winfo_y() + root.winfo_height() // 2
    for m in get_monitors():
        if m.x <= x < m.x + m.width and m.y <= y < m.y + m.height:
            return m.width, m.height, m.x, m.y
    primary = [m for m in get_monitors() if m.is_primary][0]
    return primary.width, primary.height, primary.x, primary.y

def enter_fullscreen():
    global fullscreen, prev_geometry
    if fullscreen: return
    fullscreen = True
    prev_geometry = root.geometry()
    w, h, x, y = get_current_monitor_geometry()
    root.overrideredirect(True)
    root.geometry(f"{w}x{h}+{x}+{y}")

def exit_fullscreen(event=None):
    global fullscreen
    if not fullscreen: return
    fullscreen = False
    root.overrideredirect(False)
    if prev_geometry:
        root.geometry(prev_geometry)

def toggle_fullscreen(event=None):
    if fullscreen:
        exit_fullscreen()
    else:
        enter_fullscreen()

def monitor_tracker():
    if fullscreen:
        w, h, x, y = get_current_monitor_geometry()
        root.geometry(f"{w}x{h}+{x}+{y}")
    else:
        root.geometry("960x600")
    root.after(500, monitor_tracker)

# ==== Bindings ====
root.bind("<F11>", toggle_fullscreen)
root.bind("<Escape>", exit_fullscreen)
monitor_tracker()

# ==== Main update loop for the GUI ====
def _update_metric_display(key, history, usage_values):
    val = usage_values[key]
    if val is None:
        return
    
    lbl, bar, cvs, maxv, overlay_lbl = widgets[key]
    lbl_color = get_usage_color(val) if val == max(v for v in usage_values.values() if v is not None) else CRT_GREEN

    if key == "CPU":
        freq_tuple = core.get_cpu_freq()
        freq_text = f"{freq_tuple[0]:.2f} GHz" if freq_tuple else "N/A"
        lbl.config(foreground=lbl_color, text=f"CPU Usage: {val:.1f}%  CPU Speed: {freq_text}")
    else:
        lbl.config(foreground=lbl_color, text=f"{key} Usage: {val:.1f}%")

    style.configure(bar._style_name, background=lbl_color)
    bar["value"] = val
    crt_grapher.draw_metric(cvs, history[key], maxv, color=lbl_color)
    
    if key == "RAM":
        ram_info = core.get_ram_info()
        lbl.config(text=f"RAM used {ram_info['used']} GB / free {ram_info['available']} GB")
        if overlay_lbl:
            overlay_lbl.config(text=f"{val:.1f}%", background=lbl_color)

def update_gui():
    try:
        while not data_queue.empty():
            history = data_queue.get_nowait()
            crt_grapher.frame_count += 3

            # Update CPU, RAM, GPU
            usage_values = {
                "CPU": history.get("CPU")[-1] if history.get("CPU") else None, 
                "RAM": history.get("RAM")[-1] if history.get("RAM") else None, 
                "GPU": history.get("GPU")[-1] if history.get("GPU") else None
            }

            for key in ["CPU", "RAM", "GPU"]:
                _update_metric_display(key, history, usage_values)

            # Update Disk I/O
            read_mb = history.get("DISK_read")[-1] if history.get("DISK_read") else 0
            write_mb = history.get("DISK_write")[-1] if history.get("DISK_write") else 0
            crt_grapher.update_dual_io_labels(read_mb, write_mb)
            crt_grapher.draw_dual_io(history["DISK_read"], history["DISK_write"])
            
    except queue.Empty:
        pass
    finally:
        root.after(REFRESH_GUI_MS, update_gui)

def update_heavy_stats():
    """SysInfo + Top Processes + Temps (run in a worker thread)."""
    def worker():
        try:
            # --- Fetch all data ---
            cpu_info = core.get_cpu_info()
            gpu_info = core.get_gpu_info()
            disk_use = core.get_disk_summary()
            
            cpu_temp = core.get_cpu_temp()
            gpu_temp = core.get_gpu_temp()
            #print("temp cvals",cpu_temp)
            #print("temp gvals",gpu_temp)
            procs = core.get_top_processes(limit=5)
            header = "PID      USER        VIRT      RES   CPU%   MEM%   NAME"
            top_text = header + "\n" + "\n".join(procs)

            load_avg = core.get_load_average()
            uptime = core.get_uptime()

            def apply_updates():
                # --- Update System Info Tab ---
                info_labels = widgets["Sys Info"]
                info_labels["CPU Model"].config(text=f"CPU Model: {cpu_info['model']}")
                info_labels["Cores"].config(
                    text=f"{cpu_info['physical_cores']} CORES | {cpu_info['logical_cores']} THREADS"
                )
                info_labels["GPU"].config(text=f"GPU: {gpu_info}")
                info_labels["DISK"].config(text=f"DISK USAGE: {disk_use}")
                info_labels["Net IN"].config(text=f"Net IN: {network_results['in_MB']:.2f} MB/s")
                info_labels["Net OUT"].config(text=f"Net OUT: {network_results['out_MB']:.2f} MB/s")
                lat = network_results['latency_ms']
                info_labels["Latency"].config(
                    text=f"Latency: {lat:.1f} ms" if lat is not None else "Latency: N/A"
                )
                info_labels["Uptime"].config(text=f"Uptime: {uptime}")

                # --- Update CPU Stats Tab ---
                cpu_labels = widgets["CPU Stats"]
                cpu_labels["Info"].config(text=f"CPU Load Avg: {load_avg}  Uptime: {uptime}")
                cpu_labels["Top Processes"].config(text=top_text)
                
                # --- Update Temperature Stats Tab ---
                temp_labels = widgets["Temp Stats"]
                if cpu_temp is not None:
                    temp_labels["CPU Temp"].config(text=f"CPU Temperature: {cpu_temp:.2f}°C")
                else:
                    temp_labels["CPU Temp"].config(text="CPU Temperature: N/A")
                
                if gpu_temp is not None:
                    temp_labels["GPU Temp"].config(text=f"GPU Temperature: {gpu_temp:.2f}°C")
                else:
                    temp_labels["GPU Temp"].config(text="GPU Temperature: N/A")

            root.after(0, apply_updates)

        except Exception as e:
            print("Heavy stats error:", e)

        finally:
            root.after(REFRESH_HEAVY_MS, update_heavy_stats)

    threading.Thread(target=worker, daemon=True).start()

def update_time():
    """Local time/date every 1000ms (lightweight)."""
    date_lbl, time_lbl = widgets["Time & Uptime"]
    time_lbl.config(text=f"{core.get_local_time()}")
    date_lbl.config(text=f"Date: {core.get_local_date()}")
    root.after(1000, update_time)

# ==== Start everything ====
def start_app():
    data_fetcher = ThreadedDataFetcher(data_queue, interval=REFRESH_MS / 1000)
    data_fetcher.start()
    schedule_network_update()
    update_heavy_stats()
    update_time()
    update_gui()

startup_loader(root, widgets, style, on_complete=start_app)
root.mainloop()
