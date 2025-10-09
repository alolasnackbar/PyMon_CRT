"""
Network Monitor Tab Module - Integrated Version
Combines network statistics monitoring with game server ping testing
"""

import os
import re
import subprocess
import time
import psutil
import tkinter as tk
import threading
from concurrent.futures import ThreadPoolExecutor
from constants import *


# ============================================================================
# CORE - Server Configuration & Network Functions
# ============================================================================

DEFAULT_SERVERS_FILE = "game_servers.txt"

def load_game_servers(filepath=DEFAULT_SERVERS_FILE):
    """Load game servers from a text file."""
    servers = {}
    
    default_servers = {
        "na_riot": {"name": "Riot NA", "region": "US-West", "ip": "104.160.131.1", "fallback": "8.8.8.8"},
        "euw_riot": {"name": "Riot EUW", "region": "EU-West", "ip": "104.160.141.1", "fallback": "1.1.1.1"},
        "oce_riot": {"name": "Riot OCE", "region": "OCE-AUS", "ip": "104.160.152.3", "fallback": "1.0.0.1"}
    }
    
    if not os.path.exists(filepath):
        try:
            with open(filepath, 'w') as f:
                f.write("# Game Server Configuration (Riot Games)\n")
                f.write("# Format: ServerName,Region,IPAddress,FallbackDNS(optional)\n")
                f.write("# Fallback DNS will be used if main server doesn't respond to ping\n")
                f.write("# Add more servers below - one per line\n\n")
                f.write("# Riot Games Servers\n")
                f.write("Riot NA,US-West,104.160.131.1,8.8.8.8\n")
                f.write("Riot EUW,EU-West,104.160.141.1,1.1.1.1\n")
                f.write("Riot OCE,OCE-AUS,104.160.152.3,1.0.0.1\n\n")
                f.write("# Alternative Test Servers (DNS servers that respond to ping)\n")
                f.write("Google DNS,US,8.8.8.8\n")
                f.write("Cloudflare US,US,1.1.1.1\n")
                f.write("Cloudflare Sydney,OCE-AUS,1.0.0.1\n")
        except:
            pass
        return default_servers
    
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    server_name = parts[0]
                    region = parts[1]
                    ip = parts[2]
                    fallback = parts[3] if len(parts) >= 4 else None
                    
                    key = server_name.lower().replace(' ', '_').replace('-', '_')
                    servers[key] = {
                        "name": server_name, 
                        "region": region, 
                        "ip": ip,
                        "fallback": fallback
                    }
        
        if not servers:
            return default_servers
        return servers
    except:
        return default_servers


class PingCache:
    """Cache for network measurements to avoid blocking."""
    def __init__(self):
        self.net_cache = {"in": 0.0, "out": 0.0, "timestamp": 0}
        self.lat_cache = {"latency": None, "timestamp": 0}
        self.lock = threading.Lock()
    
    def get_net(self):
        with self.lock:
            return self.net_cache["in"], self.net_cache["out"]
    
    def set_net(self, net_in, net_out):
        with self.lock:
            self.net_cache = {"in": net_in, "out": net_out, "timestamp": time.time()}
    
    def get_lat(self):
        with self.lock:
            return self.lat_cache["latency"]
    
    def set_lat(self, latency):
        with self.lock:
            self.lat_cache = {"latency": latency, "timestamp": time.time()}


