import threading
import time
import os
from collections import deque

import psutil
import wmi
def get_primary_interface():
    """
    Auto-select the main active interface, ignoring loopback and common virtuals.
    Returns "WiFi", "Ethernet", or None.
    """
    try:
        stats = psutil.net_io_counters(pernic=True)
        # Prioritize interfaces based on naming conventions
        for iface, data in stats.items():
            low = iface.lower()
            if low in ("lo", "loopback") or "docker" in low or "veth" in low or "virtual" in low:
                continue
            if data.bytes_sent > 0 or data.bytes_recv > 0:
                if "eth" in low or "lan" in low:
                    return "Ethernet"
                elif "wlan" in low or "wifi" in low:
                    return "WiFi"
        
        # Fallback to the first active candidate if no naming convention match
        candidates = []
        for iface, data in stats.items():
            low = iface.lower()
            if low in ("lo", "loopback") or "docker" in low or "veth" in low or "virtual" in low:
                continue
            if data.bytes_sent > 0 or data.bytes_recv > 0:
                candidates.append(iface)
        
        if candidates:
            # Check the first candidate by its name
            first_iface_low = candidates[0].lower()
            if "eth" in first_iface_low or "lan" in first_iface_low:
                return "Ethernet"
            elif "wlan" in first_iface_low or "wifi" in first_iface_low:
                return "WiFi"
            else:
                # Can't determine type from name
                return None
        return None
    except Exception:
        return None
    
def calc_ul_dl(rate, dt=3, interface="Ethernet"): #WiFi
    t0 = time.time()
    counter = psutil.net_io_counters(pernic=True)[interface]
    tot = (counter.bytes_sent, counter.bytes_recv)

    while True:
        last_tot = tot
        time.sleep(dt)
        counter = psutil.net_io_counters(pernic=True)[interface]
        t1 = time.time()
        tot = (counter.bytes_sent, counter.bytes_recv)
        ul, dl = [
            (now - last) / (t1 - t0) / 1000.0
            for now, last in zip(tot, last_tot)
        ]
        rate.append((ul, dl))
        t0 = time.time()


def print_rate(rate):
    try:
        print("UL: {0:.0f} kB/s / DL: {1:.0f} kB/s".format(*rate[-1]))
    except IndexError:
        "UL: - kB/s/ DL: - kB/s"


# Create the ul/dl thread and a deque of length 1 to hold the ul/dl- values
transfer_rate = deque(maxlen=1)
t = threading.Thread(target=calc_ul_dl, args=(transfer_rate,))

# The program will exit if there are only daemonic threads left.
t.daemon = True
t.start()

# The rest of your program, emulated by me using a while True loop
while True:
    print(get_primary_interface())
    print_rate(transfer_rate)
    time.sleep(5)