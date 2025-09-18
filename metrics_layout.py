# metrics_layout.py
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from constants import *
from widgets import build_metric_frame #center_overlay_label

# ==== Build metrics ====
def build_metrics(root, style):
    """
    Creates and places all the main frames and widgets into the root window using a 
    data-driven approach with .grid() for a responsive layout.
    """
    widgets = {}

    metric_list = [
        {"name": "CPU", "maxval": 100, "row": 0, "col": 0},
        {"name": "GPU", "maxval": 100, "row": 1, "col": 0},
        {"name": "RAM", "maxval": 100, "row": 2, "col": 0},
        {"name": "Disk I/O", "maxval": DISK_IO_MAX_MBPS, "row": 0, "col": 1, "io": True},
        {"name": "Sys Info", "row": 1, "col": 1, "rowspan": 1, "sysinfo": True},
        {"name": "Time & Uptime", "row": 2, "col": 1, "timewidget": True}
    ]

    for metric in metric_list:
        name = metric["name"]
        row, col = metric["row"], metric["col"]
        colspan = metric.get("colspan", 1)
        rowspan = metric.get("rowspan", 1)

        if metric.get("io", False):
            f = tb.Labelframe(root, text=name, bootstyle=FONT_TAB_TITLE_COLOR)
            f.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=4, pady=4)
            f.columnconfigure(0, weight=1)
            f.rowconfigure(4, weight=1) # Make canvas row resizable

            io_read_lbl = tb.Label(f, text="READ: ...", anchor="w", font=FONT_TITLE, foreground=CRT_GREEN)
            io_read_lbl.grid(row=0, column=0, sticky="ew", padx=4, pady=(2,0))
            
            io_read_bar_style = "IORead.Horizontal.TProgressbar"
            style.configure(io_read_bar_style, troughcolor="black", background=CRT_GREEN, thickness=PROGRESS_THICKNESS)
            io_read_bar = tb.Progressbar(f, bootstyle="success", maximum=DISK_IO_MAX_MBPS, style=io_read_bar_style)
            io_read_bar._style_name = io_read_bar_style
            io_read_bar.grid(row=1, column=0, sticky="ew", padx=4, pady=(0,2))

            io_write_lbl = tb.Label(f, text="WRITE: ...", anchor="w", font=FONT_TITLE, foreground="white")
            io_write_lbl.grid(row=2, column=0, sticky="ew", padx=4, pady=(2,0))
            
            io_write_bar_style = "IOWrite.Horizontal.TProgressbar"
            style.configure(io_write_bar_style, troughcolor="black", background="white", thickness=PROGRESS_THICKNESS)
            io_write_bar = tb.Progressbar(f, bootstyle="success", maximum=DISK_IO_MAX_MBPS, style=io_write_bar_style)
            io_write_bar._style_name = io_write_bar_style
            io_write_bar.grid(row=3, column=0, sticky="ew", padx=4, pady=(0,2))

            io_canvas = tb.Canvas(f, height=GRAPH_HEIGHT, background="black", highlightthickness=0)
            io_canvas.grid(row=4, column=0, sticky="nsew", padx=4, pady=4)
            widgets[name] = (io_read_lbl, io_write_lbl, io_read_bar, io_write_bar, io_canvas)
    
        elif metric.get("sysinfo", False):
            f = tb.Labelframe(root, text=name, bootstyle=FONT_TAB_TITLE_COLOR)
            f.grid(row=row, column=col, rowspan=rowspan, columnspan=colspan, sticky="nsew", padx=4, pady=4)
            f.rowconfigure(0, weight=1)
            f.columnconfigure(0, weight=1)

            nb = tb.Notebook(f, bootstyle="dark")
            nb.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

            # --- Tab 1: System Info ---
            f_sys = tb.Frame(nb)
            nb.add(f_sys, text="System Info")
            f_sys.columnconfigure(0, weight=1)
            info_labels = {}
            sys_info_keys = ["CPU Model", "Cores", "Uptime", "GPU", "DISK"]
            for i, key in enumerate(sys_info_keys):
                lbl = tb.Label(f_sys, text=f"{key}: ...", anchor="w", font=FONT_INFOTXT, foreground=CRT_GREEN)
                lbl.grid(row=i, column=0, sticky="ew", padx=4, pady=1)
                info_labels[key] = lbl

            # --- Tab 2: CPU Stats ---
            f_cpu = tb.Frame(nb)
            nb.add(f_cpu, text="Processing Stats")
            f_cpu.columnconfigure(0, weight=1)
            f_cpu.rowconfigure(1, weight=1) # Let process list expand
            cpu_labels = {}
            cpu_info_lbl = tb.Label(f_cpu, text="CPU: ... Uptime: ...", anchor="w", font=FONT_INFOTXT, foreground=CRT_GREEN)
            cpu_info_lbl.grid(row=0, column=0, sticky="ew", padx=4, pady=2)
            cpu_labels["Info"] = cpu_info_lbl
            cpu_top_lbl = tb.Label(f_cpu, text="PID USER VIRT RES CPU% MEM% NAME", anchor="w", font=("Consolas", 9), foreground=CRT_GREEN, justify="left")
            cpu_top_lbl.grid(row=1, column=0, sticky="new", padx=4, pady=4)
            cpu_labels["Top Processes"] = cpu_top_lbl

            # --- Tab 3: Network Stats ---
            f_net = tb.Frame(nb)
            nb.add(f_net, text="Network Stats")
            f_net.columnconfigure(0, weight=1)
            net_in_lbl = tb.Label(f_net, text="Net Download: ... MB/s", anchor="w", font=FONT_NETTXT, foreground=CRT_GREEN)
            net_in_lbl.grid(row=0, column=0, sticky="ew", padx=4, pady=1)
            net_out_lbl = tb.Label(f_net, text="Net Upload: ... MB/s", anchor="w", font=FONT_NETTXT, foreground=CRT_GREEN)
            net_out_lbl.grid(row=1, column=0, sticky="ew", padx=4, pady=1)
            latency_lbl = tb.Label(f_net, text="Latency: ... ms", anchor="w", font=FONT_NETTXT, foreground=CRT_GREEN)
            latency_lbl.grid(row=2, column=0, sticky="ew", padx=4, pady=1)

            # --- Tab 4: Temperature Stats ---
            f_temp = tb.Frame(nb)
            nb.add(f_temp, text="Temperature Stats")
            f_temp.columnconfigure(0, weight=1)
            temp_labels = {}
            cpu_temp_lbl = tb.Label(f_temp, text="CPU Temperature: ...", anchor="w", font=FONT_INFOTXT, foreground=CRT_GREEN)
            cpu_temp_lbl.grid(row=0, column=0, sticky="ew", padx=4, pady=1)
            temp_labels["CPU Temp"] = cpu_temp_lbl
            gpu_temp_lbl = tb.Label(f_temp, text="GPU Temperature: ...", anchor="w", font=FONT_INFOTXT, foreground=CRT_GREEN)
            gpu_temp_lbl.grid(row=1, column=0, sticky="ew", padx=4, pady=1)
            temp_labels["GPU Temp"] = gpu_temp_lbl

            # --- Store widget references ---
            widgets["Sys Info"] = info_labels
            widgets["CPU Stats"] = cpu_labels
            widgets["Temp Stats"] = temp_labels
            info_labels["Net IN"] = net_in_lbl
            info_labels["Net OUT"] = net_out_lbl
            info_labels["Latency"] = latency_lbl
            widgets[name] = info_labels # Legacy compatibility

        elif metric.get("timewidget", False):
            f = tb.Labelframe(root, text=name, bootstyle=FONT_TAB_TITLE_COLOR)
            f.grid(row=row, column=col, rowspan=rowspan, columnspan=colspan, sticky="nsew", padx=4, pady=4)
            f.columnconfigure(0, weight=1)
            f.rowconfigure(0, weight=1)
            f.rowconfigure(1, weight=1)
            
            time_lbl = tb.Label(f, text="Time: ...", anchor="w", font=FONT_SYSTIME, foreground=CRT_GREEN)
            time_lbl.grid(row=0, column=0, sticky="nsew", padx=5)
            date_lbl = tb.Label(f, text="Date: ...", anchor="w", font=("Consolas", 15, "bold"), foreground=CRT_GREEN)
            date_lbl.grid(row=1, column=0, sticky="nsew", padx=5)
            widgets["Time & Uptime"] = (date_lbl, time_lbl)

        else:
            f, lbl, bar, cvs, overlay_lbl = build_metric_frame(root, name, style=style, maxval=metric["maxval"])
            f.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            root.rowconfigure(row, weight=1)
            root.columnconfigure(col, weight=1)
            widgets[name] = (lbl, bar, cvs, metric["maxval"], overlay_lbl)

    return widgets