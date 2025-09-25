import random
import tkinter as tk
from tkinter import ttk
from constants import *
import threading
import time

# Import monitor_core to test actual data detection
try:
    import monitor_core as core
except ImportError:
    core = None

def test_data_sources():
    """Test all data sources and return their status."""
    if not core:
        return {}
    
    status = {}
    
    # Test CPU data
    try:
        cpu_usage = core.get_cpu_usage() if hasattr(core, 'get_cpu_usage') else None
        cpu_info = core.get_cpu_info() if hasattr(core, 'get_cpu_info') else None
        cpu_temp = core.get_cpu_temp() if hasattr(core, 'get_cpu_temp') else None
        
        if cpu_usage is not None and cpu_usage > 0:
            status['CPU'] = 'detected'
        elif cpu_usage is not None:
            status['CPU'] = 'missing'  # Function exists but returns null/0
        else:
            status['CPU'] = 'default'
            
        if cpu_temp is not None and cpu_temp > 0:
            status['CPU_temp'] = 'detected'
        else:
            status['CPU_temp'] = 'missing'
    except Exception:
        status['CPU'] = 'default'
        status['CPU_temp'] = 'default'
    
    # Test RAM data
    try:
        ram_info = core.get_ram_info() if hasattr(core, 'get_ram_info') else None
        if ram_info and isinstance(ram_info, dict) and ram_info.get('used', 0) > 0:
            status['RAM'] = 'detected'
        else:
            status['RAM'] = 'missing'
    except Exception:
        status['RAM'] = 'default'
    
    # Test GPU data
    try:
        gpu_usage = core.get_gpu_usage() if hasattr(core, 'get_gpu_usage') else None
        gpu_temp = core.get_gpu_temp() if hasattr(core, 'get_gpu_temp') else None
        gpu_info = core.get_gpu_info() if hasattr(core, 'get_gpu_info') else None
        
        if gpu_usage is not None and gpu_usage > 0:
            status['GPU'] = 'detected'
        elif gpu_info and gpu_info != "N/A":
            status['GPU'] = 'missing'  # GPU detected but no usage data
        else:
            status['GPU'] = 'default'
            
        if gpu_temp is not None and gpu_temp > 0:
            status['GPU_temp'] = 'detected'
        else:
            status['GPU_temp'] = 'missing'
    except Exception:
        status['GPU'] = 'default'
        status['GPU_temp'] = 'default'
    
    # Test Disk I/O data
    try:
        disk_io = core.get_disk_io() if hasattr(core, 'get_disk_io') else None
        if disk_io and isinstance(disk_io, dict):
            status['Disk I/O'] = 'detected'
        else:
            status['Disk I/O'] = 'missing'
    except Exception:
        status['Disk I/O'] = 'default'
    
    # Test Network data
    try:
        net_data = core.net_usage_latency() if hasattr(core, 'net_usage_latency') else None
        if net_data and len(net_data) >= 2:
            status['Network'] = 'detected'
        else:
            status['Network'] = 'missing'
    except Exception:
        status['Network'] = 'default'
    
    # Test System Info components
    try:
        uptime = core.get_uptime() if hasattr(core, 'get_uptime') else None
        load_avg = core.get_load_average() if hasattr(core, 'get_load_average') else None
        if uptime or load_avg:
            status['Sys Info'] = 'detected'
        else:
            status['Sys Info'] = 'missing'
    except Exception:
        status['Sys Info'] = 'default'
    
    return status

def update_widget_status(widgets, widget_key, status, style):
    """Update widget visual status based on detection result."""
    color = STATUS_COLORS.get(status, STATUS_COLORS['default'])
    
    w = widgets.get(widget_key)
    if not w:
        return
    
    # Handle progress bar widgets (CPU, GPU, RAM, Disk I/O)
    if isinstance(w, tuple) and len(w) == 5:
        if widget_key == "Disk I/O":
            _, _, io_read_bar, io_write_bar, _ = w
            style.configure(io_read_bar._style_name, background=color)
            style.configure(io_write_bar._style_name, background=color)
        else:
            _, bar, _, _, _ = w
            style.configure(bar._style_name, background=color)
    
    # Handle dictionary widgets (labels)
    elif isinstance(w, dict):
        for key, widget in w.items():
            try:
                if hasattr(widget, 'config') and hasattr(widget, 'winfo_class'):
                    widget_class = widget.winfo_class()
                    
                    # Skip buttons, checkbuttons, scales, and other interactive widgets
                    if widget_class in ('TButton', 'TCheckbutton', 'TScale', 'Button', 'Checkbutton', 'Scale'):
                        continue
                        
                    # Only apply color to labels and text widgets
                    if widget_class in ('TLabel', 'Label', 'Text', 'Entry'):
                        widget.config(foreground=color)
                        
            except (tk.TclError, AttributeError):
                pass