def ping_server_fast(host_address, ping_count=10):
    """Fast ping with minimal parsing."""
    try:
        is_windows = os.name == 'nt'
        
        if is_windows:
            command = ['ping', host_address, '-n', str(ping_count), '-w', '2000']
        else:
            command = ['ping', host_address, '-c', str(ping_count), '-W', '2', '-i', '0.5']
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(15, ping_count),
            check=False
        )

        output = result.stdout
        
        stats = {
            "avg": None,
            "min": None,
            "max": None,
            "packet_loss": 100.0,
            "sent": ping_count,
            "received": 0,
            "jitter": None
        }
        
        if is_windows:
            if "Request timed out" in output or "could not find host" in output:
                return None
            
            loss_match = re.search(r'\((\d+)%', output)
            if loss_match:
                stats["packet_loss"] = float(loss_match.group(1))
            else:
                loss_match2 = re.search(r'Lost = \d+ \((\d+)%', output)
                if loss_match2:
                    stats["packet_loss"] = float(loss_match2.group(1))
            
            recv_match = re.search(r'Received = (\d+)', output)
            if recv_match:
                stats["received"] = int(recv_match.group(1))
            
            stat_match = re.search(r'Minimum = (\d+)ms, Maximum = (\d+)ms, Average = (\d+)ms', output)
            if not stat_match:
                stat_match = re.search(r'Minimum=(\d+)ms,Maximum=(\d+)ms,Average=(\d+)ms', output)
            
            if stat_match:
                stats["min"] = float(stat_match.group(1))
                stats["max"] = float(stat_match.group(2))
                stats["avg"] = float(stat_match.group(3))
                stats["jitter"] = round((stats["max"] - stats["min"]) / 2, 1)
                
        else:
            if "100% packet loss" in output or "Unreachable" in output:
                return None
            
            loss_match = re.search(r'(\d+)% packet loss', output)
            if loss_match:
                stats["packet_loss"] = float(loss_match.group(1))
            
            recv_match = re.search(r'(\d+) received', output)
            if recv_match:
                stats["received"] = int(recv_match.group(1))
            
            rtt_match = re.search(r'= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', output)
            if rtt_match:
                stats["min"] = float(rtt_match.group(1))
                stats["avg"] = float(rtt_match.group(2))
                stats["max"] = float(rtt_match.group(3))
                stats["jitter"] = float(rtt_match.group(4))
        
        if stats["avg"] is None and stats["received"] == 0:
            return None
            
        return stats
    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        return None


# ============================================================================
# LAYOUT - UI Construction (Modified for gui.py integration)
# ============================================================================

