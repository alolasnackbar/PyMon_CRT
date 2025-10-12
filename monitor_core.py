import psutil
import subprocess
import platform
import time
import shutil
import re
import os
import sys
from datetime import datetime
# Try to import win32pdh, but don't fail if not available
try:
    import win32pdh
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

# ---- CPU Info (cached) ----
_cpu_model_cache = None

# Global cache variables
_last_freq_check = 0
_last_freq = None
_freq_min = None
_freq_max = None
_freq_base = None

# ---- Disk I/O (rate based on actual elapsed) ----
_last_disk_io = psutil.disk_io_counters()
_last_disk_ts = time.time()

# ---- Optional Windows WMI (for CPU model & temperature) ----
WMI_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import wmi  # type: ignore
        WMI_AVAILABLE = True
    except Exception:
        WMI_AVAILABLE = False

# ---- Helpers ----
def _which(cmd: str) -> bool:
    """Check if a command is available in the system's PATH."""
    return shutil.which(cmd) is not None

def _run_cmd(args, timeout=0.3):
    """Run a subprocess command and return its output."""
    try:
        out = subprocess.check_output(args, stderr=subprocess.DEVNULL, timeout=timeout, text=True)
        return out.strip()
    except Exception:
        return None

def get_cpu_freq(rate_limit_sec: float = 1.0):
    """
    Returns a tuple (current_GHz, min_GHz, max_GHz).
    - `current_GHz`: live frequency updated at most once per `rate_limit_sec`.
    - `min_GHz`, `max_GHz`: cached once at startup.
    Returns (None, None, None) if unavailable.
    
    Uses Windows Performance Counters for real-time frequency data including turbo boost.
    Requires pywin32: pip install pywin32
    """
    global _last_freq_check, _last_freq, _freq_min, _freq_max, _freq_base
    
    try:
        now = time.time()
        
        # Initialize min/max/base once
        if _freq_min is None or _freq_max is None or _freq_base is None:
            # Try psutil first
            try:
                f = psutil.cpu_freq(percpu=False)
                if f:
                    # Note: min might be 0, so we check > 0
                    if f.min and f.min > 0:
                        _freq_min = round(f.min / 1000.0, 2)
                    if f.max and f.max > 0:
                        _freq_max = round(f.max / 1000.0, 2)
                        _freq_base = f.max  # Keep in MHz for calculations
            except Exception:
                pass
            
            # If we don't have base from psutil, get it from WMI
            if _freq_base is None:
                wmi_freq = _get_base_frequency_wmi()
                if wmi_freq and wmi_freq > 0:
                    _freq_base = wmi_freq
                    # Also set max if we don't have it
                    if _freq_max is None:
                        _freq_max = round(wmi_freq / 1000.0, 2)
            
            # Last resort: use current frequency as base
            if _freq_base is None:
                try:
                    f = psutil.cpu_freq(percpu=False)
                    if f and f.current and f.current > 0:
                        _freq_base = f.current
                        if _freq_max is None:
                            _freq_max = round(f.current / 1000.0, 2)
                except Exception:
                    pass
        
        # Rate-limit the "current" lookup
        if now - _last_freq_check >= rate_limit_sec or _last_freq is None:
            current_freq = _get_live_cpu_freq_windows()
            _last_freq = round(current_freq / 1000.0, 2) if current_freq else None
            _last_freq_check = now
        
        return (_last_freq, _freq_min, _freq_max)
    
    except Exception:
        return (None, None, None)