def cycle_notebook_tabs(widgets, current_cycle, max_cycles, detection_status, style, on_complete):
    """Cycle through notebook tabs showing detection status."""
    if "notebook" not in widgets:
        on_complete()
        return
    
    notebook = widgets["notebook"]
    tab_count = len(notebook.tabs())
    
    if tab_count == 0:
        on_complete()
        return
    
    current_tab = current_cycle % tab_count
    notebook.select(current_tab)
    
    # Update status display for current tab
    tab_text = notebook.tab(current_tab, "text")
    
    # Show detection status in the current tab
    if tab_text in detection_status:
        status = detection_status[tab_text]
        # You could add visual indicators here for the specific tab content
        
    if current_cycle < max_cycles:
        # Continue cycling
        delay = 800 if current_cycle < max_cycles - tab_count else 400  # Faster on final check
        widgets["notebook"].after(delay, lambda: cycle_notebook_tabs(
            widgets, current_cycle + 1, max_cycles, detection_status, style, on_complete
        ))
    else:
        # Finished cycling, proceed to end loading
        on_complete()

def reset_widget_styles(widgets, style):
    """Reset all widget styles to their default GUI colors."""
    for key, w_group in widgets.items():
        if isinstance(w_group, tuple) and len(w_group) == 5:
            try:
                if key == "Disk I/O":
                    _, _, io_read_bar, io_write_bar, _ = w_group
                    # Reset to original IO bar colors
                    style.configure(io_read_bar._style_name, background=CRT_GREEN)
                    style.configure(io_write_bar._style_name, background="white")
                else:
                    _, bar, _, _, _ = w_group
                    # Reset to default progress bar color (will be updated by GUI)
                    style.configure(bar._style_name, background=CRT_GREEN)
            except (tk.TclError, AttributeError):
                pass

        elif isinstance(w_group, dict):
            # Reset label colors to default, but protect interactive widgets
            for key, widget in w_group.items():
                try:
                    if hasattr(widget, 'config') and hasattr(widget, 'winfo_class'):
                        widget_class = widget.winfo_class()
                        
                        # Skip buttons, checkbuttons, scales, and other interactive widgets
                        if widget_class in ('TButton', 'TCheckbutton', 'TScale', 'Button', 'Checkbutton', 'Scale'):
                            continue
                            
                        # Only apply color to labels and text widgets
                        if widget_class in ('TLabel', 'Label', 'Text', 'Entry'):
                            widget.config(foreground=CRT_GREEN)
                            
                except (tk.TclError, AttributeError):
                    pass

def end_loading(widgets, style, on_complete=None):
    """
    Clears initial states from all widgets, resets all colors to normal,
    and calls an optional on_complete function when finished.
    FIXED: Now properly protects interactive widgets like buttons.
    """
    # First reset all colors/styles to normal GUI defaults
    reset_widget_styles(widgets, style)
    
    # Reset notebook to first tab
    if "notebook" in widgets:
        try:
            widgets["notebook"].select(0)
        except (tk.TclError, AttributeError):
            pass
    
    for key, w_group in widgets.items():
        # Handles progress bars stored in tuples (e.g., CPU, RAM)
        if isinstance(w_group, tuple) and len(w_group) == 5:
            try:
                if key == "Disk I/O":
                    _, _, io_read_bar, io_write_bar, _ = w_group
                    io_read_bar["value"] = 0
                    io_write_bar["value"] = 0
                else:
                    _, bar, _, _, _ = w_group
                    bar["value"] = 0
            except (tk.TclError, AttributeError):
                pass

        # Handles widgets stored in dictionaries
        elif isinstance(w_group, dict):
            for widget_key, widget in w_group.items():
                try:
                    if hasattr(widget, 'config') and hasattr(widget, 'winfo_class'):
                        widget_class = widget.winfo_class()
                        
                        # Skip buttons, checkbuttons, scales, and other interactive widgets
                        if widget_class in ('TButton', 'TCheckbutton', 'TScale', 'Button', 'Checkbutton', 'Scale'):
                            continue
                            
                        # Only clear text for labels and text widgets
                        if widget_class in ('TLabel', 'Label', 'Text', 'Entry'):
                            widget.config(text="")
                            
                except (tk.TclError, AttributeError):
                    pass

    # Call the completion callback function if it exists
    if on_complete:
        on_complete()