def create_network_tab_integrated(f_net, info_labels, FONT_NETTXT, CRT_GREEN):
    """
    Create the Network Stats tab widgets - INTEGRATED VERSION for gui.py
    This version extends the existing Network Stats tab instead of creating a new one.
    
    Args:
        f_net: The existing Network Stats frame from gui.py
        info_labels: Dictionary to store widget references (from gui.py)
        FONT_NETTXT: Font for network text
        CRT_GREEN: Default green color for text
    
    Returns:
        Dictionary containing server-related widgets for command binding
    """
    # Note: Row 0 and 1 already contain network stats from gui.py
    # We'll add the server ping functionality starting from row 2
    
    # --- Separator ---
    separator1 = tk.Frame(f_net, height=2, bg="#444444")
    separator1.grid(row=2, column=0, sticky="ew", padx=4, pady=6)

    # --- Server Selection Row ---
    server_select_frame = tk.Frame(f_net, bg=f_net.cget('bg'))
    server_select_frame.grid(row=3, column=0, sticky="ew", padx=4, pady=2)
    server_select_frame.columnconfigure(1, weight=1)

    # Server dropdown
    server_combo_label = tk.Label(
        server_select_frame,
        text="Server:",
        anchor="w",
        font=FONT_NETTXT,
        foreground=CRT_GREEN,
        bg=server_select_frame.cget('bg')
    )
    server_combo_label.grid(row=0, column=0, sticky="w", padx=(0, 4))

    selected_server = tk.StringVar()
    
    # Use ttk.Combobox for better styling compatibility
    try:
        import ttkbootstrap as tb
        server_combo = tb.Combobox(
            server_select_frame,
            textvariable=selected_server,
            values=[],
            state="readonly",
            font=FONT_COFIG,
            width=30
        )
    except:
        import tkinter.ttk as ttk
        server_combo = ttk.Combobox(
            server_select_frame,
            textvariable=selected_server,
            values=[],
            state="readonly",
            font=FONT_COFIG,
            width=30
        )
    
    server_combo.grid(row=0, column=1, sticky="ew", padx=(0, 4))

    # Ping button - initially without command
    try:
        import ttkbootstrap as tb
        ping_btn = tb.Button(
            server_select_frame,
            text="Ping",
            command=None,
            bootstyle="success-outline",
            width=8
        )
    except:
        import tkinter.ttk as ttk
        ping_btn = ttk.Button(
            server_select_frame,
            text="Ping",
            command=None,
            width=8
        )
    
    ping_btn.grid(row=0, column=2, sticky="e", padx=(0, 2))

    # Config button
    try:
        import ttkbootstrap as tb
        config_btn = tb.Button(
            server_select_frame,
            text="⚙",
            command=None,
            bootstyle="success-outline",
            width=3
        )
    except:
        import tkinter.ttk as ttk
        config_btn = ttk.Button(
            server_select_frame,
            text="⚙",
            command=None,
            width=3
        )
    
    config_btn.grid(row=0, column=3, sticky="e")

    # Status label for ping results
    ping_status_lbl = tk.Label(
        f_net,
        text="Select server and click Ping to test",
        anchor="w",
        font=FONT_COFIG,
        foreground="#888888",
        bg=f_net.cget('bg')
    )
    ping_status_lbl.grid(row=4, column=0, sticky="w", padx=4, pady=2)

    # Results frame with scrollable text
    results_frame = tk.Frame(f_net, bg=f_net.cget('bg'))
    results_frame.grid(row=5, column=0, sticky="nsew", padx=4, pady=2)
    results_frame.rowconfigure(0, weight=1)
    results_frame.columnconfigure(0, weight=1)

    # Configure f_net to expand results
    f_net.rowconfigure(5, weight=1)

    # Results text widget
    results_text = tk.Text(
        results_frame,
        height=10,
        font=FONT_COFIG,
        bg="#1a1a1a",
        fg=CRT_GREEN,
        insertbackground=CRT_GREEN,
        state=tk.DISABLED,
        wrap=tk.WORD,
        relief="sunken",
        borderwidth=1
    )
    results_text.grid(row=0, column=0, sticky="nsew")

    # Scrollbar
    try:
        import ttkbootstrap as tb
        results_scrollbar = tb.Scrollbar(results_frame, command=results_text.yview)
    except:
        results_scrollbar = tk.Scrollbar(results_frame, command=results_text.yview)
    
    results_scrollbar.grid(row=0, column=1, sticky="ns")
    results_text.config(yscrollcommand=results_scrollbar.set)

    # --- Store references in info_labels for easy updates ---
    info_labels["ServerCombo"] = server_combo
    info_labels["SelectedServer"] = selected_server
    info_labels["PingButton"] = ping_btn
    info_labels["PingStatus"] = ping_status_lbl
    info_labels["ResultsText"] = results_text
    info_labels["ConfigButton"] = config_btn

    # Latency display state
    info_labels["LatencyMode"] = "normal"  # "normal" or "server"
    info_labels["LatencyRevertTimer"] = None
    
    # Return tab-specific data
    return {
        "ping_btn": ping_btn,
        "config_btn": config_btn
    }


# ============================================================================
# MAIN - Application Logic & Integration
# ============================================================================

