"""
Network Monitor Tab Module
Combines network statistics monitoring with game server ping testing
"""

import os
import re
import subprocess
import time
import psutil
import tkinter as tk
import ttkbootstrap as tb
import threading
from concurrent.futures import ThreadPoolExecutor


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


def get_primary_interface():
    """Auto-select the main active interface."""
    try:
        stats = psutil.net_io_counters(pernic=True)
        for iface, data in stats.items():
            low = iface.lower()
            if low in ("lo", "loopback") or "docker" in low or "veth" in low or "virtual" in low:
                continue
            if data.bytes_sent > 0 or data.bytes_recv > 0:
                if "eth" in low or "lan" in low:
                    return iface
                elif "wlan" in low or "wifi" in low:
                    return iface
        
        for iface, data in stats.items():
            low = iface.lower()
            if low not in ("lo", "loopback") and "docker" not in low and data.bytes_sent > 0:
                return iface
        return None
    except:
        return None


def measure_network_usage(interface, interval=0.2):
    """Fast network usage measurement."""
    try:
        if interface is None:
            return 0.0, 0.0

        pernic1 = psutil.net_io_counters(pernic=True)
        if interface not in pernic1:
            return 0.0, 0.0

        bytes_recv1 = pernic1[interface].bytes_recv
        bytes_sent1 = pernic1[interface].bytes_sent

        time.sleep(interval)

        pernic2 = psutil.net_io_counters(pernic=True)
        if interface not in pernic2:
            return 0.0, 0.0

        bytes_recv2 = pernic2[interface].bytes_recv
        bytes_sent2 = pernic2[interface].bytes_sent

        net_in_MB = round((bytes_recv2 - bytes_recv1) / 1024 / 1024 / interval, 2)
        net_out_MB = round((bytes_sent2 - bytes_sent1) / 1024 / 1024 / interval, 2)

        return net_in_MB, net_out_MB
    except:
        return 0.0, 0.0


def quick_ping(host, count=3):
    """Ultra-fast ping for latency only."""
    try:
        is_windows = os.name == 'nt'
        if is_windows:
            cmd = ['ping', host, '-n', str(count), '-w', '500']
        else:
            cmd = ['ping', host, '-c', str(count), '-W', '1', '-i', '0.2']
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False)
        
        if is_windows:
            match = re.search(r'Average = (\d+)ms', result.stdout)
        else:
            match = re.search(r'= [\d.]+/([\d.]+)/', result.stdout)
        
        if match:
            return float(match.group(1))
        return None
    except:
        return None


def get_net_color(speed_MB):
    """Return color based on network speed."""
    if speed_MB > 10:
        return "#00ff00"
    elif speed_MB > 5:
        return "#7fff00"
    elif speed_MB > 1:
        return "#ffff00"
    elif speed_MB > 0.1:
        return "#ff7f00"
    else:
        return "#888888"


def get_latency_color(lat_ms):
    """Return color based on latency."""
    if lat_ms is None:
        return "#888888"
    elif lat_ms < 30:
        return "#00ff00"
    elif lat_ms < 60:
        return "#7fff00"
    elif lat_ms < 100:
        return "#ffff00"
    elif lat_ms < 150:
        return "#ff7f00"
    else:
        return "#ff0000"


# ============================================================================
# LAYOUT - UI Construction
# ============================================================================

