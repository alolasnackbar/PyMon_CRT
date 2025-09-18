import ttkbootstrap as tb
from ttkbootstrap.constants import *
from constants import FONT_TITLE, FONT_TAB_TITLE_COLOR, CRT_GREEN, PROGRESS_THICKNESS, GRAPH_HEIGHT

def build_metric_frame(parent, title, maxval=100, graph_height=GRAPH_HEIGHT, style=None):
    """
    Builds a standard metric frame (Label, Progressbar, Canvas) using the .grid() layout manager
    to ensure it's fully responsive.
    """
    f = tb.Labelframe(parent, text=title, bootstyle=FONT_TAB_TITLE_COLOR)
    
    # --- Grid Configuration ---
    # Configure the internal grid of this frame to be responsive.
    # Column 0 should expand horizontally (weight=1).
    f.columnconfigure(0, weight=1)
    # Row 2 (the canvas) should expand vertically (weight=1).
    f.rowconfigure(2, weight=1)

    # --- Widget Creation and Placement ---
    lbl = tb.Label(f, text=f"{title}: ...", anchor="w", font=FONT_TITLE, foreground=CRT_GREEN)
    # Place label in the first row, sticking to the left and right edges (ew).
    lbl.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))

    style_name = f"{title}.Horizontal.TProgressbar"
    if style:
        style.configure(style_name, troughcolor="black", background=CRT_GREEN, thickness=PROGRESS_THICKNESS)
    
    bar = tb.Progressbar(f, bootstyle="success", maximum=maxval, style=style_name)
    bar._style_name = style_name
    # Place progress bar in the second row, sticking to the left and right edges (ew).
    bar.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))

    overlay_lbl = None
    if title == "RAM":
        # .place() is still the correct choice for an overlay on a specific widget.
        overlay_lbl = tb.Label(f, text="", font=FONT_TITLE, foreground="black", background="black")
        overlay_lbl.place(in_=bar, relx=0.5, rely=0.5, anchor="center")

    cvs = tb.Canvas(f, height=graph_height, background="black", highlightthickness=0)
    # Place canvas in the third row. It should stick to all four sides (nsew)
    # of its grid cell, filling all available space.
    cvs.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
    
    return f, lbl, bar, cvs, overlay_lbl