def startup_loader(root, widgets, style, on_complete=None):
    """
    Enhanced startup loader with value detection and debug visualization.
    Shows detection status with colors and cycles through tabs.
    FIXED: Now properly protects interactive widgets during all phases.
    """
    detection_status = {}
    
    def fill_bar_gradually(bar, max_value=100, duration=800, steps=20, color=CRT_GREEN):
        """Gradually fill a progress bar with specified color."""
        step_delay = duration // steps

        def step(i=0):
            try:
                if i <= steps:
                    val = (i / steps) * max_value
                    bar["value"] = val
                    style.configure(bar._style_name, background=color)
                    root.after(step_delay, step, i + 1)
                else:
                    bar["value"] = max_value
            except (tk.TclError, AttributeError):
                pass
        step()

    def animate_loading_phase():
        """Phase 1: Show loading animation with default red colors."""
        delay = 0
        
        for widget_key in widgets.keys():
            if widget_key == "notebook":  # Skip notebook itself
                continue
                
            def animate_widget(key=widget_key):
                w = widgets[key]
                
                # Set initial red color and animate
                if isinstance(w, tuple) and len(w) == 5:
                    if key == "Disk I/O":
                        _, _, io_read_bar, io_write_bar, _ = w
                        fill_bar_gradually(io_read_bar, max_value=DISK_IO_MAX_MBPS, color=STATUS_COLORS['default'])
                        fill_bar_gradually(io_write_bar, max_value=DISK_IO_MAX_MBPS, color=STATUS_COLORS['default'])
                    else:
                        _, bar, _, _, _ = w
                        fill_bar_gradually(bar, color=STATUS_COLORS['default'])
                
                elif isinstance(w, dict):
                    for widget_key, widget in w.items():
                        try:
                            if hasattr(widget, 'config') and hasattr(widget, 'winfo_class'):
                                widget_class = widget.winfo_class()
                                
                                # Skip buttons, checkbuttons, scales, and other interactive widgets
                                if widget_class in ('TButton', 'TCheckbutton', 'TScale', 'Button', 'Checkbutton', 'Scale'):
                                    continue
                                    
                                # Only apply loading text to labels and text widgets
                                if widget_class in ('TLabel', 'Label', 'Text', 'Entry'):
                                    widget.config(text="Loading...", foreground=STATUS_COLORS['default'])
                                    
                        except (tk.TclError, AttributeError):
                            pass
            
            root.after(delay, animate_widget)
            delay += 200 + random.randint(0, 100)
        
        # After loading animation, start detection phase
        root.after(delay + 500, detection_phase)
    
    def detection_phase():
        """Phase 2: Test data sources and update colors."""
        def test_in_background():
            nonlocal detection_status
            detection_status = test_data_sources()
            
            # Update widget colors based on detection
            root.after(0, lambda: update_detection_display())
        
        def update_detection_display():
            for widget_key, status in detection_status.items():
                update_widget_status(widgets, widget_key, status, style)
            
            # Add some delay to show the color changes
            root.after(1000, tab_cycling_phase)
        
        # Run detection in background thread to avoid blocking UI
        threading.Thread(target=test_in_background, daemon=True).start()
    
    def tab_cycling_phase():
        """Phase 3: Cycle through tabs showing detection results."""
        if "notebook" in widgets:
            tab_count = len(widgets["notebook"].tabs())
            # Cycle through twice (2x) plus one final check (1x)
            max_cycles = tab_count * 2
            cycle_notebook_tabs(widgets, 0, max_cycles, detection_status, style, final_phase)
        else:
            final_phase()
    
    def final_phase():
        """Phase 4: Complete loading and start application."""
        end_loading(widgets, style, on_complete)
    
    # Start the enhanced loading sequence
    animate_loading_phase()