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
    w, h = canvas.winfo_width(), canvas.winfo_height()
    if len(data) < 2 or w < 10 or h < 10: return
    step = w / MAX_POINTS
    pts = [(i * step, h - (val / max(1e-6, max_value)) * h) for i, val in enumerate(data)]
    flat_pts = [coord for pt in pts for coord in pt]
    canvas.create_line(*flat_pts, fill=line_color, width=width, smooth=True, splinesteps=CRT_LINE_SMOT)

def draw_dual_io(canvas, read_hist, write_hist, frame_count):
    from constants import CRT_GREEN
    canvas.delete("all")
    w = canvas.winfo_width()
    grid_spacing = max(1, w // 10)
    x_offset = -(frame_count * 3) % grid_spacing
    draw_crt_grid(canvas, x_offset)
    max_io = max(read_hist + write_hist + [1])
    draw_crt_line(canvas, read_hist, max_io, CRT_GREEN)
    draw_crt_line(canvas, write_hist, max_io, "white")

def draw_metric(canvas, series, max_value, color, frame_count):
    canvas.delete("all")
    w = canvas.winfo_width()
    grid_spacing = max(1, w // 10)
    x_offset = -(frame_count * 3) % grid_spacing
    draw_crt_grid(canvas, x_offset)
    draw_crt_line(canvas, series, max_value, color)