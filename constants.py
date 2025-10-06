# --- Widget ---
MAX_POINTS = 60
REFRESH_MS = 1000
DISK_IO_MAX_MBPS = 500
GRAPH_HEIGHT = 90
PROGRESS_THICKNESS = 24
CRT_LINE_SMOT = 69

# Color schemes for color blind mode
CRT_GREEN = "#00FF66"
CRT_YELLOW = "#FFFF00"
CRT_RED = "#FF4444"
CRT_GRID  = "#024D02"
CRT_CYAN = "#04AD97"

COLORBLIND_COLORS = {
    'success': '#0173B2',   # Blue
    'warning': '#DE8F05',   # Orange  
    'danger': '#CC78BC',    # Pink
    'info': '#029E73'       # Teal
}

NORMAL_COLORS = {
    'success': CRT_GREEN,
    'warning': CRT_YELLOW, 
    'danger': CRT_RED,
    'info': CRT_CYAN
}

# Color scheme for detection status
STATUS_COLORS = {
    'default': CRT_RED,      # Red: Default/undetected
    'detected': CRT_GREEN,   # Green: Values detected
    'missing': CRT_YELLOW,   # Yellow: Not supported/null values
    'loading': CRT_CYAN      # Cyan: Currently testing
}

# --- Font styling ---
FONT_TITLE = ("Consolas", 14, "bold")
FONT_SYSTIME = ("Consolas", 55, "bold")
FONT_INFOTXT = ("Consolas", 11, "bold")
FONT_NETTXT = ("Consolas", 17, "bold")

FONT_TAB_TITLE_COLOR = "success"
FONT_OVERLAY = ('Helvetica', 12)
FONT_INFO = ("Consolas")

# --- Constants & Globals ---
REFRESH_GUI_MS = 100
REFRESH_HEAVY_MS = REFRESH_MS * 5
REFRESH_SLOW_MS = REFRESH_MS * 2

NETWORK_INTERFACE = None
PING_HOST = "8.8.8.8"
PING_COUNT = 3

# Configuration defaults
DEFAULT_CONFIG = {
    "monitor_index": 3,
    "process_count": 5,
    "cycle_enabled": False,
    "cycle_delay": 5,
    "focus_enabled": True,
    "cpu_threshold": 80,
    "temp_threshold": 75,
    "latency_threshold": 200,
    "colorblind_mode": False
}