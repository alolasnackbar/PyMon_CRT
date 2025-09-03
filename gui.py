import ttkbootstrap as tb
from ttkbootstrap.constants import *
import monitor_core as core

# --- History for graphs ---
MAX_POINTS = 60
cpu_history, ram_history, gpu_history = [], [], []
disk_usage_history, disk_read_history, disk_write_history = [], [], []

# ==== GUI Setup ====
root = tb.Window(themename="darkly")
root.title("System Monitor (Task Manager Style)")
root.geometry("950x600")

# --- Custom progress bar style ---
style = tb.Style()
style.configure("Medium.Horizontal.TProgressbar", thickness=20)

# ==== Graph drawing function with fill ====
def draw_filled_graph(canvas, data, max_value, color, overlay_data=None, overlay_color=None):
    canvas.delete("all")
    if len(data) < 2:
        return
    w, h = canvas.winfo_width(), canvas.winfo_height()
    step = w / MAX_POINTS

    # --- Primary filled graph ---
    points = []
    for i, val in enumerate(data):
        x = i * step
        y = h - (val / max_value) * h
        points.append((x, y))

    # Build polygon: add bottom right and bottom left to close the shape
    polygon_points = [(points[0][0], h)] + points + [(points[-1][0], h)]
    canvas.create_polygon(polygon_points, fill=color, outline=color)

    # --- Overlay if exists ---
    if overlay_data and overlay_color:
        overlay_points = []
        for i, val in enumerate(overlay_data):
            x = i * step
            y = h - (val / max_value) * h
            overlay_points.append((x, y))
        overlay_polygon = [(overlay_points[0][0], h)] + overlay_points + [(overlay_points[-1][0], h)]
        canvas.create_polygon(overlay_polygon, fill=overlay_color, outline=overlay_color)



# ==== Update stats function ====
def update_stats():
    # Fetch system stats
    cpu = core.get_cpu_usage()
    ram = core.get_ram_usage()
    gpu = core.get_gpu_usage()
    disk = core.get_disk_usage()
    read_mb, write_mb = core.get_disk_io(interval=0.5)

    # --- CPU ---
    if cpu is not None:
        cpu_bar["value"] = cpu
        cpu_label.config(text=f"CPU Usage: {cpu:.1f}%")
        cpu_history.append(cpu)
        if len(cpu_history) > MAX_POINTS:
            cpu_history.pop(0)
    else:
        cpu_label.config(text="CPU Usage: N/A")

    # --- RAM ---
    if ram is not None:
        ram_bar["value"] = ram
        ram_label.config(text=f"RAM Usage: {ram:.1f}%")
        ram_history.append(ram)
        if len(ram_history) > MAX_POINTS:
            ram_history.pop(0)
    else:
        ram_label.config(text="RAM Usage: N/A")

    # --- GPU ---
    if gpu is not None:
        gpu_bar["value"] = gpu
        gpu_label.config(text=f"GPU Usage: {gpu:.1f}%")
        gpu_history.append(gpu)
        if len(gpu_history) > MAX_POINTS:
            gpu_history.pop(0)
    else:
        gpu_bar["value"] = 0
        gpu_label.config(text="GPU Usage: N/A")

    # --- Disk ---
    if disk is not None:
        disk_bar["value"] = disk
        disk_label.config(text=f"Disk Usage: {disk:.1f}%")
        disk_usage_history.append(disk)
        if len(disk_usage_history) > MAX_POINTS:
            disk_usage_history.pop(0)
    else:
        disk_label.config(text="Disk Usage: N/A")

    # --- Disk I/O ---
    if read_mb is not None and write_mb is not None:
        io_label.config(text=f"Disk I/O: {read_mb:.2f} MB/s read, {write_mb:.2f} MB/s write")
        disk_read_history.append(read_mb)
        disk_write_history.append(write_mb)
        if len(disk_read_history) > MAX_POINTS:
            disk_read_history.pop(0)
            disk_write_history.pop(0)
    else:
        io_label.config(text="Disk I/O: N/A")

    # --- Draw filled graphs ---
    draw_filled_graph(cpu_canvas, cpu_history, 100, "green")
    draw_filled_graph(ram_canvas, ram_history, 100, "cyan")
    draw_filled_graph(gpu_canvas, gpu_history, 100, "red")
    max_io = max(disk_read_history + disk_write_history + [1])
    draw_filled_graph(disk_canvas, disk_read_history, max_io, "orange",
                      overlay_data=disk_write_history, overlay_color="magenta")

    root.after(1000, update_stats)


