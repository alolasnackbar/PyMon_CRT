import ttkbootstrap as tb
from ttkbootstrap.constants import *
import monitor_core as core
import threading

from constants import *
from crt_graphics import draw_crt_grid, draw_crt_line, draw_dual_io, draw_metric
from metrics_layout import build_metrics   # <-- NEW import

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
root.geometry("960x640")

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
    """Run network usage & ping in a separate thread."""
    global network_results
    try:
        net_in, net_out, avg_latency = core.net_usage_latency(
            interface=NETWORK_INTERFACE, 
            ping_host_addr=PING_HOST,  # matches core function
            ping_count=PING_COUNT
        )
        network_results["in_MB"] = net_in
        network_results["out_MB"] = net_out
        network_results["latency_ms"] = avg_latency
    except Exception as e:
        print("Network stats error:", e)

def schedule_network_update():
    threading.Thread(target=update_network_stats, daemon=True).start()
    root.after(1000, schedule_network_update)  # every 1 second

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
            if core_freq:
                freq_ghz = core_freq / 1000
                lbl.config(
                    foreground=lbl_color,
                    text=f"CPU Usage: {val:.1f}%  CPU Speed: {freq_ghz:.1f} GHz"
                )
            else:
                lbl.config(
                    foreground=lbl_color,
                    text=f"CPU Usage: {val:.1f}%  CPU Hz: N/A"
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
    info_labels["CPU Model"].config(text=f"CPU Model: {cpu_info['model']}")
    info_labels["Cores"].config(
        text=f"{cpu_info['physical_cores']} CORES | {cpu_info['logical_cores']} THREADS | {core_freq/1000:.1f} GHz"
    )
    info_labels["GPU"].config(text=f"GPU: {gpu_info}")
    info_labels["Net IN"].config(text=f"Net IN: {network_results['in_MB']:.2f} MB/s")
    info_labels["Net OUT"].config(text=f"Net OUT: {network_results['out_MB']:.2f} MB/s")
    lat = network_results['latency_ms']
    info_labels["Latency"].config(
        text=f"Latency: {lat:.1f} ms" if lat is not None else "Latency: N/A"
    )

    # === Dedicated Time & Uptime widget ===
    time_lbl, uptime_lbl = widgets["Time & Uptime"]
    time_lbl.config(text=f"Time: {core.get_local_time()}")
    uptime_lbl.config(text=f"Uptime: {core.get_uptime()}")

    # schedule next update
    root.after(REFRESH_MS, update_stats)

# ==== Start everything ====
schedule_network_update()
update_stats()
root.mainloop()
