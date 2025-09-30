import os
import sys
import time
import curses
import shutil
import platform
import subprocess
import monitor_core as core

# ==== Global settings ====
REFRESH_MS = 500

# ==== Helper functions ====
def ascii_bar(value, maxval, width=40, char="█"):
    """Return an ASCII progress bar."""
    if value is None:
        return "[ ? ]"
    if maxval == 0:
        return "[ 0 ]"
    filled = int((value / maxval) * width)
    return char * filled + "-" * (width - filled)

def get_usage_color(val):
    if val is None:
        return 4  # cyan for unknown
    if val < 60: 
        return 2  # green
    elif val < 80: 
        return 3  # yellow
    return 1  # red

# ==== Curses drawing loop ====
def draw_screen(stdscr):
    curses.curs_set(0)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLACK)

    while True:
        try:
            stdscr.clear()

            # === Collect All Stats ===
            cpu = core.get_cpu_usage()
            ram = core.get_ram_usage()
            gpu = core.get_gpu_usage()
            cpu_temp = core.get_cpu_temp()
            gpu_temp = core.get_gpu_temp()
            gpu_clock = core.get_gpu_clock_speed()
            freq = core.get_cpu_freq()
            read_mb, write_mb = core.get_disk_io()
            cpu_info = core.get_cpu_info()
            gpu_info = core.get_gpu_info()
            ram_info = core.get_ram_info()
            load_avg = core.get_load_average()
            disk_summary = core.get_disk_summary()
            
            # Network monitoring with auto-detected interface
            primary_interface = core.get_primary_interface()
            net_in, net_out, latency = core.net_usage_latency(interface=primary_interface, interval=0.1)

            # === CPU ===
            cpu_color = get_usage_color(cpu)
            freq_str = f"{freq[0]:.2f} GHz" if freq and freq[0] else "N/A"
            temp_str = f"{cpu_temp:.1f}°C" if cpu_temp else "N/A"
            
            stdscr.addstr(1, 2, f"CPU Usage: {cpu:.1f}% @ {freq_str} | Temp: {temp_str} | Load: {load_avg}", curses.color_pair(cpu_color))
            stdscr.addstr(2, 4, ascii_bar(cpu, 100))

            # === RAM ===
            ram_color = get_usage_color(ram)
            stdscr.addstr(4, 2, f"RAM: {ram:.1f}% (Used {ram_info['used']:.2f}GB / Free {ram_info['available']:.2f}GB)", curses.color_pair(ram_color))
            stdscr.addstr(5, 4, ascii_bar(ram, 100))

            # === GPU ===
            if gpu is not None:
                gpu_color = get_usage_color(gpu)
                gpu_temp_str = f"{gpu_temp:.1f}°C" if gpu_temp else "N/A"
                gpu_clock_str = f"{gpu_clock} MHz" if gpu_clock != "N/A" else "N/A"
                stdscr.addstr(7, 2, f"GPU Usage: {gpu:.1f}% | Clock: {gpu_clock_str} | Temp: {gpu_temp_str}", curses.color_pair(gpu_color))
                stdscr.addstr(8, 4, ascii_bar(gpu, 100))
            else:
                stdscr.addstr(7, 2, "GPU: Not detected", curses.color_pair(4))

            # === Storage ===
            stdscr.addstr(10, 2, f"Disk Usage: {disk_summary}", curses.color_pair(4))
            stdscr.addstr(11, 2, f"Disk I/O: Read {read_mb:.2f} MB/s | Write {write_mb:.2f} MB/s", curses.color_pair(4))
            stdscr.addstr(12, 4, ascii_bar(read_mb, 100))

            # === Network ===
            net_in_str = f"{net_in:.2f}" if net_in is not None else "N/A"
            net_out_str = f"{net_out:.2f}" if net_out is not None else "N/A"
            latency_str = f"{latency:.1f}ms" if latency is not None else "N/A"
            interface_str = primary_interface if primary_interface else "Auto"
            
            stdscr.addstr(14, 2, f"Network ({interface_str}): ↓{net_in_str} MB/s | ↑{net_out_str} MB/s | Ping: {latency_str}", curses.color_pair(4))
            if net_in is not None:
                stdscr.addstr(15, 4, ascii_bar(net_in, 10))  # Scale to 10 MB/s max

            # === Top Processes ===
            try:
                top_processes = core.get_top_processes(limit=3)
                stdscr.addstr(17, 2, "Top Processes:", curses.color_pair(3))
                stdscr.addstr(18, 4, "PID    USER     VIRT   RES    CPU%  MEM%  COMMAND", curses.color_pair(4))
                for i, proc in enumerate(top_processes):
                    if 19 + i < 22:  # Make sure we don't go past our display area
                        stdscr.addstr(19 + i, 4, proc[:70], curses.color_pair(6) if 'curses' in globals() else 0)
            except Exception:
                stdscr.addstr(17, 2, "Process info unavailable", curses.color_pair(1))

            # === System Info ===
            stdscr.addstr(23, 2, f"Time: {core.get_local_time()} | Uptime: {core.get_uptime()} | Date: {core.get_local_date()}", curses.color_pair(2))
            stdscr.addstr(24, 2, f"CPU: {cpu_info['model'][:50]}...", curses.color_pair(3))
            stdscr.addstr(25, 2, f"Cores: {cpu_info['physical_cores']}P/{cpu_info['logical_cores']}L", curses.color_pair(3))
            if gpu_info:
                stdscr.addstr(26, 2, f"GPU: {str(gpu_info)[:50]}...", curses.color_pair(3))

            stdscr.addstr(28, 2, "[CTRL+C to exit]", curses.color_pair(4))

            stdscr.refresh()
            time.sleep(REFRESH_MS / 1000)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            stdscr.addstr(0, 0, f"Error: {str(e)}", curses.color_pair(1))
            stdscr.refresh()
            time.sleep(1)

# ==== Launcher ====
def launch_new_terminal():
    script = os.path.abspath(__file__)
    system = platform.system()

    if system == "Windows":
        # Prefer the official Windows Python launcher
        python_cmd = shutil.which("py") or shutil.which("python") or "python"

        # Force open in Windows Terminal (wt.exe)
        subprocess.Popen([
            "wt.exe", "cmd.exe", "/k", f'{python_cmd} "{script}" --child'])


    elif system == "Linux":
        if shutil.which("gnome-terminal"):
            os.system(f'gnome-terminal -- python3 "{script}" --child')
        elif shutil.which("xterm"):
            os.system(f'xterm -e python3 "{script}" --child &')
        else:
            print("No compatible terminal emulator found.")
            sys.exit(1)
    elif system == "Darwin":
        os.system(f'osascript -e \'tell app "Terminal" to do script "python3 {script} --child"\'')
    else:
        print(f"Unsupported OS: {system}")
        sys.exit(1)

# ==== Entry point ====
if __name__ == "__main__":
    if "--child" not in sys.argv:
        launch_new_terminal()
        sys.exit()

    curses.wrapper(draw_screen)