import tkinter as tk
from tkinter import ttk
import monitor_core as core

def update_stats():
    cpu = core.get_cpu_usage()
    gpu = core.get_gpu_usage()
    temp = core.get_temp()
    ram = core.get_ram_usage()
    disk = core.get_disk_usage()

    cpu_label.config(text=f"CPU Usage: {cpu:.1f}%")
    gpu_label.config(text=f"GPU Usage: {gpu:.1f}%" if gpu else "GPU Usage: N/A")
    temp_label.config(text=f"Temperature: {temp}")
    ram_label.config(text=f"RAM Usage: {ram:.1f}%")
    disk_label.config(text=f"Disk Usage: {disk:.1f}%")

    root.after(2000, update_stats)  # refresh every 2s

# ==== GUI ====
root = tk.Tk()
root.title("System Monitor")
root.geometry("500x500")

cpu_label = ttk.Label(root, text="CPU Usage: ...")
cpu_label.pack(padx=10, pady=5)

gpu_label = ttk.Label(root, text="GPU Usage: ...")
gpu_label.pack(padx=10, pady=5)

temp_label = ttk.Label(root, text="Temperature: ...")
temp_label.pack(padx=10, pady=5)

ram_label = ttk.Label(root, text="RAM Usage: ...")
ram_label.pack(padx=10, pady=5)

disk_label = ttk.Label(root, text="Disk Usage: ...")
disk_label.pack(padx=10, pady=5)

update_stats()
root.mainloop()
