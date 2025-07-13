import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import re
import multiprocessing

COLORS = {
    "bg": "#1e142f",           # midnight purple
    "fg": "#dcd6f7",           # lilac white
    "accent": "#a29bfe",       # soft purple
    "highlight": "#8c7ae6",    # medium purple
    "danger": "#e17055",       # coral for stop
    "entry_bg": "#2c1d4a",     # deeper background
    "console_bg": "#2f2b41",
    "console_fg": "#f8f8f2"
}


class DownloaderSession(tk.Frame):
    def __init__(self, master, core_info, on_remove):
        super().__init__(master, bg=COLORS["bg"], bd=2, relief=tk.RIDGE)
        self.master = master
        self.core_info = core_info
        self.on_remove = on_remove
        self.process = None

        self.build_ui()

    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("custom.Horizontal.TProgressbar",
            troughcolor=COLORS["entry_bg"],
            background=COLORS["accent"],
            bordercolor=COLORS["entry_bg"],
            lightcolor=COLORS["accent"],
            darkcolor=COLORS["accent"])

        style.configure("Purple.TButton",
            background=COLORS["highlight"],
            foreground="white",
            padding=6,
            relief="flat")

        style.map("Purple.TButton",
            background=[("active", COLORS["accent"]), ("disabled", "#444")],
            foreground=[("disabled", "#ccc")])

        tk.Label(self, text="Spotify Playlist URL:", bg=COLORS["bg"], fg=COLORS["fg"]).pack(pady=(10, 2))
        self.url_entry = tk.Entry(self, width=50, bg=COLORS["entry_bg"], fg=COLORS["fg"], insertbackground=COLORS["fg"])
        self.url_entry.pack(pady=(0, 10))

        tk.Label(self, text=f"Parallel Downloads (suggested: {self.core_info['suggested']}, max: {self.core_info['max']}):",
                bg=COLORS["bg"], fg=COLORS["fg"]).pack()
        self.thread_entry = tk.Entry(self, width=10, bg=COLORS["entry_bg"], fg=COLORS["fg"], insertbackground=COLORS["fg"])
        self.thread_entry.insert(0, str(self.core_info['suggested']))
        self.thread_entry.pack(pady=(0, 10))

        self.btn_frame = tk.Frame(self, bg=COLORS["bg"])
        self.btn_frame.pack(pady=(0, 10))

        self.start_btn = ttk.Button(self.btn_frame, text="Start Download", style="Purple.TButton", command=self.start_download)
        self.start_btn.grid(row=0, column=0, padx=5)

        self.stop_btn = ttk.Button(self.btn_frame, text="Stop", style="Purple.TButton", command=self.stop_download)
        self.stop_btn.grid(row=0, column=1, padx=5)

        self.remove_btn = ttk.Button(self.btn_frame, text="Remove", style="Purple.TButton", command=self.remove)
        self.remove_btn.grid(row=0, column=2, padx=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self, variable=self.progress_var, maximum=100, style="custom.Horizontal.TProgressbar")
        self.progress_bar.pack(fill='x', padx=10, pady=(0, 5))

        self.console = tk.Text(self, height=10, width=70, bg=COLORS["console_bg"], fg=COLORS["console_fg"])
        self.console.pack(padx=10, pady=(0, 10))

    def set_playlist_title(self, name):
        self.master.master.title(f"DJ Library Downloader - {name}")

    
    def start_download(self):
        url = self.url_entry.get().strip()
        threads = self.thread_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a Spotify playlist URL.")
            return

        self.remove_btn.state(["disabled"])
        self.progress_var.set(0)

        command = ["python", "parallel_downloader.py"]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        def run():
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True, env=env)
            self.process.stdin.write(url + "\n")
            self.process.stdin.write((threads or "") + "\n")
            self.process.stdin.flush()

            for line in self.process.stdout:
                self.console.insert(tk.END, line)
                self.console.see(tk.END)

                match = re.search(r'(\d+)%\|', line)
                if match:
                    percent = int(match.group(1))
                    self.progress_var.set(percent)

            self.process.wait()
            self.progress_var.set(100)
            self.process = None
            self.remove_btn.state(["!disabled"])

        threading.Thread(target=run, daemon=True).start()

    def stop_download(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.console.insert(tk.END, "\n❌ Download process terminated by user.\n")
            self.console.see(tk.END)
            self.process = None
            self.remove_btn.state(["!disabled"])

    def remove(self):
        if self.process and self.process.poll() is None:
            messagebox.showinfo("Cannot Remove", "Session is currently running. Please stop it first.")
            return
        self.on_remove(self)


class DownloaderGUI(tk.Tk):
    MAX_SESSIONS = 6
    COLS = 2

    def __init__(self):
        super().__init__()
        self.title("DJ Library Downloader")
        self.configure(bg=COLORS["bg"])

        self.core_info = self.get_core_info()
        self.sessions = []

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Purple.TButton", background=COLORS["highlight"], foreground="white", padding=6, relief="flat")
        style.map("Purple.TButton", background=[("active", COLORS["accent"]), ("disabled", "#444")], foreground=[("disabled", "#ccc")])

        self.control_frame = tk.Frame(self, bg=COLORS["bg"])
        self.control_frame.pack(pady=(10, 0), fill=tk.X)

        self.add_btn = ttk.Button(self.control_frame, text="New Download Session", style="Purple.TButton", command=self.add_new_session)
        self.add_btn.pack(side=tk.LEFT, padx=10)

        self.close_btn = ttk.Button(self.control_frame, text="Close GUI", style="Purple.TButton", command=self.quit)
        self.close_btn.pack(side=tk.LEFT, padx=10)

        self.session_frame = tk.Frame(self, bg=COLORS["bg"])
        self.session_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.update_geometry()
        self.add_new_session()

    def get_core_info(self):
        total = multiprocessing.cpu_count()
        suggested = min(10, total * 2)
        return {"total": total, "suggested": suggested, "max": total * 2}

    def update_geometry(self):
        rows = (len(self.sessions) + self.COLS - 1) // self.COLS
        height = 350 * rows
        self.geometry(f"1200x{height}")

    def add_new_session(self):
        if len(self.sessions) >= self.MAX_SESSIONS:
            messagebox.showwarning("Limit Reached", f"Only {self.MAX_SESSIONS} simultaneous sessions allowed.")
            return

        session = DownloaderSession(self.session_frame, self.core_info, self.remove_session)
        row = len(self.sessions) // self.COLS
        col = len(self.sessions) % self.COLS
        session.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        self.sessions.append(session)
        self.update_geometry()
        self.update_removal_states()

    def remove_session(self, session):
        if session in self.sessions:
            session.destroy()
            self.sessions.remove(session)
            self.refresh_layout()
            self.update_removal_states()

    def refresh_layout(self):
        for widget in self.session_frame.winfo_children():
            widget.grid_forget()

        for idx, session in enumerate(self.sessions):
            row = idx // self.COLS
            col = idx % self.COLS
            session.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        self.update_geometry()

    def update_removal_states(self):
        for session in self.sessions:
            if len(self.sessions) <= 1 or (session.process and session.process.poll() is None):
                session.remove_btn.state(["disabled"])
            else:
                session.remove_btn.state(["!disabled"])


if __name__ == "__main__":
    app = DownloaderGUI()
    app.mainloop()