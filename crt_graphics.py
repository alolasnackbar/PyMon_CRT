from constants import CRT_GREEN, CRT_GRID, MAX_POINTS, CRT_LINE_SMOT

def draw_crt_grid(canvas, x_offset=0):
    w, h = canvas.winfo_width(), canvas.winfo_height()
    if w < 10 or h < 10: return
    grid_spacing = max(1, w // 10)
    for x in range(-grid_spacing, w, grid_spacing):
        canvas.create_line(x + x_offset, 0, x + x_offset, h, fill=CRT_GRID)
    for y in range(0, h, max(1, h // 5)):
        canvas.create_line(0, y, w, y, fill=CRT_GRID)

def draw_crt_line(canvas, data, max_value, line_color, width=2):
    """Draw CRT line from right to left, always full length."""
    w, h = canvas.winfo_width(), canvas.winfo_height()
    if w < 10 or h < 10: return

    # Ensure line always has MAX_POINTS length
    plot_data = ([0] * (MAX_POINTS - len(data))) + data[-MAX_POINTS:]
    
    step = w / MAX_POINTS
    pts = [(w - i*step, h - (val / max(1e-6, max_value)) * h) for i, val in enumerate(reversed(plot_data))]
    flat_pts = [coord for pt in pts for coord in pt]
    canvas.create_line(*flat_pts, fill=line_color, width=width, smooth=True, splinesteps=CRT_LINE_SMOT)

def draw_filled_area(canvas, data, max_value, fill_color):
    """Filled CRT area, right-to-left, always full length, fill sticks to line start/end."""
    w, h = canvas.winfo_width(), canvas.winfo_height()
    if w < 10 or h < 10:
        return

    # Pre-fill with zeros if data is short
    plot_data = ([0] * (MAX_POINTS - len(data))) + data[-MAX_POINTS:]
    
    step = w / MAX_POINTS
    # Right-to-left points for the top of the area
    pts = [(w - i*step, h - (val / max(1e-6, max_value)) * h) for i, val in enumerate(reversed(plot_data))]

    if not pts:
        return

    # Instead of anchoring at canvas bottom, anchor at first/last line points
    start_y = pts[0][1]
    end_y = pts[-1][1]
    # Create polygon: start at rightmost line point, go along line, then down to end_y, back along bottom, then up to start_y
    poly_pts = [(pts[0][0], start_y)] + pts + [(pts[-1][0], end_y)] + list(reversed([(pt[0], h) for pt in pts]))  # keep bottom flat but matched
    flat_pts = [coord for pt in poly_pts for coord in pt]
    canvas.create_polygon(*flat_pts, fill=fill_color, outline="", smooth=True, splinesteps=CRT_LINE_SMOT)

    # Fill colors for read/write
    read_fill = "#224422"  # dark green
    write_fill = "#808080"  # dark blue/purple

def draw_dual_io(canvas, read_hist, write_hist, frame_count):
    """Draw read/write I/O lines with proper fills under each line, no spillover."""
    from constants import CRT_GREEN, CRT_LINE_SMOT
    canvas.delete("all")

    w, h = canvas.winfo_width(), canvas.winfo_height()
    if w < 10 or h < 10:
        return

    # Scrolling CRT grid
    grid_spacing = max(1, w // 10)
    x_offset = -(frame_count * 3) % grid_spacing
    draw_crt_grid(canvas, x_offset)

    max_io = max(read_hist + write_hist + [1])
    step = w / MAX_POINTS

    # Pad data to always have MAX_POINTS
    read_data = ([0] * (MAX_POINTS - len(read_hist))) + read_hist[-MAX_POINTS:]
    write_data = ([0] * (MAX_POINTS - len(write_hist))) + write_hist[-MAX_POINTS:]

    # Build points left-to-right
    read_pts = [(i * step, h - (val / max_io) * h) for i, val in enumerate(read_data)]
    write_pts = [(i * step, h - (val / max_io) * h) for i, val in enumerate(write_data)]

    def draw_filled(pts, fill_color):
        if not pts:
            return
        start_y = pts[0][1]
        end_y = pts[-1][1]
        # polygon follows line, anchored at start/end y
        poly_pts = [(pts[0][0], start_y)] + pts + [(pts[-1][0], end_y)] + list(reversed([(pt[0], h) for pt in pts]))
        flat_pts = [coord for pt in poly_pts for coord in pt]
        canvas.create_polygon(*flat_pts, fill=fill_color, outline="", smooth=True, splinesteps=CRT_LINE_SMOT)

    # Draw fills
    draw_filled(read_pts, "#224422")   # green for read
    draw_filled(write_pts, "#808080")  # purple/gray for write

    # Draw lines on top
    canvas.create_line([coord for pt in read_pts for coord in pt], fill=CRT_GREEN, width=2, smooth=True, splinesteps=CRT_LINE_SMOT)
    canvas.create_line([coord for pt in write_pts for coord in pt], fill="white", width=2, smooth=True, splinesteps=CRT_LINE_SMOT)


def draw_metric(canvas, series, max_value, color, frame_count):
    """Draw single metric line with filled area, always present."""
    canvas.delete("all")
    w = canvas.winfo_width()
    grid_spacing = max(1, w // 10)
    x_offset = -(frame_count * 3) % grid_spacing
    draw_crt_grid(canvas, x_offset)

    # Choose faded fill color
    if color == CRT_GREEN:
        fill_color = "#224422"  # faded green
    elif color == "white":
        fill_color = "#888888"
    else:
        fill_color = "#444444"

    draw_filled_area(canvas, series, max_value, fill_color)
    draw_crt_line(canvas, series, max_value, color)