class NetworkTabController:
    """Controller for the Network Tab - handles all business logic."""
    
    def __init__(self, root, info_labels):
        """
        Initialize the network tab controller.
        
        Args:
            root: Main Tkinter root window
            info_labels: Dictionary containing widget references
        """
        self.root = root
        self.info_labels = info_labels
        
        # Initialize threading
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Load servers
        self.servers = {}
        self.server_list = []
        
        # Monitoring state
        self.monitoring = True
    
    def load_servers(self):
        """Load game servers and populate the dropdown."""
        self.servers = load_game_servers()
        self.server_list = list(self.servers.keys())
        
        # Format server names for dropdown
        display_names = [f"{self.servers[k]['name']} ({self.servers[k]['region']})" 
                        for k in self.server_list]
        
        server_combo = self.info_labels["ServerCombo"]
        server_combo['values'] = display_names
        
        if display_names:
            self.info_labels["SelectedServer"].set(display_names[0])
    
    def run_server_ping_test(self):
        """Run ping test in background thread and update latency display."""
        ping_btn = self.info_labels["PingButton"]
        status_lbl = self.info_labels["PingStatus"]
        latency_lbl = self.info_labels["Latency"]
        
        if ping_btn['state'] == 'disabled':
            return
        
        # Cancel any existing revert timer
        if self.info_labels["LatencyRevertTimer"]:
            self.root.after_cancel(self.info_labels["LatencyRevertTimer"])
            self.info_labels["LatencyRevertTimer"] = None
        
        # Get selected server
        selected_text = self.info_labels["SelectedServer"].get()
        
        server_key = None
        for key in self.server_list:
            if f"{self.servers[key]['name']} ({self.servers[key]['region']})" == selected_text:
                server_key = key
                break
        
        if not server_key:
            return
        
        server = self.servers[server_key]
        
        # Update UI
        ping_btn.config(state='disabled', text="...")
        status_lbl.config(text=f"Pinging {server['name']}...", foreground="#ffaa00")
        self.info_labels["LatencyMode"] = "server"
        latency_lbl.config(text="Latency: Pinging...", foreground="#ffaa00")
        
        # Run in background thread
        def ping_thread():
            stats = ping_server_fast(server['ip'], ping_count=15)
            
            # Try fallback if needed
            used_fallback = False
            if stats is None and server.get('fallback'):
                stats = ping_server_fast(server['fallback'], ping_count=15)
                used_fallback = True if stats is not None else False
            
            # Update UI on main thread
            self.root.after(0, self.display_ping_results, server, stats, used_fallback)
        
        threading.Thread(target=ping_thread, daemon=True).start()
    
    def display_ping_results(self, server, stats, used_fallback=False):
        """Display ping results and update latency display."""
        ping_btn = self.info_labels["PingButton"]
        status_lbl = self.info_labels["PingStatus"]
        results_text = self.info_labels["ResultsText"]
        latency_lbl = self.info_labels["Latency"]
        
        ping_btn.config(state='normal', text="Ping")
        
        if stats is None:
            status_lbl.config(text=f"❌ {server['name']} - UNREACHABLE", foreground="#ff0000")
            latency_lbl.config(text="Latency: UNREACHABLE", foreground="#ff0000")
            result = f"Server: {server['name']} ({server['region']})\nIP: {server['ip']}\n\nStatus: UNREACHABLE\n"
            if server.get('fallback'):
                result += f"\nFallback DNS also unreachable: {server['fallback']}"
        else:
            avg = stats['avg'] if stats['avg'] else 999
            loss = stats['packet_loss']
            
            # Determine status
            if loss > 5:
                status = "❌ Poor"
                color = CRT_RED
            elif avg < 50:
                status = "✓ Excellent"
                color = CRT_GREEN
            elif avg < 100:
                status = "⚠ Good"
                color = CRT_YELLOW
            else:
                status = "⚠ Fair"
                color = CRT_CYAN #"#ffaa00" 
            
            if used_fallback:
                status += " (Unreachable Fallback used)"
            
            status_lbl.config(text=f"{status} - {server['name']}", foreground=color)
            
            # Update latency display with server ping
            self.info_labels["LatencyMode"] = "server"
            latency_lbl.config(
                text=f"Latency: {avg:.1f} ms ({server['name']})",
                foreground=color
            )
            
            # Format results
            result = f"""Server: {server['name']} ({server['region']})
IP: {server['ip']}
{'⚠ Using fallback DNS: ' + server.get('fallback', '') if used_fallback else ''}

{'='*45}
PING STATISTICS
{'='*45}

Average:      {stats['avg']:.1f} ms
Minimum:      {stats['min']:.1f} ms
Maximum:      {stats['max']:.1f} ms
Jitter:       {stats['jitter']:.1f} ms
Packet Loss:  {stats['packet_loss']:.0f}% ({stats['received']}/{stats['sent']})

Status: {status}
"""
        
        # Update text widget
        results_text.config(state=tk.NORMAL)
        results_text.delete(1.0, tk.END)
        results_text.insert(1.0, result)
        results_text.config(state=tk.DISABLED)
        
        # Schedule revert to normal latency after 5 seconds
        def revert_latency():
            if self.info_labels["LatencyMode"] == "server":
                self.info_labels["LatencyMode"] = "normal"
                self.info_labels["LatencyRevertTimer"] = None
        
        if self.info_labels["LatencyRevertTimer"]:
            self.root.after_cancel(self.info_labels["LatencyRevertTimer"])
        
        self.info_labels["LatencyRevertTimer"] = self.root.after(5000, revert_latency)
    
    def open_server_config(self):
        """Open the server configuration file."""
        filepath = os.path.abspath(DEFAULT_SERVERS_FILE)
        status_lbl = self.info_labels["PingStatus"]
        
        try:
            if os.name == 'nt':
                os.startfile(filepath)
            elif os.name == 'posix':
                if os.uname().sysname == 'Darwin':
                    subprocess.run(['open', filepath])
                else:
                    subprocess.run(['xdg-open', filepath])
            
            status_lbl.config(
                text="Config opened - Restart to reload",
                foreground=CRT_YELLOW
            )
        except Exception as e:
            status_lbl.config(
                text=f"Error: {e}",
                foreground=CRT_RED
            )
    
    def shutdown(self):
        """Clean shutdown of background threads."""
        self.monitoring = False
        self.executor.shutdown(wait=False)


