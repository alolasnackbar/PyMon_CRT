import os
import re
import subprocess
import time
import psutil
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

# --- Server Configuration ---
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
        
        # Use faster ping with shorter timeout
        if is_windows:
            command = ['ping', host_address, '-n', str(ping_count), '-w', '2000']
        else:
            command = ['ping', host_address, '-c', str(ping_count), '-W', '2', '-i', '0.5']
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(15, ping_count),  # More generous timeout
            check=False
        )

        output = result.stdout
        
        # Debug: Print raw output (comment out after testing)
        print(f"DEBUG - Ping to {host_address}:")
        print(f"Return code: {result.returncode}")
        print(f"Output: {output[:200]}")  # First 200 chars
        
        stats = {
            "avg": None,
            "min": None,
            "max": None,
            "packet_loss": 100.0,  # Default to 100% loss
            "sent": ping_count,
            "received": 0,
            "jitter": None
        }
        
        if is_windows:
            # Check for "Request timed out" or other errors
            if "Request timed out" in output or "could not find host" in output:
                print(f"DEBUG - Windows ping failed: Request timed out or host not found")
                return None
            
            # Fast regex parsing
            loss_match = re.search(r'\((\d+)%', output)
            if loss_match:
                stats["packet_loss"] = float(loss_match.group(1))
            else:
                # Try alternative format
                loss_match2 = re.search(r'Lost = \d+ \((\d+)%', output)
                if loss_match2:
                    stats["packet_loss"] = float(loss_match2.group(1))
            
            recv_match = re.search(r'Received = (\d+)', output)
            if recv_match:
                stats["received"] = int(recv_match.group(1))
            
            # Single regex for all stats - try multiple patterns
            stat_match = re.search(r'Minimum = (\d+)ms, Maximum = (\d+)ms, Average = (\d+)ms', output)
            if not stat_match:
                # Try without spaces
                stat_match = re.search(r'Minimum=(\d+)ms,Maximum=(\d+)ms,Average=(\d+)ms', output)
            
            if stat_match:
                stats["min"] = float(stat_match.group(1))
                stats["max"] = float(stat_match.group(2))
                stats["avg"] = float(stat_match.group(3))
                stats["jitter"] = round((stats["max"] - stats["min"]) / 2, 1)
            else:
                print(f"DEBUG - Could not parse Windows ping stats")
                
        else:
            # Check for errors
            if "100% packet loss" in output or "Unreachable" in output:
                print(f"DEBUG - Unix ping failed: 100% packet loss")
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
            else:
                print(f"DEBUG - Could not parse Unix ping stats")
        
        # Check if we got any valid data
        if stats["avg"] is None and stats["received"] == 0:
            print(f"DEBUG - No valid ping data received")
            return None
            
        print(f"DEBUG - Success! Avg: {stats['avg']}ms, Loss: {stats['packet_loss']}%")
        return stats
    except subprocess.TimeoutExpired:
        print(f"DEBUG - Ping timeout expired for {host_address}")
        return None
    except Exception as e:
        print(f"DEBUG - Ping exception: {e}")
        return None


def get_primary_interface():
    """Auto-select the main active interface - cached version."""
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
        
        # Return first active interface
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


# --- Color Functions ---
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