def _get_base_frequency_wmi():
    """Get the base/nominal CPU frequency from WMI (one-time lookup)"""
    try:
        import subprocess
        result = subprocess.run(
            ['wmic', 'cpu', 'get', 'MaxClockSpeed'],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:
                line = line.strip()
                if line and line.isdigit():
                    return float(line)  # Returns MHz
    except Exception:
        pass
    return None


def _get_live_cpu_freq_windows():
    """
    Get live CPU frequency on Windows using Performance Counters.
    Returns frequency in MHz or None if unavailable.
    """
    if not WIN32_AVAILABLE:
        return _get_freq_psutil()
    
    # Try Performance Counter method (most accurate for live data)
    freq = _get_freq_performance_counter()
    if freq:
        return freq
    
    # Fallback to psutil
    return _get_freq_psutil()


def _get_freq_performance_counter():
    """
    Use Windows Performance Counter to get actual live CPU frequency.
    Counter: \\Processor Information(_Total)\\% Processor Performance
    Returns percentage of base frequency (can exceed 100% with turbo boost).
    """
    if not WIN32_AVAILABLE or _freq_base is None:
        return None
    
    query = None
    try:
        # Counter path - shows CPU performance as percentage of base
        counter_path = r'\Processor Information(_Total)\% Processor Performance'
        
        # Open query
        query = win32pdh.OpenQuery(None, 0)
        
        # Add counter
        counter_handle = win32pdh.AddEnglishCounter(query, counter_path, 0)
        
        # Collect first sample
        win32pdh.CollectQueryData(query)
        
        # Wait briefly for delta calculation
        time.sleep(0.1)
        
        # Collect second sample
        win32pdh.CollectQueryData(query)
        
        # Get the value
        counter_type, value = win32pdh.GetFormattedCounterValue(
            counter_handle, 
            win32pdh.PDH_FMT_DOUBLE
        )
        
        # Close query
        win32pdh.CloseQuery(query)
        
        # Calculate actual frequency
        # value is percentage (e.g., 150 means 150% of base)
        # _freq_base is in MHz
        if value > 0:
            actual_freq = _freq_base * (value / 100.0)
            return actual_freq
            
    except Exception:
        if query:
            try:
                win32pdh.CloseQuery(query)
            except:
                pass
    
    return None


def _get_freq_psutil():
    """Fallback: Use psutil (may be static on Windows)"""
    try:
        f = psutil.cpu_freq(percpu=False)
        if f and f.current and f.current > 0:
            return f.current
    except Exception:
        pass
    return None


def get_internal_state():
    """
    Helper function to inspect internal state for debugging.
    Returns dict with all global cache variables.
    """
    return {
        'freq_base_mhz': _freq_base,
        'freq_min_ghz': _freq_min,
        'freq_max_ghz': _freq_max,
        'last_freq_ghz': _last_freq,
        'last_check_timestamp': _last_freq_check,
        'win32_available': WIN32_AVAILABLE
    }

# ---- CPU ----
def get_cpu_usage(interval=None):
    """
    Return CPU usage percent.
    - interval=None: instantaneous (requires prior warmup call by psutil).
    - interval>0: blocks for that interval.
    """
    try:
        return psutil.cpu_percent(interval=interval)
    except Exception:
        return 0.0

def get_cpu_info():
    global _cpu_model_cache
    if _cpu_model_cache is None:
        model = None
        try:
            system = platform.system()
            if system == "Windows":
                # Detect actual CPU model on Windows using WMI for a cleaner name
                out = _run_cmd(["wmic", "cpu", "get", "Name", "/value"])
                if out:
                    # Parse output (e.g., "Name=Intel(R) Core(TM) i7-13700K CPU @ 3.40GHz")
                    for line in out.splitlines():
                        if line.startswith("Name="):
                            model = line.split("=", 1)[1].strip()
                            break
            elif system == "Darwin":
                out = _run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])
                model = out or platform.processor()
            else:  # Linux or other Unix
                out = _run_cmd(["lscpu"])
                if out:
                    for line in out.splitlines():
                        if "Model name" in line:
                            model = line.split(":", 1)[1].strip()
                            break
                # Fallback to /proc/cpuinfo
                if not model:
                    try:
                        with open("/proc/cpuinfo") as f:
                            for line in f:
                                if "model name" in line:
                                    model = line.split(":", 1)[1].strip()
                                    break
                    except Exception:
                        pass
                # Final fallback
                if not model:
                    model = platform.processor() or platform.uname().processor
        except Exception:
            model = platform.processor() or "Unknown CPU"

        _cpu_model_cache = model or "Unknown CPU"

    return {
        "model": _cpu_model_cache,
        "physical_cores": psutil.cpu_count(logical=False) or 0,
        "logical_cores": psutil.cpu_count(logical=True) or 0,
    }

