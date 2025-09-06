import ttkbootstrap as tb
from ttkbootstrap.constants import *
from constants import FONT_TITLE, FONT_TAB_TITLE_COLOR, CRT_GREEN, PROGRESS_THICKNESS, GRAPH_HEIGHT

def build_metric_frame(parent, title, maxval=100, graph_height=GRAPH_HEIGHT, style=None):
    f = tb.Labelframe(parent, text=title, bootstyle=FONT_TAB_TITLE_COLOR)
    lbl = tb.Label(f, text=f"{title}: ...", anchor="w", font=FONT_TITLE, foreground=CRT_GREEN)
    lbl.pack(fill=X, padx=4, pady=(4,2))

    style_name = f"{title}.Horizontal.TProgressbar"
    if style:
        style.configure(style_name, troughcolor="black", background=CRT_GREEN, thickness=PROGRESS_THICKNESS)
    bar = tb.Progressbar(f, bootstyle="success", maximum=maxval, style=style_name)
    bar._style_name = style_name
    bar.pack(fill=X, padx=4, pady=(0,4))

    overlay_lbl = None
    if title == "RAM":
        overlay_lbl = tb.Label(f, text="", font=FONT_TITLE, foreground="black", background="black")
        overlay_lbl.place(in_=bar, relx=0.5, rely=0.5, anchor="center")

    cvs = tb.Canvas(f, height=graph_height, background="black", highlightthickness=0)
    cvs.pack(fill=BOTH, expand=True, padx=4, pady=4)
    return f, lbl, bar, cvs, overlay_lbl

def center_overlay_label(bar, overlay_lbl):
    if overlay_lbl:
        overlay_lbl.place_configure(in_=bar, relx=0.5, rely=0.5, anchor="center")