# ==== Frames & Widgets ====

# CPU Frame
cpu_frame = tb.Labelframe(root, text="CPU", bootstyle="success")
cpu_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
cpu_label = tb.Label(cpu_frame, text="CPU Usage: ...", anchor="w", font=("Segoe UI", 10, "bold"))
cpu_label.pack(fill=X, padx=5, pady=2)
cpu_bar = tb.Progressbar(cpu_frame, bootstyle="success-striped", maximum=100,
                         style="Medium.Horizontal.TProgressbar")
cpu_bar.pack(fill=X, padx=5, pady=5)
cpu_canvas = tb.Canvas(cpu_frame, height=80)
cpu_canvas.pack(fill=BOTH, expand=True, padx=5, pady=5)

# RAM Frame
ram_frame = tb.Labelframe(root, text="RAM", bootstyle="info")
ram_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
ram_label = tb.Label(ram_frame, text="RAM Usage: ...", anchor="w", font=("Segoe UI", 10, "bold"))
ram_label.pack(fill=X, padx=5, pady=2)
ram_bar = tb.Progressbar(ram_frame, bootstyle="info-striped", maximum=100,
                         style="Medium.Horizontal.TProgressbar")
ram_bar.pack(fill=X, padx=5, pady=5)
ram_canvas = tb.Canvas(ram_frame, height=80)
ram_canvas.pack(fill=BOTH, expand=True, padx=5, pady=5)

# Disk Frame
disk_frame = tb.Labelframe(root, text="DISK", bootstyle="warning")
disk_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
disk_label = tb.Label(disk_frame, text="Disk Usage: ...", anchor="w", font=("Segoe UI", 10, "bold"))
disk_label.pack(fill=X, padx=5, pady=2)
disk_bar = tb.Progressbar(disk_frame, bootstyle="warning-striped", maximum=100,
                          style="Medium.Horizontal.TProgressbar")
disk_bar.pack(fill=X, padx=5, pady=5)
io_label = tb.Label(disk_frame, text="Disk I/O: ...", anchor="w", font=("Segoe UI", 9))
io_label.pack(fill=X, padx=5, pady=2)
disk_canvas = tb.Canvas(disk_frame, height=80)
disk_canvas.pack(fill=BOTH, expand=True, padx=5, pady=5)

# GPU Frame
gpu_frame = tb.Labelframe(root, text="GPU", bootstyle="danger")
gpu_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
gpu_label = tb.Label(gpu_frame, text="GPU Usage: ...", anchor="w", font=("Segoe UI", 10, "bold"))
gpu_label.pack(fill=X, padx=5, pady=2)
gpu_bar = tb.Progressbar(gpu_frame, bootstyle="danger-striped", maximum=100,
                         style="Medium.Horizontal.TProgressbar")
gpu_bar.pack(fill=X, padx=5, pady=5)
gpu_canvas = tb.Canvas(gpu_frame, height=80)
gpu_canvas.pack(fill=BOTH, expand=True, padx=5, pady=5)

# Grid expansion
root.columnconfigure((0,1), weight=1)
root.rowconfigure((0,1), weight=1)
cpu_frame.columnconfigure(0, weight=1); cpu_frame.rowconfigure(2, weight=1)
ram_frame.columnconfigure(0, weight=1); ram_frame.rowconfigure(2, weight=1)
disk_frame.columnconfigure(0, weight=1); disk_frame.rowconfigure(3, weight=1)
gpu_frame.columnconfigure(0, weight=1); gpu_frame.rowconfigure(2, weight=1)

# Start monitoring
update_stats()
root.mainloop()