def get_cpu_temp():
    """
    Returns CPU temperature in Celsius, or None if not available.
    Supports `psutil.sensors_temperatures()` as the primary method for all platforms,
    with a robust search for common sensor names.
    """
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None

        # Tier 1: Look for common, explicit CPU/Core temperature sensors
        for name, sensors in temps.items():
            if sensors and any(kw in name.lower() for kw in ['cpu', 'core', 'package']):
                # Return the first found valid current temperature
                for sensor in sensors:
                    if sensor.current is not None:
                        return sensor.current

        # Tier 2: General fallback for any sensor that seems like a temperature reading
        for name, sensors in temps.items():
            if sensors and any(kw in name.lower() for kw in ['temp', 'thermal']):
                for sensor in sensors:
                    if sensor.current is not None:
                        return sensor.current

    except Exception:
        pass
    
    # Windows-specific WMI fallback
    if platform.system() == "Windows" and WMI_AVAILABLE:
        try:
            # FIX: Use a raw string (r"...") to avoid SyntaxWarning from '\w'
            w = wmi.WMI(namespace=r"root\wmi")
            temperature_info = w.MSAcpi_ThermalZoneTemperature()
            if temperature_info:
                # Temperature is in tenths of Kelvin
                return (temperature_info[0].CurrentTemperature / 10) - 273.15
        except Exception:
            pass

    return None

# ---- CPU htop Process Table ----
def get_load_average():
    """Return load average in Linux style, Windows shows CPU percent fallback."""
    try:
        load1, load5, load15 = os.getloadavg()
        return f"{load1:.2f} {load5:.2f} {load15:.2f}"
    except (AttributeError, OSError):
        # Windows fallback: show CPU usage %
        cpu = psutil.cpu_percent(interval=1)
        return f"{cpu:.1f}"
    
