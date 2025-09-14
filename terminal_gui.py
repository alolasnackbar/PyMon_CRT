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
    filled = int((value / maxval) * width)
    return char * filled + "-" * (width - filled)

def get_usage_color(val):
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

    while True:
        stdscr.clear()

        # === Collect Stats ===
        cpu = core.get_cpu_usage()
        ram = core.get_ram_usage()
        gpu = core.get_gpu_usage()
        freq = core.get_cpu_freq()
        read_mb, write_mb = core.get_disk_io(interval=0.2)
        cpu_info = core.get_cpu_info()
        gpu_info = core.get_gpu_info()

        # === CPU ===
        cpu_color = get_usage_color(cpu)
        freq_ghz = freq if freq else 0
        stdscr.addstr(1, 2, f"CPU Usage: {cpu}%  @ {freq_ghz} GHz", curses.color_pair(cpu_color))
        stdscr.addstr(2, 4, ascii_bar(cpu, 100))

        # === RAM ===
        ram_color = get_usage_color(ram)
        ram_info = core.get_ram_info()
        stdscr.addstr(4, 2, f"RAM: {ram:.1f}% (Used {ram_info['used']}GB / Free {ram_info['available']}GB)", curses.color_pair(ram_color))
        stdscr.addstr(5, 4, ascii_bar(ram, 100))

        # === GPU ===
        gpu_color = get_usage_color(gpu)
        stdscr.addstr(7, 2, f"GPU Usage: {gpu:.1f}%", curses.color_pair(gpu_color))
        stdscr.addstr(8, 4, ascii_bar(gpu, 100))

        # === Disk I/O ===
        stdscr.addstr(10, 2, f"Disk Read: {read_mb:.2f} MB/s", curses.color_pair(4))
        stdscr.addstr(11, 4, ascii_bar(read_mb, 500))
        stdscr.addstr(12, 2, f"Disk Write: {write_mb:.2f} MB/s", curses.color_pair(4))
        stdscr.addstr(13, 4, ascii_bar(write_mb, 500))

        # === System Info ===
        stdscr.addstr(15, 2, f"Time: {core.get_local_time()}", curses.color_pair(2))
        stdscr.addstr(16, 2, f"Uptime: {core.get_uptime()}", curses.color_pair(2))
        stdscr.addstr(18, 2, f"CPU Model: {cpu_info['model']}", curses.color_pair(3))
        stdscr.addstr(19, 2, f"{cpu_info['physical_cores']} CORES | {cpu_info['logical_cores']} THREADS", curses.color_pair(3))
        stdscr.addstr(20, 2, f"GPU: {gpu_info}", curses.color_pair(3))

        stdscr.addstr(curses.LINES - 1, 2, "[CTRL+C to exit]", curses.color_pair(4))

        stdscr.refresh()
        time.sleep(REFRESH_MS / 1000)

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

