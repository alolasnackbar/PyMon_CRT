import os
import platform
import subprocess
import time

# Optional: only import wmi if on Windows
if platform.system() == "Windows":
    try:
        #import wmi
        import ctypes
    except ImportError:
        #wmi = None
        ctypes = None

def run_cmd(cmd):
    """Run a shell command safely, return stripped output or empty string."""
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""

# ---- Linux CPU live usage ----
def get_cpu_usage_linux(interval=0.1):
    """Return CPU usage % over a short interval (Linux only)."""
    with open("/proc/stat", "r") as f:
        first = f.readline().split()[1:]
        first = list(map(int, first))

    time.sleep(interval)

    with open("/proc/stat", "r") as f:
        second = f.readline().split()[1:]
        second = list(map(int, second))

    total1, total2 = sum(first), sum(second)
    idle1, idle2 = first[3], second[3]

    total_diff = total2 - total1
    idle_diff = idle2 - idle1

    usage = (1 - (idle_diff / total_diff)) * 100 if total_diff else 0
    return usage

def get_cpu_usage():
    system = platform.system()
    if system == "Windows":
        out = run_cmd("wmic cpu get loadpercentage")
        parts = [p for p in out.split() if p.isdigit()]
        return float(parts[-1]) if parts else 0.0
    elif system == "Linux":
        return get_cpu_usage_linux()
    elif system == "Darwin":  # macOS
        out = run_cmd("ps -A -o %cpu")
        try:
            values = [float(x) for x in out.split()[1:]]
            return sum(values)
        except:
            return 0.0
    return 0.0

def get_gpu_usage():
    out = run_cmd("nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits")
    try:
        return float(out)
    except:
        return 0.0

def get_temp():
    system = platform.system()
    if system == "Linux":
        try:
            for zone in os.listdir("/sys/class/thermal"):
                path = f"/sys/class/thermal/{zone}/temp"
                if os.path.isfile(path):
                    with open(path) as f:
                        val = int(f.read().strip())
                        return f"{val/1000:.1f}°C"
        except:
            pass
    # elif system == "Windows" and wmi is not None:
    #     try:
    #         w = wmi.WMI(namespace="root\\wmi")
    #         temps = w.MSAcpi_ThermalZoneTemperature()
    #         if temps:
    #             return f"{(temps[0].CurrentTemperature / 10) - 273.15:.1f}°C"
    #     except Exception:
    #         pass
    return "N/A"

# ---- RAM Usage (Cross-platform) ----
def get_ram_usage():
    system = platform.system()
    if system == "Windows":
        out = run_cmd("wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value")
        try:
            lines = out.splitlines()
            free = int([l for l in lines if l.startswith("FreePhysicalMemory")][0].split("=")[1])
            total = int([l for l in lines if l.startswith("TotalVisibleMemorySize")][0].split("=")[1])
            used = total - free
            return (used / total) * 100
        except:
            return 0.0
    elif system in ["Linux", "Darwin"]:
        out = run_cmd("free -m") if system == "Linux" else run_cmd("vm_stat")
        try:
            if system == "Linux":
                lines = out.splitlines()
                mem_line = [l for l in lines if l.startswith("Mem:")][0].split()
                total, used = int(mem_line[1]), int(mem_line[2])
                return (used / total) * 100
            else:  # macOS vm_stat reports pages
                lines = {l.split(":")[0]: int(l.split(":")[1].strip().replace(".", "")) for l in out.splitlines() if ":" in l}
                page_size = 4096  # 4K pages
                free = (lines["Pages free"] + lines.get("Pages inactive", 0)) * page_size
                total = (lines["Pages free"] + lines["Pages active"] + lines["Pages inactive"] + lines["Pages speculative"]) * page_size
                used = total - free
                return (used / total) * 100
        except:
            return 0.0
    return 0.0

# ---- Disk Usage (Cross-platform) ----
def get_disk_usage():
    system = platform.system()
    if system == "Windows" and ctypes is not None:
        try:
            drive = os.getenv("SystemDrive", "C:\\")  # dynamically get system drive
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(drive),
                                                       ctypes.pointer(free_bytes),
                                                       ctypes.pointer(total_bytes),
                                                       None)
            used = total_bytes.value - free_bytes.value
            return (used / total_bytes.value) * 100
        except:
            return 0.0
    else:  # Linux & macOS
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        return (used / total) * 100