# ============================================================================
# INTEGRATION HELPER FOR gui.py
# ============================================================================

def integrate_network_tab_to_gui(root, widgets, FONT_NETTXT, CRT_GREEN):
    """
    Integration function specifically for gui.py
    
    This function extends the existing Network Stats tab with server ping functionality.
    Call this from gui.py after the widgets dictionary is populated.
    
    Args:
        root: Main Tkinter root window (from gui.py)
        widgets: The widgets dictionary from gui.py
        FONT_NETTXT: Font for network text (from constants.py)
        CRT_GREEN: Default green color for text (from constants.py)
    
    Returns:
        NetworkTabController instance for managing the tab
    
    Usage in gui.py:
        # After widgets = build_metrics(root, style)
        network_controller = integrate_network_tab_to_gui(root, widgets, FONT_NETTXT, CRT_GREEN)
        
        # In your application close handler:
        def on_close():
            network_controller.shutdown()
            # ... rest of cleanup ...
    """
    # Get the existing Network Stats frame and info_labels
    if "Sys Info" not in widgets:
        raise ValueError("Widgets dictionary must contain 'Sys Info' key")
    
    info_labels = widgets["Sys Info"]
    
    # Find the Network Stats tab frame
    # Looking for the parent frame that contains the network widgets
    f_net = None
    if "NetFrame" in info_labels:
        # Get the parent of NetFrame which should be the tab frame
        f_net = info_labels["NetFrame"].master
    
    if f_net is None:
        raise ValueError("Could not find Network Stats tab frame")
    
    # Create the additional UI components
    tab_widgets = create_network_tab_integrated(f_net, info_labels, FONT_NETTXT, CRT_GREEN)
    
    # Create the controller
    controller = NetworkTabController(root, info_labels)
    
    # Wire up the button commands
    tab_widgets["ping_btn"].config(command=controller.run_server_ping_test)
    tab_widgets["config_btn"].config(command=controller.open_server_config)
    
    # Load servers
    controller.load_servers()
    
    return controller