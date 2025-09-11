import ttkbootstrap as tb
from ttkbootstrap.constants import *
import monitor_core as core
import threading
import pygetwindow as gw
import ctypes

from constants import *
from crt_graphics import draw_crt_grid, draw_crt_line, draw_dual_io, draw_metric
from metrics_layout import build_metrics   # <-- NEW import
from startup_loader import startup_loader
from screeninfo import get_monitors

# ==== Global settings ====
history = {"CPU": [], "RAM": [], "GPU": [], "DISK_read": [], "DISK_write": []}
frame_count = 0
network_results = {"in_MB": 0, "out_MB": 0, "latency_ms": 0}
NETWORK_INTERFACE = None
PING_HOST = "8.8.8.8"
PING_COUNT = 3

# ==== Main GUI setup ====
root = tb.Window(themename="darkly")
root.title("AlohaSnackBar Hardware Monitor")
root.geometry("960x600")

# Configure root grid weights
for i in range(3):  # rows
    root.rowconfigure(i, weight=1)
for i in range(2):  # columns
    root.columnconfigure(i, weight=1)

style = tb.Style()

# ==== Build Metrics ====
widgets = build_metrics(root, style)

# ---- Helper functions ----
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
    root.after(1000, schedule_network_update)

# ==== Fullscreen Utilities (Windows dynamic, multi-monitor) ====
fullscreen = False
prev_geometry = None  # store previous window size/position

def get_current_monitor_geometry():
    """Return width, height, x, y of the monitor containing the center of the window."""
    x = root.winfo_x() + root.winfo_width() // 2
    y = root.winfo_y() + root.winfo_height() // 2
    for m in get_monitors():
        if m.x <= x < m.x + m.width and m.y <= y < m.y + m.height:
            return m.width, m.height, m.x, m.y
    # fallback to primary monitor
    primary = [m for m in get_monitors() if m.is_primary][0]
    return primary.width, primary.height, primary.x, primary.y

def enter_fullscreen():
    global fullscreen, prev_geometry
    if fullscreen:
        return
    fullscreen = True
    # save current geometry
    prev_geometry = root.geometry()
    # get current monitor
    w, h, x, y = get_current_monitor_geometry()
    root.overrideredirect(True)  # remove window decorations
    root.geometry(f"{w}x{h}+{x}+{y}")

def exit_fullscreen(event=None):  # accept event
    global fullscreen
    if not fullscreen:
        return
    fullscreen = False
    root.overrideredirect(False)  # restore window decorations
    if prev_geometry:
        root.geometry(prev_geometry)

def toggle_fullscreen(event=None):
    if fullscreen:
        exit_fullscreen()
    else:
        enter_fullscreen()

def monitor_tracker():
    """If window is moved while fullscreen, resize to new monitor dynamically."""
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


# ==== Update function ====
def update_stats():
    global frame_count
    frame_count += 3

    cpu = core.get_cpu_usage()
    ram_percent = core.get_ram_usage()
    core_freq = core.get_cpu_freq()
    gpu = core.get_gpu_usage()
    usage_values = {"CPU": cpu, "RAM": ram_percent, "GPU": gpu}
    max_metric = max([v for v in usage_values.values() if v is not None] + [0])

    # === Update CPU, GPU, RAM ===
    for key, val in usage_values.items():
        if val is None:
            continue
        history[key].append(val)
        if len(history[key]) > MAX_POINTS:
            history[key].pop(0)

        lbl, bar, cvs, maxv, overlay_lbl = widgets[key]
        lbl_color = get_usage_color(val) if val == max_metric else CRT_GREEN

        if key == "CPU":
            freq_tuple = core.get_cpu_freq()
            if freq_tuple:
                current, min_freq, max_freq = freq_tuple
                freq_text = f"{current:.2f} GHz"
                if min_freq is not None and max_freq is not None and min_freq > 0 and max_freq > 0:
                    freq_text += f" (min {min_freq:.2f} / max {max_freq:.2f})"
                lbl.config(
                    foreground=lbl_color,
                    text=f"CPU Usage: {val:.1f}%  CPU Speed: {freq_text}"
                )
            else:
                lbl.config(
                    foreground=lbl_color,
                    text=f"CPU Usage: {val:.1f}%  CPU Speed: N/A"
                )
        else:
            lbl.config(foreground=lbl_color, text=f"{key} Usage: {val:.1f}%")

        style.configure(bar._style_name, background=lbl_color)
        bar["value"] = val
        draw_metric(cvs, history[key], maxv, color=lbl_color, frame_count=frame_count)

        if key == "RAM":
            ram_info = core.get_ram_info()
            lbl.config(text=f"RAM Utilized: {val:.1f}%")
            if overlay_lbl:
                overlay_lbl.config(
                    text=f"used {ram_info['used']} GB / free {ram_info['available']} GB",
                    background=lbl_color
                )

    # === Disk I/O ===
    read_mb, write_mb = core.get_disk_io(interval=0.5)
    if read_mb is not None:
        io_read_lbl, io_write_lbl, io_read_bar, io_write_bar, io_canvas = widgets["Disk I/O"]
        io_read_lbl.config(text=f"READ: {read_mb:.2f} MB/s")
        io_write_lbl.config(text=f"WRITE: {write_mb:.2f} MB/s")
        io_read_bar["value"] = min(read_mb, DISK_IO_MAX_MBPS)
        io_write_bar["value"] = min(write_mb, DISK_IO_MAX_MBPS)
        history["DISK_read"].append(read_mb)
        history["DISK_write"].append(write_mb)
        if len(history["DISK_read"]) > MAX_POINTS:
            history["DISK_read"].pop(0)
            history["DISK_write"].pop(0)
        draw_dual_io(io_canvas, history["DISK_read"], history["DISK_write"], frame_count=frame_count)

    # === Sys Info Tab ===
    info_labels = widgets["Sys Info"]
    cpu_info = core.get_cpu_info()
    gpu_info = core.get_gpu_info()
    disk_use = core.get_disk_summary()

    info_labels["CPU Model"].config(text=f"CPU Model: {cpu_info['model']}")
    info_labels["Cores"].config(
        text=f"{cpu_info['physical_cores']} CORES | {cpu_info['logical_cores']} THREADS | {freq_text}"
    )
    info_labels["GPU"].config(text=f"GPU: {gpu_info}")
    info_labels["DISK"].config(text=f"DISK USAGE: {disk_use}")
    info_labels["Net IN"].config(text=f"Net IN: {network_results['in_MB']:.2f} MB/s")
    info_labels["Net OUT"].config(text=f"Net OUT: {network_results['out_MB']:.2f} MB/s")
    lat = network_results['latency_ms']
    info_labels["Latency"].config(
        text=f"Latency: {lat:.1f} ms" if lat is not None else "Latency: N/A"
    )
    info_labels["Uptime"].config(text=f"Uptime: {core.get_uptime()}")

    # === Dedicated Time & Uptime widget ===
    date_lbl, time_lbl = widgets["Time & Uptime"]
    time_lbl.config(text=f"{core.get_local_time()}")  # Include AM/PM if formatted in core
    date_lbl.config(text=f"Date: {core.get_local_date()}")  # Include weekday if formatted in core

    root.after(REFRESH_MS, update_stats)

# ==== Start everything ====
def start_app():
    schedule_network_update()
    update_stats()

startup_loader(root, widgets, style, on_complete=start_app)

root.mainloop()