# --- GUI Application ---
class NetworkMonitorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Network Monitor with Server Ping")
        self.root.geometry("800x600")
        
        # Initialize cache and threading
        self.cache = PingCache()
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.interface = get_primary_interface()
        
        # Load servers
        self.servers = load_game_servers()
        self.server_list = list(self.servers.keys())
        
        # Selected server
        self.selected_server = tk.StringVar()
        if self.server_list:
            self.selected_server.set(self.server_list[0])
        
        # Ping results
        self.ping_in_progress = False
        
        # Create UI
        self.create_widgets()
        
        # Start background workers
        self.monitoring = True
        self.start_background_workers()
        
        # Start UI updates
        self.update_ui()
    
    def create_widgets(self):
        """Create all UI widgets."""
        main_frame = ttkb.Frame(self.root, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)
        
        # Title
        title_label = ttkb.Label(
            main_frame, 
            text="Network & Server Monitor", 
            font=("Helvetica", 16, "bold"),
            bootstyle="primary"
        )
        title_label.pack(pady=(0, 10))
        
        # Network Stats Frame
        net_frame = ttkb.LabelFrame(main_frame, text="Network Statistics", padding=10)
        net_frame.pack(fill=X, pady=(0, 10))
        
        self.info_labels = {}
        
        # Net Download/Upload (combined on one line)
        net_combined_label = ttkb.Label(net_frame, text="Net Down/Upload: 0.00/0.00 MB/s", font=("Courier", 11))
        net_combined_label.pack(anchor=W, pady=2)
        self.info_labels["Net Combined"] = net_combined_label
        
        # Latency
        lat_label = ttkb.Label(net_frame, text="Latency:         N/A", font=("Courier", 11))
        lat_label.pack(anchor=W, pady=2)
        self.info_labels["Latency"] = lat_label
        
        # Server Ping Frame
        server_frame = ttkb.LabelFrame(main_frame, text="Game Server Ping Test", padding=10)
        server_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))
        
        # Server selection row
        select_frame = ttkb.Frame(server_frame)
        select_frame.pack(fill=X, pady=(0, 10))
        
        ttkb.Label(select_frame, text="Select Server:", font=("Helvetica", 10)).pack(side=LEFT, padx=(0, 10))
        
        server_combo = ttkb.Combobox(
            select_frame,
            textvariable=self.selected_server,
            values=[f"{self.servers[k]['name']} ({self.servers[k]['region']})" for k in self.server_list],
            state="readonly",
            width=40
        )
        server_combo.pack(side=LEFT, padx=(0, 10))
        
        # Ping button
        self.ping_btn = ttkb.Button(
            select_frame,
            text="Ping Server",
            command=self.run_ping_test,
            bootstyle="success",
            width=15
        )
        self.ping_btn.pack(side=LEFT, padx=(0, 10))
        
        # Config button
        config_btn = ttkb.Button(
            select_frame,
            text="Edit Servers",
            command=self.open_config,
            bootstyle="info-outline",
            width=15
        )
        config_btn.pack(side=LEFT)
        
        # Results frame
        results_frame = ttkb.Frame(server_frame)
        results_frame.pack(fill=BOTH, expand=YES)
        
        # Status label
        self.status_label = ttkb.Label(
            results_frame,
            text="Select a server and click 'Ping Server' to test",
            font=("Helvetica", 10),
            bootstyle="secondary"
        )
        self.status_label.pack(pady=(0, 10))
        
        # Results display
        self.results_text = tk.Text(
            results_frame,
            height=12,
            font=("Courier", 10),
            bg="#2b2b2b",
            fg="#ffffff",
            insertbackground="#ffffff",
            state=DISABLED
        )
        self.results_text.pack(fill=BOTH, expand=YES)
        
        # Scrollbar
        scrollbar = ttkb.Scrollbar(self.results_text)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.results_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.results_text.yview)
    
    def start_background_workers(self):
        """Start background threads for measurements."""
        # Network usage worker
        def net_worker():
            while self.monitoring:
                net_in, net_out = measure_network_usage(self.interface, interval=0.2)
                self.cache.set_net(net_in, net_out)
                time.sleep(0.8)  # Update every second total
        
        # Latency worker
        def lat_worker():
            while self.monitoring:
                lat = quick_ping("8.8.8.8", count=3)
                self.cache.set_lat(lat)
                time.sleep(2)  # Update every 2 seconds
        
        # Start workers
        threading.Thread(target=net_worker, daemon=True).start()
        threading.Thread(target=lat_worker, daemon=True).start()
    
    def update_ui(self):
        """Update UI with cached data - runs on main thread."""
        if not self.monitoring:
            return
        
        # Get cached data (non-blocking)
        net_in, net_out = self.cache.get_net()
        lat = self.cache.get_lat()
        
        # Determine color based on higher of the two speeds
        max_speed = max(net_in, net_out)
        net_color = get_net_color(max_speed)
        
        # Update combined network label
        self.info_labels["Net Combined"].config(
            text=f"Net Down/Upload: {net_in:>5.2f}/{net_out:>5.2f} MB/s",
            foreground=net_color
        )
        
        lat_text = f"Latency:         {lat:>5.1f} ms" if lat is not None else "Latency:         N/A"
        self.info_labels["Latency"].config(
            text=lat_text,
            foreground=get_latency_color(lat)
        )
        
        # Schedule next UI update (fast refresh)
        self.root.after(100, self.update_ui)
    
    def run_ping_test(self):
        """Run ping test in background thread."""
        if self.ping_in_progress:
            return
        
        # Get selected server
        selected_text = self.selected_server.get()
        server_key = None
        for key in self.server_list:
            if f"{self.servers[key]['name']} ({self.servers[key]['region']})" == selected_text:
                server_key = key
                break
        
        if not server_key:
            return
        
        server = self.servers[server_key]
        
        # Update UI
        self.ping_in_progress = True
        self.ping_btn.config(state=DISABLED, text="Pinging...")
        self.status_label.config(
            text=f"Testing {server['name']} ({server['ip']})...",
            bootstyle="warning"
        )
        
        # Run in executor
        self.executor.submit(self.ping_thread, server)
    
    def ping_thread(self, server):
        """Background thread for ping test with fallback."""
        stats = ping_server_fast(server['ip'], ping_count=15)
        
        # If server is unreachable and has fallback, try fallback
        used_fallback = False
        if stats is None and server.get('fallback'):
            fallback_ip = server['fallback']
            stats = ping_server_fast(fallback_ip, ping_count=15)
            used_fallback = True if stats is not None else False
        
        self.root.after(0, self.display_ping_results, server, stats, used_fallback)
    
    def display_ping_results(self, server, stats, used_fallback=False):
        """Display ping results in the text widget."""
        self.ping_in_progress = False
        self.ping_btn.config(state=NORMAL, text="Ping Server")
        
        if stats is None:
            self.status_label.config(
                text=f"❌ {server['name']} - UNREACHABLE",
                bootstyle="danger"
            )
            fallback_note = f"\n\nNote: Server and fallback DNS ({server.get('fallback', 'N/A')}) both unreachable" if server.get('fallback') else ""
            self.update_results_text(f"Server: {server['name']} ({server['region']})\nIP: {server['ip']}\n\nStatus: UNREACHABLE{fallback_note}\n")
            return
        
        # Determine status
        avg = stats['avg'] if stats['avg'] else 999
        loss = stats['packet_loss']
        
        if loss > 5:
            status = "❌ Poor Connection"
            status_style = "danger"
        elif avg < 50:
            status = "✓ Excellent"
            status_style = "success"
        elif avg < 100:
            status = "⚠ Good"
            status_style = "warning"
        else:
            status = "⚠ Fair"
            status_style = "warning"
        
        # Add fallback indicator to status
        if used_fallback:
            status = f"{status} (Fallback DNS)"
            self.status_label.config(
                text=f"{status} - {server['name']}",
                bootstyle=status_style
            )
        else:
            self.status_label.config(
                text=f"{status} - {server['name']}",
                bootstyle=status_style
            )
        
        # Format results
        fallback_info = ""
        if used_fallback:
            fallback_info = f"\n⚠ NOTE: Primary server blocked ping. Using fallback DNS: {server.get('fallback')}\n   This shows network quality to the region, not the exact game server.\n"
        
        result_text = f"""Server: {server['name']} ({server['region']})
IP: {server['ip']}{fallback_info}

═══════════════════════════════════════════════════════
PING STATISTICS
═══════════════════════════════════════════════════════

Average Ping:    {stats['avg']:.1f} ms
Minimum Ping:    {stats['min']:.1f} ms
Maximum Ping:    {stats['max']:.1f} ms
Jitter:          {stats['jitter']:.1f} ms
Packet Loss:     {stats['packet_loss']:.0f}% ({stats['received']}/{stats['sent']} received)

Status: {status}
"""
        
        self.update_results_text(result_text)
    
    def update_results_text(self, text):
        """Update the results text widget."""
        self.results_text.config(state=NORMAL)
        self.results_text.delete(1.0, END)
        self.results_text.insert(1.0, text)
        self.results_text.config(state=DISABLED)
    
    def open_config(self):
        """Open the server configuration file."""
        filepath = os.path.abspath(DEFAULT_SERVERS_FILE)
        
        try:
            if os.name == 'nt':
                os.startfile(filepath)
            elif os.name == 'posix':
                if os.uname().sysname == 'Darwin':
                    subprocess.run(['open', filepath])
                else:
                    subprocess.run(['xdg-open', filepath])
            
            self.status_label.config(
                text=f"Opened {DEFAULT_SERVERS_FILE} - Restart to reload servers",
                bootstyle="info"
            )
        except Exception as e:
            self.status_label.config(
                text=f"Error opening config: {e}",
                bootstyle="danger"
            )
    
    def on_closing(self):
        """Handle window closing."""
        self.monitoring = False
        self.executor.shutdown(wait=False)
        self.root.destroy()


# --- Main ---
if __name__ == "__main__":
    root = ttkb.Window(themename="darkly")
    app = NetworkMonitorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()