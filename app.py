import customtkinter as ctk
import subprocess
import threading
import os
import json
from tkinter import filedialog

# -------------------------
# App setup
# -------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Docker Sandbox Executor")
app.geometry("800x600")

# -------------------------
# State
# -------------------------
cpu_var = ctk.StringVar(value="0.5")
mem_var = ctk.StringVar(value="256")
pids_var = ctk.StringVar(value="64")
network_var = ctk.BooleanVar(value=False)
handler_var = ctk.StringVar()

code_file = {"path": None}
input_file = {"path": None}

# -------------------------
# Output helper
# -------------------------
def append_output(text):
    output_box.configure(state="normal")
    output_box.insert("end", text + "\n")
    output_box.see("end")
    output_box.configure(state="disabled")

# -------------------------
# File selectors
# -------------------------
def select_code_file():
    path = filedialog.askopenfilename(
        filetypes=[("Python files", "*.py")]
    )
    if path:
        code_file["path"] = path
        code_label.configure(text=path)

def select_input_file():
    path = filedialog.askopenfilename(
        filetypes=[("JSON files", "*.json")]
    )
    if path:
        input_file["path"] = path
        input_label.configure(text=path)

# -------------------------
# Validation
# -------------------------
def validate_inputs():
    if not handler_var.get():
        return "Handler path is required (e.g. main.handler)"

    if "." not in handler_var.get():
        return "Handler must be in module.function format"

    if not code_file["path"] or not os.path.isfile(code_file["path"]):
        return "Valid Python code file not selected"

    if not input_file["path"] or not os.path.isfile(input_file["path"]):
        return "Valid JSON input file not selected"

    if not code_file["path"].endswith(".py"):
        return "Code file must be .py"

    if not input_file["path"].endswith(".json"):
        return "Input file must be .json"

    if os.path.getsize(input_file["path"]) > 1_000_000:
        return "Input JSON too large (>1MB)"

    try:
        with open(input_file["path"]) as f:
            json.load(f)
    except Exception:
        return "Invalid JSON file"

    return None

# -------------------------
# Docker runner (thread)
# -------------------------
def run_docker():
    output_box.configure(state="normal")
    output_box.delete("1.0", "end")
    output_box.configure(state="disabled")

    error = validate_inputs()
    if error:
        append_output(f"❌ {error}")
        return

    cmd = [
        "docker", "run", "--rm",
        "--cpus", cpu_var.get(),
        "--memory", f"{mem_var.get()}m",
        "--memory-swap", f"{mem_var.get()}m",
        "--pids-limit", pids_var.get(),
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--read-only",
        "--tmpfs", "/tmp:rw,size=64m",
    ]

    if not network_var.get():
        cmd += ["--network", "none"]

    cmd += [
        "-v", f"{code_file['path']}:/function/main.py:ro",
        "-v", f"{input_file['path']}:/input/input.json:ro",
        "-v", f"{os.path.abspath('user_runner.py')}:/function/user_runner.py:ro",
        "python:3.11-slim",
        "python",
        "/function/user_runner.py",
        handler_var.get(),
        "/input/input.json"
    ]

    append_output("> " + " ".join(cmd))

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    for line in process.stdout:
        app.after(0, append_output, line.rstrip())

    for line in process.stderr:
        app.after(0, append_output, "ERR: " + line.rstrip())

    code = process.wait()
    app.after(0, append_output, f"\n[Exit code: {code}]")

# -------------------------
# Start execution
# -------------------------
def start_execution():
    threading.Thread(target=run_docker, daemon=True).start()

# -------------------------
# Layout
# -------------------------
ctk.CTkLabel(app, text="Docker Sandbox Executor", font=("Arial", 20)).pack(pady=10)

form = ctk.CTkFrame(app)
form.pack(pady=10)

ctk.CTkLabel(form, text="Handler (module.function)").grid(row=0, column=0, padx=5, pady=5)
ctk.CTkEntry(form, textvariable=handler_var, width=250).grid(row=0, column=1)

ctk.CTkLabel(form, text="CPU").grid(row=1, column=0)
ctk.CTkEntry(form, textvariable=cpu_var, width=80).grid(row=1, column=1, sticky="w")

ctk.CTkLabel(form, text="Memory (MB)").grid(row=2, column=0)
ctk.CTkEntry(form, textvariable=mem_var, width=80).grid(row=2, column=1, sticky="w")

ctk.CTkLabel(form, text="PIDs").grid(row=3, column=0)
ctk.CTkEntry(form, textvariable=pids_var, width=80).grid(row=3, column=1, sticky="w")

ctk.CTkCheckBox(app, text="Enable Network", variable=network_var).pack()

ctk.CTkButton(app, text="Select Code File", command=select_code_file).pack(pady=5)
code_label = ctk.CTkLabel(app, text="No code file selected", wraplength=700)
code_label.pack()

ctk.CTkButton(app, text="Select Input JSON", command=select_input_file).pack(pady=5)
input_label = ctk.CTkLabel(app, text="No input file selected", wraplength=700)
input_label.pack()

ctk.CTkButton(app, text="Run Container", command=start_execution).pack(pady=15)

output_box = ctk.CTkTextbox(app, width=750, height=250)
output_box.pack(pady=10)
output_box.configure(state="disabled")

app.mainloop()
