import ttkbootstrap as tb
from ttkbootstrap.constants import *
import monitor_core as core
import threading

from constants import *
from crt_graphics import draw_crt_grid, draw_crt_line, draw_dual_io, draw_metric
from widgets import build_metric_frame, center_overlay_label

# ==== Global settings ====
history = {"CPU": [], "RAM": [], "GPU": [], "DISK_read": [], "DISK_write": []}
frame_count = 0
network_results = {"in_MB": 0, "out_MB": 0, "latency_ms": 0}  # store latest network stats
NETWORK_INTERFACE = None  # set your interface, e.g., "eth0" or "Wi-Fi"
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

# ---- Helper functions ----
def get_usage_color(value):
    if value < 60: return CRT_GREEN
    elif value < 80: return CRT_YELLOW
    else: return CRT_RED

# ==== Layout ====
metric_list = [
    {"name": "CPU", "maxval": 100, "row": 0, "col": 0},
    {"name": "GPU", "maxval": 100, "row": 1, "col": 0},
    {"name": "RAM", "maxval": 100, "row": 2, "col": 0}, 
    {"name": "Disk I/O", "maxval": DISK_IO_MAX_MBPS, "row": 0, "col": 1, "io": True},
    {"name": "Sys Info & Time", "row": 1, "col": 1, "rowspan": 2, "sysinfo": True}
]
widgets = {}

