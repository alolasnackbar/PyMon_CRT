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

            # Store notebook reference for auto-cycling
            widgets["notebook"] = nb

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
            f_temp.columnconfigure((0, 1), weight=1) # Configure columns to center meters

            temp_widgets = {} # Use this dict directly

            # --- CPU Temperature Meter ---
            cpu_meter = tb.Meter(
                master=f_temp,
                metersize=120,
                padding=5,
                amountused=0,
                metertype='semi',
                stripethickness=3,
                interactive=False,
                bootstyle='success',
                textleft='CPU',
                textright="°C",
                subtextfont="consolas",
            )
            cpu_meter.grid(row=0, column=0, padx=5, pady=5)
            temp_widgets["CPU Meter"] = cpu_meter # Use the correct key

            # --- GPU Temperature Meter ---
            gpu_meter = tb.Meter(
                master=f_temp,
                metersize=120,
                padding=5,
                amountused=0,
                metertype='semi',
                stripethickness=3,
                interactive=False,
                bootstyle='success',
                textleft='GPU',
                textright="°C",
                subtextfont="consolas",
            )
            gpu_meter.grid(row=0, column=1, padx=5, pady=5)
            temp_widgets["GPU Meter"] = gpu_meter # Use the correct key

            # --- Tab 5: Configuration ---
            f_config = tb.Frame(nb)
            nb.add(f_config, text="Config")
            f_config.columnconfigure((0, 1), weight=1)
            f_config.rowconfigure(0, weight=1)
            
            config_widgets = {}
            
            # Create scrollable frame for config content
            config_canvas = tb.Canvas(f_config, height=100)  # Fixed height for compact display
            config_scrollbar = tb.Scrollbar(f_config, orient="vertical", command=config_canvas.yview)
            scrollable_frame = tb.Frame(config_canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: config_canvas.configure(scrollregion=config_canvas.bbox("all"))
            )
            
            config_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            config_canvas.configure(yscrollcommand=config_scrollbar.set)
            
            config_canvas.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=2, pady=2)
            config_scrollbar.grid(row=0, column=2, sticky="ns", pady=2)
            
            # Make scrollable_frame use full width
            scrollable_frame.columnconfigure(0, weight=1)
            scrollable_frame.columnconfigure(1, weight=1)
            
            # Compact two-column layout
            col1 = tb.Frame(scrollable_frame)
            col1.grid(row=0, column=0, sticky="nsew", padx=2)
            col2 = tb.Frame(scrollable_frame)
            col2.grid(row=0, column=1, sticky="nsew", padx=2)
            
            # Column 1: Processing & Auto-cycling
            # Process count (ultra compact)
            process_frame = tb.Labelframe(col1, text="Processing", bootstyle="info")
            process_frame.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
            process_frame.columnconfigure(1, weight=1)
            
            tb.Label(process_frame, text="Count:", font=("Consolas", 8), foreground=CRT_GREEN).grid(row=0, column=0, padx=2, sticky="w")
            process_slider = tb.Scale(process_frame, from_=0, to=5, orient="horizontal", bootstyle="success", length=140)
            process_slider.set(5)
            process_slider.grid(row=0, column=1, sticky="ew", padx=2)
            process_count_lbl = tb.Label(process_frame, text="3", font=("Consolas", 8, "bold"), foreground=CRT_GREEN, width=2)
            process_count_lbl.grid(row=0, column=2, padx=2)
            
            def update_process_count(val):
                count = int(float(val))
                process_count_lbl.config(text=str(count))
                config_widgets["process_count"] = count
            
            process_slider.configure(command=update_process_count)
            config_widgets["process_count"] = 5
            config_widgets["process_slider"] = process_slider
            
            # Auto-cycling (compact)
            cycle_frame = tb.Labelframe(col1, text="Auto Cycle", bootstyle="success")
            cycle_frame.grid(row=1, column=0, sticky="ew", padx=1, pady=1)
            cycle_frame.columnconfigure(1, weight=1)
            
            cycle_enabled_var = tb.BooleanVar(value=False)
            cycle_check = tb.Checkbutton(cycle_frame, text="ON", variable=cycle_enabled_var, 
                                         bootstyle="success-round-toggle")
            cycle_check.grid(row=0, column=0, padx=2, sticky="w")
            
            tb.Label(cycle_frame, text="Delay:", font=("Consolas", 8), foreground=CRT_GREEN).grid(row=1, column=0, padx=2, sticky="w")
            cycle_slider = tb.Scale(cycle_frame, from_=2, to=30, orient="horizontal", bootstyle="success", length=140)
            cycle_slider.set(5)
            cycle_slider.grid(row=1, column=1, sticky="ew", padx=2)
            cycle_delay_lbl = tb.Label(cycle_frame, text="5s", font=("Consolas", 8, "bold"), foreground=CRT_GREEN, width=3)
            cycle_delay_lbl.grid(row=1, column=2, padx=2)
            
            def update_cycle_delay(val):
                delay = int(float(val))
                cycle_delay_lbl.config(text=f"{delay}s")
                config_widgets["cycle_delay"] = delay
            
            cycle_slider.configure(command=update_cycle_delay)
            config_widgets["cycle_enabled"] = cycle_enabled_var
            config_widgets["cycle_delay"] = 5
            
            # Column 2: Smart Focus & Accessibility
            # Smart focus (ultra compact)
            focus_frame = tb.Labelframe(col2, text="Smart Focus", bootstyle="warning")
            focus_frame.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
            focus_frame.columnconfigure(1, weight=1)
            
            focus_enabled_var = tb.BooleanVar(value=True)
            focus_check = tb.Checkbutton(focus_frame, text="ON", variable=focus_enabled_var, 
                                         bootstyle="warning-round-toggle")
            focus_check.grid(row=0, column=0, columnspan=3, padx=2, sticky="w")
            
            # Compact threshold settings - single row each
            threshold_data = [
                ("CPU%:", 50, 95, 80, "cpu_threshold", "warning", "%"),
                ("Temp°C:", 60, 95, 75, "temp_threshold", "danger", "°C"),
                ("Ping ms:", 100, 1000, 200, "latency_threshold", "info", "ms")
            ]
            
            for i, (label, min_val, max_val, default, key, style, suffix) in enumerate(threshold_data, 1):
                tb.Label(focus_frame, text=label, font=("Consolas", 8), foreground=CRT_GREEN).grid(row=i, column=0, padx=2, sticky="w")
                slider = tb.Scale(focus_frame, from_=min_val, to=max_val, orient="horizontal", bootstyle=style, length=140)
                slider.set(default)
                slider.grid(row=i, column=1, sticky="ew", padx=1)
                value_lbl = tb.Label(focus_frame, text=f"{default}{suffix}", font=("Consolas", 8, "bold"), foreground=CRT_GREEN, width=4)
                value_lbl.grid(row=i, column=2, padx=2)
                
                def make_update_func(key, lbl, suffix=""):
                    def update_func(val):
                        value = int(float(val))
                        lbl.config(text=f"{value}{suffix}")
                        config_widgets[key] = value
                    return update_func
                
                slider.configure(command=make_update_func(key, value_lbl, suffix))
                config_widgets[key] = default
            
            config_widgets["focus_enabled"] = focus_enabled_var
            
            # Accessibility & Status (bottom row, spans both columns)
            bottom_frame = tb.Frame(scrollable_frame)
            bottom_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)
            bottom_frame.columnconfigure((0, 1), weight=1)
            
            # Colorblind mode (compact)
            colorblind_var = tb.BooleanVar(value=False)
            colorblind_check = tb.Checkbutton(bottom_frame, text="Color Blind Mode", 
                                             variable=colorblind_var, bootstyle="info-round-toggle")
            colorblind_check.grid(row=0, column=0, sticky="w", padx=2)
            config_widgets["colorblind_mode"] = colorblind_var
            
            # Compact status
            status_lbl = tb.Label(bottom_frame, text="Ready", 
                                 font=("Consolas", 8), foreground=CRT_GREEN, anchor="e")
            status_lbl.grid(row=0, column=1, sticky="ew", padx=2)
            config_widgets["status_label"] = status_lbl
            
            # Bind mouse wheel to canvas for scrolling
            def _on_mousewheel(event):
                config_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            config_canvas.bind_all("<MouseWheel>", _on_mousewheel)

            # --- Store widget references ---
            widgets["Sys Info"] = info_labels
            widgets["CPU Stats"] = cpu_labels
            widgets["Temp Stats"] = temp_widgets
            widgets["Config"] = config_widgets
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