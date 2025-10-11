import subprocess
import re
import os
import time
import psutil


def ping_host(host_address, ping_count=3, timeout=10):
    """
    Pings a host and returns the average latency in milliseconds.
    
    Args:
        host_address (str): The IP address or hostname to ping.
        ping_count (int): The number of pings to send (default: 3).
        timeout (int): Maximum time to wait for ping completion in seconds (default: 10).
        
    Returns:
        float: The average latency in milliseconds, or None if ping fails.
    """
    try:
        # Build cross-platform command
        if os.name == 'nt':  # Windows
            command = ['ping', '-n', str(ping_count), '-w', '1000', host_address]
        else:  # Linux/macOS
            command = ['ping', '-c', str(ping_count), '-W', '1', host_address]
        
        # Run the command and capture output
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False  # Don't raise exception on non-zero exit
        )

        # Check if ping was successful
        if result.returncode != 0:
            return None

        output = result.stdout
        
        # Parse output based on platform
        if os.name == 'nt':  # Windows
            # Try different Windows formats:
            # English: "Average = 12ms" or "Average = 12.34ms"
            # Some locales: "Média = 12ms" or "Moyenne = 12ms"
            match = re.search(r'(?:Average|Média|Moyenne|Promedio)\s*=\s*([\d.]+)\s*ms', output, re.IGNORECASE)
            
            if not match:
                # Fallback: try to extract any timing values and average them manually
                times = re.findall(r'(?:time|tiempo|temps|tempo)[<=]\s*([\d.]+)\s*ms', output, re.IGNORECASE)
                if times:
                    avg = sum(float(t) for t in times) / len(times)
                    return round(avg, 2)
        else:  # Linux/macOS
            # Standard format: "rtt min/avg/max/mdev = 10.123/12.345/14.567/1.234 ms"
            match = re.search(r'(?:rtt|round-trip)\s+min/avg/max/[^=]+=\s*[\d.]+/([\d.]+)/', output, re.IGNORECASE)
            
            if not match:
                # Alternative format: "min/avg/max = 10.123/12.345/14.567 ms"
                match = re.search(r'min/avg/max\s*=\s*[\d.]+/([\d.]+)/', output, re.IGNORECASE)

        if match:
            return round(float(match.group(1)), 2)
        
        return None  # Could not parse output
        
    except subprocess.TimeoutExpired:
        return None
    except FileNotFoundError:
        print("Error: 'ping' command not found. Is it installed?")
        return None
    except Exception as e:
        print(f"Ping failed with unexpected error: {e}")
        return None


def net_usage_latency(interface=None, ping_target="8.8.8.8", ping_count=3, 
                      interval=0.1, measure_latency=True):
    """
    Measure network usage and optionally latency for a given interface.
    
    Args:
        interface (str): Network interface name. If None, auto-detects primary interface.
        ping_target (str): Host to ping for latency measurement (default: 8.8.8.8).
        ping_count (int): Number of pings to send (default: 3).
        interval (float): Time interval for measuring network I/O (default: 0.1 seconds).
        measure_latency (bool): Whether to measure latency (default: True). 
                                Set to False for frequent calls to avoid overhead.
    
    Returns:
        tuple: (net_in_MB_per_s, net_out_MB_per_s, avg_latency_ms, interface_name, connection_type)
               Returns (0.0, 0.0, None, None, None) on failure.
    """
    net_in_MB = 0.0
    net_out_MB = 0.0
    avg_latency = None
    interface_name = None
    connection_type = None
    
    try:
        # Auto-detect interface if not specified
        if interface is None:
            result = get_primary_interface()
            if result == (None, None):
                return 0.0, 0.0, None, None, None
            interface_name, connection_type = result
        else:
            # If interface is provided as string, use it directly
            interface_name = interface
            connection_type = "Unknown"
        
        # 1. Measure Network Usage
        try:
            pernic1 = psutil.net_io_counters(pernic=True)
            
            if interface_name not in pernic1:
                print(f"Warning: Interface '{interface_name}' not found")
                return 0.0, 0.0, None, interface_name, connection_type

            bytes_recv1 = pernic1[interface_name].bytes_recv
            bytes_sent1 = pernic1[interface_name].bytes_sent

            time.sleep(interval)

            pernic2 = psutil.net_io_counters(pernic=True)
            
            if interface_name not in pernic2:
                print(f"Warning: Interface '{interface_name}' disappeared during measurement")
                return 0.0, 0.0, None, interface_name, connection_type

            bytes_recv2 = pernic2[interface_name].bytes_recv
            bytes_sent2 = pernic2[interface_name].bytes_sent

            # Calculate throughput in MB/s
            delta_recv = max(0, bytes_recv2 - bytes_recv1)  # Prevent negative values
            delta_sent = max(0, bytes_sent2 - bytes_sent1)
            
            net_in_MB = round(delta_recv / 1024 / 1024 / interval, 3)
            net_out_MB = round(delta_sent / 1024 / 1024 / interval, 3)

        except KeyError as e:
            print(f"Network interface error: {e}")
        except Exception as e:
            print(f"Network usage measurement failed: {e}")

        # 2. Measure Latency (optional)
        if measure_latency:
            try:
                avg_latency = ping_host(ping_target, ping_count)
            except Exception as e:
                print(f"Latency measurement failed: {e}")

        return net_in_MB, net_out_MB, avg_latency, interface_name, connection_type
        
    except Exception as e:
        print(f"Unexpected error in net_usage_latency: {e}")
        return 0.0, 0.0, None, None, None