for metric in metric_list:
    name = metric["name"]
    row, col = metric["row"], metric["col"]
    colspan = metric.get("colspan", 1)
    rowspan = metric.get("rowspan", 1)

    if metric.get("io", False):
        f = tb.Labelframe(root, text=name, bootstyle=FONT_TAB_TITLE_COLOR)
        f.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=4, pady=4)
        root.rowconfigure(row, weight=1)
        root.columnconfigure(col, weight=1)

        io_read_lbl = tb.Label(f, text="READ: ...", anchor="w", font=FONT_TITLE, foreground=CRT_GREEN)
        io_read_lbl.pack(fill=X, padx=4, pady=(2,0))
        io_read_bar_style = f"IORead.Horizontal.TProgressbar"
        style.configure(io_read_bar_style, troughcolor="black", background=CRT_GREEN, thickness=PROGRESS_THICKNESS)
        io_read_bar = tb.Progressbar(f, bootstyle="success", maximum=DISK_IO_MAX_MBPS, style=io_read_bar_style)
        io_read_bar._style_name = io_read_bar_style
        io_read_bar.pack(fill=X, padx=4, pady=(0,2))

        io_write_lbl = tb.Label(f, text="WRITE: ...", anchor="w", font=FONT_TITLE, foreground="white")
        io_write_lbl.pack(fill=X, padx=4, pady=(2,0))
        io_write_bar_style = f"IOWrite.Horizontal.TProgressbar"
        style.configure(io_write_bar_style, troughcolor="black", background="white", thickness=PROGRESS_THICKNESS)
        io_write_bar = tb.Progressbar(f, bootstyle="success", maximum=DISK_IO_MAX_MBPS, style=io_write_bar_style)
        io_write_bar._style_name = io_write_bar_style
        io_write_bar.pack(fill=X, padx=4, pady=(0,2))

        io_canvas = tb.Canvas(f, height=GRAPH_HEIGHT, background="black", highlightthickness=0)
        io_canvas.pack(fill=BOTH, expand=True, padx=4, pady=4)
        widgets[name] = (io_read_lbl, io_write_lbl, io_read_bar, io_write_bar, io_canvas)

    elif metric.get("sysinfo", False):
        f = tb.Labelframe(root, text="System Info & Time", bootstyle=FONT_TAB_TITLE_COLOR)
        f.grid(row=row, column=col, columnspan=colspan, rowspan=rowspan, sticky="nsew", padx=4, pady=4)
        root.rowconfigure(row, weight=1)
        for c in range(col, col+colspan):
            root.columnconfigure(c, weight=1)

        time_lbl = tb.Label(f, text="Time: ...", anchor="w", font=("FONT_TITLE", 15, "bold"), foreground=CRT_GREEN)
        time_lbl.pack(fill=X, pady=(10,2))
        uptime_lbl = tb.Label(f, text="Uptime: ...", anchor="w", font=("FONT_TITLE", 10, "bold"), foreground=CRT_GREEN)
        uptime_lbl.pack(fill=X, pady=(2,10))

        info_labels = {}
        for key in ["CPU Model", "Cores", "GPU"]:
            lbl = tb.Label(f, text=f"{key}: ...", anchor="w", font=FONT_TITLE, foreground=CRT_GREEN)
            lbl.pack(fill=X, padx=4, pady=1)
            info_labels[key] = lbl

        # Network info labels
        net_in_lbl = tb.Label(f, text="Net IN: ... MB/s", anchor="w", font=FONT_TITLE, foreground=CRT_GREEN)
        net_in_lbl.pack(fill=X, padx=4, pady=1)
        net_out_lbl = tb.Label(f, text="Net OUT: ... MB/s", anchor="w", font=FONT_TITLE, foreground=CRT_GREEN)
        net_out_lbl.pack(fill=X, padx=4, pady=1)
        latency_lbl = tb.Label(f, text="Latency: ... ms", anchor="w", font=FONT_TITLE, foreground=CRT_GREEN)
        latency_lbl.pack(fill=X, padx=4, pady=1)

        info_labels["Net IN"] = net_in_lbl
        info_labels["Net OUT"] = net_out_lbl
        info_labels["Latency"] = latency_lbl

        widgets[name] = (time_lbl, uptime_lbl, info_labels)

    else:
        f, lbl, bar, cvs, overlay_lbl = build_metric_frame(root, name, style=style)
        f.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        root.rowconfigure(row, weight=1)
        root.columnconfigure(col, weight=1)
        widgets[name] = (lbl, bar, cvs, metric["maxval"], overlay_lbl)
        if name == "RAM" and overlay_lbl:
            bar.bind("<Configure>", lambda e, b=bar, l=overlay_lbl: center_overlay_label(b, l))

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

    for key, val in usage_values.items():
        if val is None: continue
        history[key].append(val)
        if len(history[key]) > MAX_POINTS: history[key].pop(0)
        widget_tuple = widgets[key]
        lbl, bar, cvs, maxv = widget_tuple[:4]
        overlay_lbl = widget_tuple[4] if len(widget_tuple) > 4 else None

        lbl_color = get_usage_color(val) if val == max_metric else CRT_GREEN

        # Show CPU Hz next to CPU usage
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

    # Disk I/O
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

    # System info
    time_lbl, uptime_lbl, info_labels = widgets["Sys Info & Time"]
    time_lbl.config(text=f"Time: {core.get_local_time()}")
    uptime_lbl.config(text=f"Uptime: {core.get_uptime()}")

    cpu_info = core.get_cpu_info()
    gpu_info = core.get_gpu_info()
    info_labels["CPU Model"].config(text=f"CPU Model: {cpu_info['model']}")
    info_labels["Cores"].config(text=f"{cpu_info['physical_cores']} CORES | {cpu_info['logical_cores']} THREADS | {freq_ghz:.1f} average GHZ")
    info_labels["GPU"].config(text=f"GPU: {gpu_info}")

    # Non-blocking network stats
    info_labels["Net IN"].config(text=f"Net IN: {network_results['in_MB']:.2f} MB/s")
    info_labels["Net OUT"].config(text=f"Net OUT: {network_results['out_MB']:.2f} MB/s")
    lat = network_results['latency_ms']
    info_labels["Latency"].config(text=f"Latency: {lat:.1f} ms" if lat is not None else "Latency: N/A")
    root.after(REFRESH_MS, update_stats)
    #print("checking", network_results)
    
# ==== Start everything ====
schedule_network_update()

update_stats()
root.mainloop()
