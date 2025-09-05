import ttkbootstrap as tb
from ttkbootstrap.constants import *
import monitor_core as core

MAX_POINTS = 60
REFRESH_MS = 1000
history = {"CPU": [], "RAM": [], "GPU": [], "DISK_read": [], "DISK_write": []}
DISK_IO_MAX_MBPS = 500

# CRT colors and fonts
CRT_GREEN = "#00FF66"
CRT_YELLOW = "#FFFF00"
CRT_RED = "#FF4444"
CRT_GRID  = "#024D02"
FONT_TITLE = ("Courier", 9, "bold")
GRAPH_HEIGHT = 90
PROGRESS_THICKNESS = 35

# ==== GUI setup ====
root = tb.Window(themename="darkly")
root.title("AlohaSnackBar Hardware Monitor")
root.geometry("960x600")
root.columnconfigure((0,1), weight=1)
root.rowconfigure((0,1), weight=1)

style = tb.Style()

# ---- Helper functions ----
def get_usage_color(value):
    if value < 60: return CRT_GREEN
    elif value < 80: return CRT_YELLOW
    else: return CRT_RED

def draw_crt_grid(canvas):
    w, h = canvas.winfo_width(), canvas.winfo_height()
    if w < 10 or h < 10: return
    for x in range(0, w, max(1, w // 10)):
        canvas.create_line(x, 0, x, h, fill=CRT_GRID)
    for y in range(0, h, max(1, h // 5)):
        canvas.create_line(0, y, w, y, fill=CRT_GRID)

def draw_crt_line(canvas, data, max_value, line_color, width=2):
    w, h = canvas.winfo_width(), canvas.winfo_height()
    if len(data) < 2 or w < 10 or h < 10: return
    step = w / MAX_POINTS
    pts = [(i * step, h - (val / max(1e-6, max_value)) * h) for i, val in enumerate(data)]
    for i in range(len(pts)-1):
        canvas.create_line(pts[i], pts[i+1], fill=line_color, width=width)

def draw_dual_io(canvas, read_hist, write_hist):
    canvas.delete("all")
    draw_crt_grid(canvas)
    max_io = max(read_hist + write_hist + [1])
    draw_crt_line(canvas, read_hist, max_io, CRT_GREEN)
    draw_crt_line(canvas, write_hist, max_io, "white")

def draw_metric(canvas, series, max_value, color=CRT_GREEN):
    canvas.delete("all")
    draw_crt_grid(canvas)
    draw_crt_line(canvas, series, max_value, color)

# ---- Build metric frame ----
def build_metric_frame(parent, title, maxval=100, graph_height=GRAPH_HEIGHT):
    f = tb.Labelframe(parent, text=title, bootstyle="white")
    lbl = tb.Label(f, text=f"{title}: ...", anchor="w", font=FONT_TITLE, foreground=CRT_GREEN)
    lbl.pack(fill=X, padx=4, pady=(4,2))

    style_name = f"{title}.Horizontal.TProgressbar"
    style.configure(style_name, troughcolor="black", background=CRT_GREEN, thickness=PROGRESS_THICKNESS)
    bar = tb.Progressbar(f, bootstyle="success", maximum=maxval, style=style_name)
    bar._style_name = style_name
    bar.pack(fill=X, padx=4, pady=(0,4))

    cvs = tb.Canvas(f, height=graph_height, background="black", highlightthickness=0)
    cvs.pack(fill=BOTH, expand=True, padx=4, pady=4)
    return f, lbl, bar, cvs

# ==== Layout ====
metric_list = [
    {"name": "CPU", "maxval": 100, "row": 0, "col": 0},
    {"name": "RAM", "maxval": 100, "row": 0, "col": 1},
    {"name": "GPU", "maxval": 100, "row": 1, "col": 0},
    {"name": "Disk I/O", "maxval": DISK_IO_MAX_MBPS, "row": 1, "col": 1, "io": True},
    {"name": "Sys Info & Time", "row": 2, "col": 0, "colspan": 2, "sysinfo": True}
]

widgets = {}

for metric in metric_list:
    name = metric["name"]
    row, col = metric["row"], metric["col"]
    colspan = metric.get("colspan", 1)

    if metric.get("io", False):
        f = tb.Labelframe(root, text=name, bootstyle="white")
        f.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=4, pady=4)

        io_read_lbl = tb.Label(f, text="READ: ...", anchor="w", font=("Courier", 8, "bold"), foreground=CRT_GREEN)
        io_read_lbl.pack(fill=X, padx=4, pady=(2,0))
        io_read_bar_style = f"IORead.Horizontal.TProgressbar"
        style.configure(io_read_bar_style, troughcolor="black", background=CRT_GREEN, thickness=PROGRESS_THICKNESS)
        io_read_bar = tb.Progressbar(f, bootstyle="success", maximum=DISK_IO_MAX_MBPS, style=io_read_bar_style)
        io_read_bar._style_name = io_read_bar_style
        io_read_bar.pack(fill=X, padx=4, pady=(0,2))

        io_write_lbl = tb.Label(f, text="WRITE: ...", anchor="w", font=("Courier", 8, "bold"), foreground="white")
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
        f = tb.Labelframe(root, text="System Info & Time", bootstyle="white")
        f.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=4, pady=4)

        # Time / Uptime large
        time_lbl = tb.Label(f, text="Time: ...", anchor="w", font=("Courier", 15, "bold"), foreground=CRT_GREEN)
        time_lbl.pack(fill=X, pady=(10,2))
        uptime_lbl = tb.Label(f, text="Uptime: ...", anchor="w", font=("Courier", 15, "bold"), foreground=CRT_GREEN)
        uptime_lbl.pack(fill=X, pady=(2,10))

        # System info smaller
        info_labels = {}
        for key in ["CPU Model", "Cores", "Threads", "GPU"]:
            lbl = tb.Label(f, text=f"{key}: ...", anchor="w", font=("Courier", 10, "bold"), foreground=CRT_GREEN)
            lbl.pack(fill=X, padx=4, pady=1)
            info_labels[key] = lbl
        widgets[name] = (time_lbl, uptime_lbl, info_labels)

    else:
        f, lbl, bar, cvs = build_metric_frame(root, name)
        f.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        widgets[name] = (lbl, bar, cvs, metric["maxval"])

# ==== Update function ====
def update_stats():
    # CPU / RAM / GPU
    cpu = core.get_cpu_usage()
    ram_percent = core.get_ram_usage()
    gpu = core.get_gpu_usage()
    usage_values = {"CPU": cpu, "RAM": ram_percent, "GPU": gpu}
    max_metric = max([v for v in usage_values.values() if v is not None] + [0])

    for key, val in usage_values.items():
        if val is None: continue
        history[key].append(val)
        if len(history[key]) > MAX_POINTS: history[key].pop(0)
        lbl, bar, cvs, maxv = widgets[key]

        lbl_color = get_usage_color(val) if val == max_metric else CRT_GREEN
        lbl.config(foreground=lbl_color, text=f"{key} Usage: {val:.1f}%")
        style.configure(bar._style_name, background=lbl_color)
        bar["value"] = val
        draw_metric(cvs, history[key], maxv, color=lbl_color)

        # RAM inline used/free
        if key == "RAM":
            ram_info = core.get_ram_info()
            lbl.config(text=f"RAM Utilized: {ram_info['used']} GB Used | {ram_info['available']} GB Left | ({val:.1f}%)")

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
        draw_dual_io(io_canvas, history["DISK_read"], history["DISK_write"])

    # System Info & Time
    time_lbl, uptime_lbl, info_labels = widgets["Sys Info & Time"]
    time_lbl.config(text=f"Time: {core.get_local_time()}")
    uptime_lbl.config(text=f"Uptime: {core.get_uptime()}")

    cpu_info = core.get_cpu_info()
    gpu_info = core.get_gpu_info()
    info_labels["CPU Model"].config(text=f"CPU Model: {cpu_info['model']}")
    info_labels["Cores"].config(text=f"Cores: {cpu_info['physical_cores']}")
    info_labels["Threads"].config(text=f"Threads: {cpu_info['logical_cores']}")
    info_labels["GPU"].config(text=f"GPU: {gpu_info}")

    root.after(REFRESH_MS, update_stats)

update_stats()
root.mainloop()
