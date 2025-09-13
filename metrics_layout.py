# metrics_layout.py
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from constants import *
from widgets import build_metric_frame, center_overlay_label

# ==== Build metrics ====
def build_metrics(root, style):
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
            # Notebook widget
            f = tb.Labelframe(root, text=name, bootstyle=FONT_TAB_TITLE_COLOR)
            f.grid(row=row, column=col, columnspan=colspan, rowspan=rowspan,
                    sticky="nsew", padx=4, pady=4)

            nb = tb.Notebook(f, bootstyle="dark")
            nb.pack(fill=BOTH, expand=True, padx=4, pady=4)

            # --- Tab 1: System Info (basic hardware details) ---
            f_sys = tb.Frame(nb)
            nb.add(f_sys, text="System Info")

            info_labels = {}
            for key in ["CPU Model", "Cores", "Uptime", "GPU", "DISK"]:
                lbl = tb.Label(f_sys, text=f"{key}: ...", anchor="w",
                            font=FONT_INFOTXT, foreground=CRT_GREEN)
                lbl.pack(fill=X, padx=4, pady=1)
                info_labels[key] = lbl

            # --- Tab 2: CPU Stats (load, uptime, top processes) ---
            f_cpu = tb.Frame(nb)
            nb.add(f_cpu, text="CPU Stats")

            cpu_labels = {}

            # One line: CPU usage + uptime
            cpu_info_lbl = tb.Label(
                f_cpu,
                text="CPU: ...  Uptime: ...",
                anchor="w",
                font=FONT_INFOTXT,
                foreground=CRT_GREEN
            )
            cpu_info_lbl.pack(fill=X, padx=4, pady=2)
            cpu_labels["Info"] = cpu_info_lbl

            # Top processes (header + 3 rows)
            cpu_top_lbl = tb.Label(
                f_cpu,
                text="PID    USER       VIRT    RES   CPU%  MEM%  NAME",
                anchor="w",
                font=("Consolas", 9),  # monospace for alignment
                foreground=CRT_GREEN,
                justify="left"
            )
            cpu_top_lbl.pack(fill=X, padx=4, pady=4)
            cpu_labels["Top Processes"] = cpu_top_lbl

            # Register labels into widgets dict
            widgets["CPU Stats"] = cpu_labels

            # --- Tab 3: GPU Stats ---
            f_gpu = tb.Frame(nb)
            nb.add(f_gpu, text="GPU Stats")
            gpu_lbl = tb.Label(f_gpu, text="GPU Usage: ...", anchor="w",
                            font=FONT_INFOTXT, foreground=CRT_GREEN)
            gpu_lbl.pack(fill=X, padx=4, pady=2)

            # --- Tab 4: Network Stats ---
            f_net = tb.Frame(nb)
            nb.add(f_net, text="Network Stats")
            net_in_lbl = tb.Label(f_net, text="Net IN: ... MB/s", anchor="w",
                                font=FONT_INFOTXT, foreground=CRT_GREEN)
            net_in_lbl.pack(fill=X, padx=4, pady=1)
            net_out_lbl = tb.Label(f_net, text="Net OUT: ... MB/s", anchor="w",
                                font=FONT_INFOTXT, foreground=CRT_GREEN)
            net_out_lbl.pack(fill=X, padx=4, pady=1)
            latency_lbl = tb.Label(f_net, text="Latency: ... ms", anchor="w",
                                font=FONT_INFOTXT, foreground=CRT_GREEN)
            latency_lbl.pack(fill=X, padx=4, pady=1)

            # Store widget references
            widgets["Sys Info"] = info_labels
            widgets["CPU Stats"] = cpu_labels   
            info_labels["GPU Usage"] = gpu_lbl
            info_labels["Net IN"] = net_in_lbl
            info_labels["Net OUT"] = net_out_lbl
            info_labels["Latency"] = latency_lbl

            widgets[name] = info_labels



        elif metric.get("timewidget", False):
            # Dedicated Time & Uptime widget
            f = tb.Labelframe(root, text=name, bootstyle=FONT_TAB_TITLE_COLOR)
            f.grid(row=row, column=col, columnspan=colspan, rowspan=rowspan,
                sticky="nsew", padx=4, pady=4)

            time_lbl = tb.Label(f, text="Time: ...", anchor="w", font=FONT_SYSTIME, foreground=CRT_GREEN)
            time_lbl.pack(fill=X, pady=(1,1))

            date_lbl = tb.Label(f, text="Date: ...", anchor="w", font=("Consolas", 15, "bold"), foreground=CRT_GREEN)
            date_lbl.pack(fill=X, pady=(2,1))

            # uptime_lbl = tb.Label(f, text="Uptime: ...", anchor="w", font=("Consolas", 12, "bold"), foreground=CRT_GREEN)
            # uptime_lbl.pack(fill=X, pady=(2,1))
            # Store them
            widgets["Time & Uptime"] = (date_lbl, time_lbl)


        else:
            f, lbl, bar, cvs, overlay_lbl = build_metric_frame(root, name, style=style)
            f.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            root.rowconfigure(row, weight=1)
            root.columnconfigure(col, weight=1)
            widgets[name] = (lbl, bar, cvs, metric["maxval"], overlay_lbl)
            if name == "RAM" and overlay_lbl:
                bar.bind("<Configure>", lambda e, b=bar, l=overlay_lbl: center_overlay_label(b, l))

    return widgets