def get_primary_interface():
    """
    Auto-select the main active interface, ignoring loopback and virtual interfaces.
    Returns tuple (interface_name, connection_type) or (None, None).
    connection_type will be "WiFi", "Ethernet", or "Unknown".
    """
    import platform
    
    try:
        stats = psutil.net_io_counters(pernic=True)
        addrs = psutil.net_if_addrs()
        if_stats = psutil.net_if_stats()
        
        system = platform.system()
        candidates = []
        
        for iface in stats.keys():
            if iface not in addrs or iface not in if_stats:
                continue
            
            low = iface.lower()
            
            # Skip loopback and virtual interfaces
            if low in ("lo", "loopback") or any(x in low for x in ["docker", "veth", "virtual", "vmnet", "vbox"]):
                continue
            
            # Check if interface is up and has an IP address
            is_up = if_stats[iface].isup
            has_ip = any(addr.family == 2 for addr in addrs[iface])  # AF_INET
            
            if not (is_up and has_ip):
                continue
            
            # Determine connection type
            conn_type = "Unknown"
            
            if system == "Windows":
                if "wi-fi" in low or "wireless" in low or "wlan" in low:
                    conn_type = "WiFi"
                elif "ethernet" in low or "local area" in low or "lan" in low:
                    conn_type = "Ethernet"
            elif system == "Linux":
                if "wlan" in low or "wifi" in low or "wlp" in low:
                    conn_type = "WiFi"
                elif "eth" in low or "enp" in low or "eno" in low or "ens" in low:
                    conn_type = "Ethernet"
            elif system == "Darwin":  # macOS
                if "en" in low:
                    conn_type = "Unknown"
            
            total_bytes = stats[iface].bytes_sent + stats[iface].bytes_recv
            candidates.append((iface, conn_type, total_bytes))
        
        if not candidates:
            return None, None
        
        # Sort by total bytes (most active first)
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        # Prefer WiFi or Ethernet over Unknown
        for iface, conn_type, _ in candidates:
            if conn_type in ("WiFi", "Ethernet"):
                return iface, conn_type
        
        # Return most active interface even if type is unknown
        return candidates[0][0], candidates[0][1]
        
    except Exception as e:
        print(f"Error detecting primary interface: {e}")
        return None, None


# Example usage
if __name__ == "__main__":
    # Test 1: Get primary interface
    iface, conn_type = get_primary_interface()
    print(f"Primary Interface: {iface} ({conn_type})")
    
    # Test 2: Quick network usage check (no latency)
    print("\nQuick network check (no ping):")
    in_mb, out_mb, latency, iface, conn = net_usage_latency(measure_latency=False)
    print(f"Interface: {iface} ({conn})")
    print(f"Download: {in_mb} MB/s, Upload: {out_mb} MB/s")
    
    # Test 3: Full network check with latency
    print("\nFull network check (with ping):")
    in_mb, out_mb, latency, iface, conn = net_usage_latency()
    print(f"Interface: {iface} ({conn})")
    print(f"Download: {in_mb} MB/s, Upload: {out_mb} MB/s")
    print(f"Latency: {latency} ms" if latency else "Latency: N/A")
    
    # Test 4: Direct ping test
    print("\nDirect ping test:")
    latency = ping_host("8.8.8.8", ping_count=4)
    print(f"Ping to 8.8.8.8: {latency} ms" if latency else "Ping failed")