def create_network_tab(nb, info_labels, FONT_NETTXT, CRT_GREEN):
    """
    Create the Network Stats tab with all widgets.
    
    Args:
        nb: Notebook widget to add the tab to
        info_labels: Dictionary to store widget references
        FONT_NETTXT: Font for network text
        CRT_GREEN: Default green color for text
    
    Returns:
        Dictionary containing server-related data for the tab
    """
    # --- Tab 3: Network Stats ---
    f_net = tb.Frame(nb)
    nb.add(f_net, text="Network Stats")
    f_net.columnconfigure(0, weight=1)

    # --- Network Download/Upload (multi-label, single line) ---
    net_frame = tb.Frame(f_net)
    net_frame.grid(row=0, column=0, sticky="w", padx=4, pady=1)

    # Prefix and static suffix labels (stay green)
    net_prefix_lbl = tb.Label(
        net_frame,
        text="Net Down/Upload:",
        anchor="w",
        font=FONT_NETTXT,
        foreground=CRT_GREEN
    )
    net_suffix_lbl = tb.Label(
        net_frame,
        text="MBs",
        anchor="w",
        font=FONT_NETTXT,
        foreground=CRT_GREEN
    )

    # Dynamic colored labels
    net_in_lbl = tb.Label(
        net_frame,
        text="0.00🡫",
        anchor="w",
        font=FONT_NETTXT,
        foreground=CRT_GREEN
    )
    net_out_lbl = tb.Label(
        net_frame,
        text="0.00🡩",
        anchor="w",
        font=FONT_NETTXT,
        foreground=CRT_GREEN
    )

    # Pack horizontally to mimic a single-line string
    net_prefix_lbl.pack(side="left")
    net_in_lbl.pack(side="left", padx=(4, 2))
    net_out_lbl.pack(side="left", padx=(2, 4))
    net_suffix_lbl.pack(side="left")

    # --- Latency + Ping Button Row ---
    latency_frame = tb.Frame(f_net)
    latency_frame.grid(row=1, column=0, sticky="ew", padx=4, pady=1)
    latency_frame.columnconfigure(0, weight=1)

    latency_lbl = tb.Label(
        latency_frame,
        text="Latency: ... ms",
        anchor="w",
        font=FONT_NETTXT,
        foreground=CRT_GREEN
    )
    latency_lbl.pack(side="left")

    # Ping button
    ping_btn = tb.Button(
        latency_frame,
        text="Ping",
        command=None,  # Will be set in main
        bootstyle="success-outline",
        width=8
    )
    ping_btn.pack(side="right", padx=2)

    # --- Separator ---
    separator1 = tb.Separator(f_net, orient="horizontal")
    separator1.grid(row=2, column=0, sticky="ew", padx=4, pady=6)

    # --- Server Selection Row ---
    server_select_frame = tb.Frame(f_net)
    server_select_frame.grid(row=3, column=0, sticky="ew", padx=4, pady=2)
    server_select_frame.columnconfigure(1, weight=1)

    # Server dropdown
    server_combo_label = tb.Label(
        server_select_frame,
        text="Server:",
        anchor="w",
        font=FONT_NETTXT,
        foreground=CRT_GREEN
    )
    server_combo_label.grid(row=0, column=0, sticky="w", padx=(0, 4))

    selected_server = tk.StringVar()
    server_combo = tb.Combobox(
        server_select_frame,
        textvariable=selected_server,
        values=[],  # Will be populated from game_servers.txt
        state="readonly",
        font=("Courier", 9),
        width=30
    )
    server_combo.grid(row=0, column=1, sticky="ew", padx=(0, 4))

    # Config button
    config_btn = tb.Button(
        server_select_frame,
        text="⚙",
        command=None,  # Will be set in main
        bootstyle="info-outline",
        width=3
    )
    config_btn.grid(row=0, column=2, sticky="e")

    # Status label for ping results
    ping_status_lbl = tb.Label(
        f_net,
        text="Select server and click Ping to test",
        anchor="w",
        font=("Courier", 9),
        foreground="#888888"
    )
    ping_status_lbl.grid(row=4, column=0, sticky="w", padx=4, pady=2)

    # Results frame with scrollable text
    results_frame = tb.Frame(f_net)
    results_frame.grid(row=5, column=0, sticky="nsew", padx=4, pady=2)
    results_frame.rowconfigure(0, weight=1)
    results_frame.columnconfigure(0, weight=1)

    # Configure f_net to expand results
    f_net.rowconfigure(5, weight=1)

    # Results text widget
    results_text = tk.Text(
        results_frame,
        height=10,
        font=("Courier", 9),
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
    results_scrollbar = tb.Scrollbar(results_frame, command=results_text.yview)
    results_scrollbar.grid(row=0, column=1, sticky="ns")
    results_text.config(yscrollcommand=results_scrollbar.set)

    # --- Store references in info_labels for easy updates ---
    info_labels["NetFrame"] = net_frame
    info_labels["NetPrefix"] = net_prefix_lbl
    info_labels["Net IN"] = net_in_lbl
    info_labels["Net OUT"] = net_out_lbl
    info_labels["NetSuffix"] = net_suffix_lbl
    info_labels["Latency"] = latency_lbl
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
        
        # Initialize cache and threading
        self.cache = PingCache()
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.interface = get_primary_interface()
        
        # Load servers
        self.servers = {}
        self.server_list = []
        
        # Monitoring state
        self.monitoring = True
        
        # Start background workers
        self.start_background_workers()
    
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
    
    def start_background_workers(self):
        """Start background threads for measurements."""
        # Network usage worker
        def net_worker():
            while self.monitoring:
                net_in, net_out = measure_network_usage(self.interface, interval=0.2)
                self.cache.set_net(net_in, net_out)
                time.sleep(0.8)
        
        # Latency worker
        def lat_worker():
            while self.monitoring:
                lat = quick_ping("8.8.8.8", count=3)
                self.cache.set_lat(lat)
                time.sleep(2)
        
        # Start workers
        threading.Thread(target=net_worker, daemon=True).start()
        threading.Thread(target=lat_worker, daemon=True).start()
    
    def update_network_display(self):
        """Update network stats display - call this from your main update loop."""
        if not self.monitoring:
            return
        
        # Get cached data (non-blocking)
        net_in, net_out = self.cache.get_net()
        lat = self.cache.get_lat()
        
        # Determine color based on higher of the two speeds
        max_speed = max(net_in, net_out)
        in_color = get_net_color(net_in)
        out_color = get_net_color(net_out)
        
        # Update network labels
        self.info_labels["Net IN"].config(
            text=f"{net_in:>5.2f}🡫",
            foreground=in_color
        )
        self.info_labels["Net OUT"].config(
            text=f"{net_out:>5.2f}🡩",
            foreground=out_color
        )
        
        # Only update latency if in normal mode (not showing server ping)
        if self.info_labels["LatencyMode"] == "normal":
            lat_text = f"Latency: {lat:>5.1f} ms" if lat is not None else "Latency: N/A"
            self.info_labels["Latency"].config(
                text=lat_text,
                foreground=get_latency_color(lat)
            )
    
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
                color = "#ff0000"
            elif avg < 50:
                status = "✓ Excellent"
                color = "#00ff00"
            elif avg < 100:
                status = "⚠ Good"
                color = "#ffff00"
            else:
                status = "⚠ Fair"
                color = "#ffaa00"
            
            if used_fallback:
                status += " (Fallback)"
            
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
                foreground="#00aaff"
            )
        except Exception as e:
            status_lbl.config(
                text=f"Error: {e}",
                foreground="#ff0000"
            )
    
    def shutdown(self):
        """Clean shutdown of background threads."""
        self.monitoring = False
        self.executor.shutdown(wait=False)


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def integrate_network_tab(root, nb, info_labels, FONT_NETTXT, CRT_GREEN):
    """
    Complete integration function - call this from your main application.
    
    Args:
        root: Main Tkinter root window
        nb: Notebook widget to add the tab to
        info_labels: Dictionary to store widget references
        FONT_NETTXT: Font for network text
        CRT_GREEN: Default green color for text
    
    Returns:
        NetworkTabController instance for managing the tab
    
    Example usage in main application:
        network_controller = integrate_network_tab(root, nb, info_labels, FONT_NETTXT, CRT_GREEN)
        
        # In your main update loop:
        def update_ui():
            network_controller.update_network_display()
            # ... other updates ...
            root.after(100, update_ui)
        
        # On application close:
        network_controller.shutdown()
    """
    # Create the UI layout
    tab_widgets = create_network_tab(nb, info_labels, FONT_NETTXT, CRT_GREEN)
    
    # Create the controller
    controller = NetworkTabController(root, info_labels)
    
    # Wire up the button commands
    tab_widgets["ping_btn"].config(command=controller.run_server_ping_test)
    tab_widgets["config_btn"].config(command=controller.open_server_config)
    
    # Load servers
    controller.load_servers()
    
    return controller


