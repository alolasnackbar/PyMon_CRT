# import tkinter as tk, os, sys
# def resource_path(rel_path):
#     if getattr(sys, "frozen", False):
#         base = os.path.dirname(sys.executable)
#     else:
#         base = os.path.dirname(os.path.abspath(__file__))
#     return os.path.join(base, rel_path)

# root = tk.Tk()
# try:
#     root.iconbitmap(resource_path("nohead_test.ico"))
#     print("ICON: loaded OK")
# except Exception as e:
#     print("ICON LOAD ERROR:", type(e).__name__, e)
# root.destroy()

import psutil
import platform
import subprocess
import time
# ---- Optional Windows WMI (for CPU model & temperature) ----
WMI_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import wmi  # type: ignore
        WMI_AVAILABLE = True
    except Exception:
        WMI_AVAILABLE = False

import wmi

# Global cache variables
_last_freq_check = 0
_last_freq = None
_freq_min = None
_freq_max = None
_freq_base = None  # Base frequency for calculations

# Try to import win32pdh, but don't fail if not available
try:
    import win32pdh
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

def get_cpu_temperature():
    """
    Retrieves the CPU temperature in Celsius using WMI.
    Returns:
        float: The CPU temperature in Celsius, or None if not found.
    """
    try:
        c = wmi.WMI(namespace="root\\wmi")
        temperature_info = c.MSAcpi_ThermalZoneTemperature()

        if temperature_info:
            # The temperature is returned in tenths of a Kelvin.
            # Convert to Celsius: (Kelvin / 10) - 273.15
            temp_kelvin_tenths = temperature_info[0].CurrentTemperature
            temp_celsius = (temp_kelvin_tenths / 10.0) - 273.15
            return temp_celsius
        else:
            print("Could not find CPU temperature information via WMI.")
            return None
    except wmi.x_wmi as e:
        print(f"WMI error: {e}")
        print("Ensure you have administrative privileges if encountering access denied errors.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

if __name__ == "__main__":
    cpu_temp = get_cpu_temperature()

    w = wmi.WMI(namespace="root\\wmi")
    while True:
        for sensor in w.MSAcpi_ThermalZoneTemperature():
            temp_c = (sensor.CurrentTemperature / 10.0) - 273.15
            print(f"{sensor.InstanceName}: {temp_c:.1f} °C")
        print("-----")
        time.sleep(2)
    #if cpu_temp is not None:
    # while cpu_temp is not None:
    #     print(f"Current CPU Temperature: {cpu_temp:.2f}°C")
    #     time.sleep(3)