def get_top_processes(limit=5):
    """Return top processes sorted by CPU usage (safe across platforms)."""
    processes = []
    for p in psutil.process_iter(['pid', 'username', 'nice', 'memory_info', 'cpu_percent', 'name']):
        try:
            info = p.info
            virt = (info.get('memory_info').vms if info.get('memory_info') else 0) / (1024 * 1024)
            res = (info.get('memory_info').rss if info.get('memory_info') else 0) / (1024 * 1024)
            processes.append((
                info.get('pid', 0),
                (info.get('username') or "unknown")[:8],
                info.get('nice', 0),
                virt,
                res,
                info.get('cpu_percent', 0.0),
                p.memory_percent() if p else 0.0,
                info.get('name', "unknown")
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Sort by CPU%
    processes.sort(key=lambda x: x[5], reverse=True)

    top = []
    for proc in processes[:limit]:
        pid, user, nice, virt, res, cpu, mem, name = proc
        top.append(
            f"{pid:<6} {user:<8} {virt:>6.1f}M {res:>6.1f}M {cpu:>5.1f} {mem:>5.1f}  {name}"
        )
    return top

# ---- RAM ----
def get_ram_usage():
    try:
        return psutil.virtual_memory().percent
    except Exception:
        return 0.0

def get_ram_info():
    try:
        mem = psutil.virtual_memory()
        return {
            "used": round(mem.used / (1024**3), 2),
            "available": round(mem.available / (1024**3), 2),
        }
    except Exception:
        return {"used": 0.0, "available": 0.0}


def get_disk_io(interval=None):
    """
    Returns (read_MB_per_s, write_MB_per_s).
    Uses actual elapsed time since the previous call for accuracy.
    The 'interval' parameter is accepted for API compatibility but is not used to sleep.
    """
    global _last_disk_io, _last_disk_ts
    try:
        now = time.time()
        io_now = psutil.disk_io_counters()
        elapsed = max(1e-3, now - _last_disk_ts)  # avoid div by zero

        read_bytes = io_now.read_bytes - _last_disk_io.read_bytes
        write_bytes = io_now.write_bytes - _last_disk_io.write_bytes

        _last_disk_io = io_now
        _last_disk_ts = now

        read_mb_s = read_bytes / (1024 * 1024) / elapsed
        write_mb_s = write_bytes / (1024 * 1024) / elapsed
        return read_mb_s, write_mb_s
    except Exception:
        return 0.0, 0.0

# --- DISK space usage ---
def get_disk_summary(max_drives=3):
    """
    Returns a formatted string of disk usage for up to `max_drives` drives.
    
    Example output: "C: 120/500 GB | D: 300/1.1 GB"
    """
    summary = []
    try:
        partitions = psutil.disk_partitions()
        count = 0
        for part in partitions:
            if count >= max_drives:
                break
            try:
                usage = psutil.disk_usage(part.mountpoint)
                used_gb = round(usage.used / (1024 ** 3), 1)
                total_gb = round(usage.total / (1024 ** 3), 1)
                # Remove any trailing '\' or ':' from the drive letter
                drive_letter = part.device.strip(':\\')
                summary.append(f"{drive_letter}: {used_gb}/{total_gb} GB")
                count += 1
            except PermissionError:
                continue
    except Exception as e:
        print("Error retrieving disk summary:", e)
        return ""
    
    return " | ".join(summary)

# ---- GPU ----
def _nvidia_smi_available():
    return _which("nvidia-smi")
    
def _rocm_smi_available():
    return _which("rocm-smi")

def get_gpu_usage():
    """
    Returns GPU utilization percent (float) or None if not available.
    Supports NVIDIA (via nvidia-smi) and AMD (via rocm-smi on Linux).
    """
    try:
        if _nvidia_smi_available():
            out = _run_cmd(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], timeout=0.25)
            if out:
                return float(out.splitlines()[0].strip())
        elif platform.system() == "Linux" and _rocm_smi_available():
            out = _run_cmd(["rocm-smi", "--showuse", "--json"], timeout=0.25)
            if out:
                import json
                data = json.loads(out)
                # Parse the usage data from the JSON output
                gpus = data.get("GPUs", [])
                if gpus and gpus[0].get("GPU use (%)"):
                    return float(gpus[0]["GPU use (%)"].strip('% '))

    except Exception:
        return None
    return None

def get_gpu_clock_speed():
    """
    Returns the live GPU clock speed from nvidia-smi as a string.
    Returns "N/A" if nvidia-smi is not available or an error occurs.
    """
    nvidia_smi_path = "nvidia-smi"
    if os.name == 'nt' and not os.path.exists(os.path.join(os.environ.get('ProgramFiles', ''), 'NVIDIA Corporation', 'NVSMI', 'nvidia-smi.exe')):
        pass
    else:
        try:
            subprocess.run([nvidia_smi_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            return "N/A"

    try:
        output = subprocess.check_output([nvidia_smi_path, "--query-gpu=clocks.sm", "--format=csv,noheader,nounits"], universal_newlines=True)
        clock_speed_mhz = float(output.strip()) 
        return f"{clock_speed_mhz:>.0f}"
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError, ValueError) as e:
        return "N/A"


def get_gpu_temp():
    """
    Returns GPU temperature in Celsius, or None if not available.
    Supports NVIDIA (via nvidia-smi) and AMD (via rocm-smi on Linux).
    """
    try:
        if _nvidia_smi_available():
            out = _run_cmd(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"], timeout=0.25)
            if out:
                return float(out.splitlines()[0].strip())
        elif platform.system() == "Linux" and _rocm_smi_available():
            out = _run_cmd(["rocm-smi", "--showtemp", "--json"], timeout=0.25)
            if out:
                import json
                data = json.loads(out)
                gpus = data.get("GPUs", [])
                if gpus and gpus[0].get("Temperature (Sensor)"):
                    temp_data = gpus[0]["Temperature (Sensor)"]
                    if isinstance(temp_data, dict) and "temp (C)" in temp_data:
                        return float(temp_data["temp (C)"])
                    return float(temp_data.strip(' C'))

    except Exception:
        return None
    return None

def get_gpu_info():
    if _nvidia_smi_available():
        out = _run_cmd(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], timeout=0.25)
        return out if out else "NVIDIA GPU"
    elif platform.system() == "Linux" and _rocm_smi_available():
        out = _run_cmd(["rocm-smi", "--showproductname"], timeout=0.25)
        return out.splitlines()[-1] if out else "AMD GPU"
    elif platform.system() == "Windows" and WMI_AVAILABLE:
        try:
            w = wmi.WMI()
            gpus = w.Win32_VideoController()
            if gpus:
                for gpu in gpus:
                    if "NVIDIA" in gpu.name:
                        return gpu.name
                    if "AMD" in gpu.name:
                        return gpu.name
                return gpus[0].name
        except Exception:
            pass
    return None


# ---- Time & Uptime ----
def get_local_date():
    """Return the current local date as a formatted string."""
    return datetime.now().strftime("%a, %b %d, %Y")

def get_local_time():
    """Return the current local time as a formatted string."""
    return datetime.now().strftime("%H:%M:%S %p")

def get_uptime():
    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"
    except Exception:
        return "N/A"


# ---- ENHANCED NETWORK FUNCTIONS (from first file) ----

def ping_host(host_address, ping_count=3, timeout=10):
    """
    Pings a host and returns the average latency in milliseconds.
    Enhanced with robust cross-platform parsing and multiple fallbacks.
    
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


def net_usage_latency(interface=None, ping_target="8.8.8.8", ping_count=3, 
                      interval=0.1, measure_latency=True):
    """
    Measure network usage and optionally latency for a given interface.
    Enhanced with better error handling and auto-detection.
    
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