# ============================================================================
# STANDALONE DEMO - Run this file directly to test
# ============================================================================

if __name__ == "__main__":
    """Standalone demo - run this file directly to test the network tab."""
    
    # Create main window
    root = tb.Window(themename="darkly")
    root.title("Network Monitor - Standalone Demo")
    root.geometry("900x700")
    
    # Configure grid
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    
    # Create a labelframe to hold the notebook (mimicking your layout)
    main_frame = tb.Labelframe(root, text="Network Monitor", bootstyle="info")
    main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    main_frame.rowconfigure(0, weight=1)
    main_frame.columnconfigure(0, weight=1)
    
    # Create notebook
    nb = tb.Notebook(main_frame, bootstyle="dark")
    nb.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
    
    # Define constants (your application would provide these)
    FONT_NETTXT = ("Courier", 11)
    CRT_GREEN = "#00ff00"
    
    # Dictionary to store widget references
    info_labels = {}
    
    # Integrate the network tab
    network_controller = integrate_network_tab(root, nb, info_labels, FONT_NETTXT, CRT_GREEN)
    
    # Update loop
    def update_ui():
        network_controller.update_network_display()
        root.after(100, update_ui)
    
    # Start updates
    update_ui()
    
    # Handle close
    def on_closing():
        network_controller.shutdown()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Run the application
    print("Network Monitor Demo Running...")
    print("- Real-time network usage monitoring")
    print("- Latency monitoring to 8.8.8.8")
    print("- Game server ping testing")
    print(f"- Server config: {os.path.abspath(DEFAULT_SERVERS_FILE)}")
    root.mainloop()