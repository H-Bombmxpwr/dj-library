import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADER = os.path.join(PROJECT_DIR, "parallel_downloader.py")
LIBRARY_DIR = os.path.join(PROJECT_DIR, "Downloaded_Music")

COLORS = {
    "bg": "#1e142f",           # midnight purple
    "panel": "#271a3f",        # session card
    "fg": "#dcd6f7",           # lilac white
    "muted": "#9d93c2",
    "accent": "#a29bfe",       # soft purple
    "highlight": "#8c7ae6",    # medium purple
    "danger": "#e17055",       # coral for stop
    "ok": "#55efc4",
    "warn": "#fdcb6e",
    "entry_bg": "#2c1d4a",     # deeper background
    "console_bg": "#2f2b41",
    "console_fg": "#f8f8f2",
}
CPU = os.cpu_count() or 4
SUGGESTED_THREADS = min(8, CPU * 2)
MAX_THREADS = max(16, CPU * 2)


def setup_styles(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("custom.Horizontal.TProgressbar", troughcolor=COLORS["entry_bg"],
                    background=COLORS["accent"], bordercolor=COLORS["entry_bg"],
                    lightcolor=COLORS["accent"], darkcolor=COLORS["accent"], thickness=10)
    for name, color, active in (("Purple", COLORS["highlight"], COLORS["accent"]),
                                ("Danger", COLORS["danger"], "#fab1a0")):
        style.configure(f"{name}.TButton", background=color, foreground="white",
                        padding=(10, 5), relief="flat", borderwidth=0, focuscolor=color)
        style.map(f"{name}.TButton", background=[("disabled", "#444"), ("active", active)],
                  foreground=[("disabled", "#999")])
    style.configure("TCheckbutton", background=COLORS["panel"], foreground=COLORS["fg"])
    style.map("TCheckbutton", background=[("active", COLORS["panel"])],
              indicatorcolor=[("selected", COLORS["accent"]), ("!selected", COLORS["entry_bg"])])
    style.configure("TSpinbox", fieldbackground=COLORS["entry_bg"], foreground=COLORS["fg"],
                    background=COLORS["highlight"], arrowcolor="white", bordercolor=COLORS["entry_bg"])
    style.configure("Vertical.TScrollbar", background=COLORS["highlight"], troughcolor=COLORS["console_bg"],
                    bordercolor=COLORS["console_bg"], arrowcolor="white")


def open_path(path):
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif os.name == "nt":
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path])


def fmt_duration(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}m {seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


class DownloaderSession(tk.Frame):
    def __init__(self, master, number, on_remove):
        super().__init__(master, bg=COLORS["panel"], highlightthickness=1,
                         highlightbackground=COLORS["highlight"])
        self.number = number
        self.on_remove = on_remove
        self.process = None
        self.lines = queue.Queue()
        self.folder = None
        self.started_at = None
        self.build_ui()
        self.poll_output()

    # ---------- UI ----------
    def label(self, parent, text="", **kw):
        kw.setdefault("fg", COLORS["fg"])
        return tk.Label(parent, text=text, bg=COLORS["panel"], **kw)

    def build_ui(self):
        pad = {"padx": 12}

        header = tk.Frame(self, bg=COLORS["panel"])
        header.pack(fill="x", pady=(10, 6), **pad)
        self.title_label = self.label(header, f"Session {self.number}", font=("Helvetica", 14, "bold"))
        self.title_label.pack(side="left")
        self.status_label = self.label(header, "● Idle", fg=COLORS["muted"])
        self.status_label.pack(side="right")

        url_row = tk.Frame(self, bg=COLORS["panel"])
        url_row.pack(fill="x", **pad)
        self.url_entry = tk.Entry(url_row, bg=COLORS["entry_bg"], fg=COLORS["fg"], relief="flat",
                                  insertbackground=COLORS["fg"], highlightthickness=1,
                                  highlightbackground=COLORS["entry_bg"], highlightcolor=COLORS["accent"])
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.url_entry.bind("<Return>", lambda _: self.start_download())
        self.paste_btn = ttk.Button(url_row, text="Paste", style="Purple.TButton", command=self.paste_url)
        self.paste_btn.pack(side="left", padx=(6, 0))
        self.label(self, "Spotify playlist, album or track link (several links separated by spaces are queued)",
                   fg=COLORS["muted"], font=("Helvetica", 10)).pack(anchor="w", **pad)

        opts = tk.Frame(self, bg=COLORS["panel"])
        opts.pack(fill="x", pady=(8, 0), **pad)
        self.label(opts, "Parallel downloads").pack(side="left")
        self.threads_var = tk.StringVar(value=str(SUGGESTED_THREADS))
        self.threads_spin = ttk.Spinbox(opts, from_=1, to=MAX_THREADS, width=4, textvariable=self.threads_var)
        self.threads_spin.pack(side="left", padx=(6, 16))
        self.normalize_var = tk.BooleanVar(value=True)
        self.normalize_chk = ttk.Checkbutton(opts, text="Normalize to", variable=self.normalize_var,
                                             command=self.toggle_lufs)
        self.normalize_chk.pack(side="left")
        self.lufs_var = tk.StringVar(value="-14")
        self.lufs_spin = ttk.Spinbox(opts, from_=-23, to=-8, increment=1, width=4, textvariable=self.lufs_var)
        self.lufs_spin.pack(side="left", padx=(4, 2))
        self.label(opts, "LUFS").pack(side="left", padx=(0, 16))
        self.lyrics_var = tk.BooleanVar(value=True)
        self.lyrics_chk = ttk.Checkbutton(opts, text="Embed lyrics", variable=self.lyrics_var)
        self.lyrics_chk.pack(side="left")

        btns = tk.Frame(self, bg=COLORS["panel"])
        btns.pack(fill="x", pady=10, **pad)
        self.start_btn = ttk.Button(btns, text="▶ Start", style="Purple.TButton", command=self.start_download)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(btns, text="■ Stop", style="Danger.TButton", command=self.stop_download)
        self.stop_btn.pack(side="left", padx=6)
        self.stop_btn.state(["disabled"])
        self.folder_btn = ttk.Button(btns, text="Open Folder", style="Purple.TButton", command=self.open_folder)
        self.folder_btn.pack(side="left")
        self.folder_btn.state(["disabled"])
        self.remove_btn = ttk.Button(btns, text="Remove", style="Purple.TButton", command=self.remove)
        self.remove_btn.pack(side="right")
        ttk.Button(btns, text="Clear Log", style="Purple.TButton", command=self.clear_log).pack(side="right", padx=6)

        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(self, variable=self.progress_var, maximum=100,
                        style="custom.Horizontal.TProgressbar").pack(fill="x", **pad)
        self.stats_label = self.label(self, "", fg=COLORS["muted"], anchor="w")
        self.stats_label.pack(fill="x", pady=(2, 4), **pad)

        console_frame = tk.Frame(self, bg=COLORS["console_bg"])
        console_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.console = tk.Text(console_frame, height=12, bg=COLORS["console_bg"], fg=COLORS["console_fg"],
                               relief="flat", wrap="word", font=("Menlo", 11), padx=8, pady=6,
                               state="disabled", highlightthickness=0)
        scroll = ttk.Scrollbar(console_frame, orient="vertical", command=self.console.yview)
        self.console.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.console.pack(side="left", fill="both", expand=True)
        self.console.tag_configure("ok", foreground=COLORS["ok"])
        self.console.tag_configure("error", foreground=COLORS["danger"])
        self.console.tag_configure("warn", foreground=COLORS["warn"])
        self.console.tag_configure("info", foreground=COLORS["accent"])

    def toggle_lufs(self):
        self.lufs_spin.state(["!disabled"] if self.normalize_var.get() else ["disabled"])

    def paste_url(self):
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            return
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, text)

    def write(self, text, tag=None):
        at_bottom = self.console.yview()[1] > 0.98
        self.console.configure(state="normal")
        self.console.insert(tk.END, text, tag)
        self.console.configure(state="disabled")
        if at_bottom:
            self.console.see(tk.END)

    def clear_log(self):
        self.console.configure(state="normal")
        self.console.delete("1.0", tk.END)
        self.console.configure(state="disabled")

    def set_status(self, text, color):
        self.status_label.configure(text=f"● {text}", fg=color)

    def set_running(self, running):
        for w in (self.start_btn, self.paste_btn, self.threads_spin, self.normalize_chk, self.lyrics_chk):
            w.state(["disabled"] if running else ["!disabled"])
        self.url_entry.configure(state="disabled" if running else "normal")
        self.stop_btn.state(["!disabled"] if running else ["disabled"])
        self.lufs_spin.state(["disabled"] if running or not self.normalize_var.get() else ["!disabled"])
        self.master.event_generate("<<SessionsChanged>>")

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    # ---------- process handling ----------
    def start_download(self):
        if self.running:
            return
        urls = self.url_entry.get().split()
        if not urls:
            messagebox.showerror("Missing link", "Paste a Spotify playlist, album or track link first.")
            return
        try:
            threads = max(1, min(MAX_THREADS, int(self.threads_var.get())))
            lufs = float(self.lufs_var.get())
        except ValueError:
            messagebox.showerror("Invalid settings", "Threads and LUFS must be numbers.")
            return

        cmd = [sys.executable, "-u", DOWNLOADER, *urls, "--gui", "-t", str(threads)]
        if self.normalize_var.get():
            cmd += ["--target-lufs", str(lufs)]
        else:
            cmd.append("--no-normalize")
        if not self.lyrics_var.get():
            cmd.append("--no-lyrics")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        kwargs = {"start_new_session": True} if os.name != "nt" else \
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}

        self.progress_var.set(0)
        self.stats_label.configure(text="Fetching playlist from Spotify...")
        self.started_at = time.time()
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                        errors="replace", cwd=PROJECT_DIR, env=env, **kwargs)
        self.set_running(True)
        self.set_status("Running", COLORS["accent"])
        self.write(f"\n▶ Starting {len(urls)} link(s) with {threads} parallel downloads\n", "info")

        proc = self.process

        def reader():
            for line in proc.stdout:
                self.lines.put(line)
            proc.wait()
            self.lines.put(None)

        threading.Thread(target=reader, daemon=True).start()

    def stop_download(self):
        if not self.running:
            return
        proc = self.process
        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(proc.pid, signal.SIGTERM)  # also stops ffmpeg children
        except (ProcessLookupError, OSError):
            proc.terminate()
        self.after(3000, lambda: proc.poll() is None and proc.kill())
        self.write("\n⏹ Stopped by user. Finished tracks are kept; partial files are discarded.\n", "warn")
        self.set_status("Stopped", COLORS["warn"])

    def poll_output(self):
        try:
            while True:
                line = self.lines.get_nowait()
                if line is None:
                    self.on_finished()
                else:
                    self.handle_line(line)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100, self.poll_output)

    def handle_line(self, line):
        if line.startswith("@@"):
            try:
                self.handle_event(json.loads(line[2:]))
            except json.JSONDecodeError:
                pass
            return
        tag = None
        if "✅" in line or "🏁" in line:
            tag = "ok"
        elif "❌" in line or "Traceback" in line or "Error" in line:
            tag = "error"
        elif "⚠️" in line:
            tag = "warn"
        elif line.startswith(("🎵", "🔗")):
            tag = "info"
        self.write(line, tag)

    def handle_event(self, ev):
        kind = ev.get("event")
        if kind == "start":
            self.folder = ev["folder"]
            self.folder_btn.state(["!disabled"])
            name = ev["playlist"]
            self.title_label.configure(text=name if len(name) <= 40 else name[:38] + "…")
            self.started_at = time.time()
            self.total, self.existing = ev["total"], ev["existing"]
            todo = self.total - self.existing
            self.progress_var.set(0 if todo else 100)
            self.stats_label.configure(text=f"{self.existing} already in library • {todo} to download")
        elif kind == "progress":
            done, total = ev["done"], ev["total"]
            self.progress_var.set(done / total * 100 if total else 100)
            elapsed = time.time() - self.started_at
            eta = elapsed / done * (total - done) if done else 0
            parts = [f"{done}/{total}", f"{ev['downloaded']} new"]
            if ev["failed"]:
                parts.append(f"{ev['failed']} failed")
            parts.append(f"{self.existing} already had")
            if done < total:
                parts.append(f"ETA {fmt_duration(eta)}")
            self.stats_label.configure(text="  •  ".join(parts))
        elif kind == "done":
            failed = f", {ev['failed']} failed" if ev["failed"] else ""
            self.stats_label.configure(
                text=f"Done: {ev['downloaded']} new, {ev['existing']} already had{failed}  •  "
                     f"{fmt_duration(time.time() - self.started_at)}")
            self.progress_var.set(100)

    def on_finished(self):
        code = self.process.returncode if self.process else 0
        self.process = None
        self.set_running(False)
        if self.status_label.cget("text").endswith("Stopped"):
            return
        if code == 0:
            self.set_status("Done", COLORS["ok"])
            self.bell()
        else:
            self.set_status("Finished with errors", COLORS["danger"])

    def open_folder(self):
        if self.folder and os.path.isdir(self.folder):
            open_path(self.folder)

    def remove(self):
        if self.running:
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
        self.minsize(720, 480)
        setup_styles(self)

        self.sessions = []
        self.session_counter = 0

        control = tk.Frame(self, bg=COLORS["bg"])
        control.pack(pady=(12, 0), padx=20, fill=tk.X)
        tk.Label(control, text="DJ Library Downloader", bg=COLORS["bg"], fg=COLORS["fg"],
                 font=("Helvetica", 18, "bold")).pack(side=tk.LEFT)
        ttk.Button(control, text="Open Library", style="Purple.TButton",
                   command=self.open_library).pack(side=tk.RIGHT)
        self.add_btn = ttk.Button(control, text="+ New Session", style="Purple.TButton",
                                  command=self.add_new_session)
        self.add_btn.pack(side=tk.RIGHT, padx=8)

        self.session_frame = tk.Frame(self, bg=COLORS["bg"])
        self.session_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.session_frame.bind("<<SessionsChanged>>", lambda _: self.update_removal_states())
        for c in range(self.COLS):
            self.session_frame.columnconfigure(c, weight=1, uniform="col")

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.add_new_session()
        self.geometry("1280x560")

    def open_library(self):
        os.makedirs(LIBRARY_DIR, exist_ok=True)
        open_path(LIBRARY_DIR)

    def add_new_session(self):
        if len(self.sessions) >= self.MAX_SESSIONS:
            messagebox.showwarning("Limit Reached", f"Only {self.MAX_SESSIONS} simultaneous sessions allowed.")
            return
        self.session_counter += 1
        session = DownloaderSession(self.session_frame, self.session_counter, self.remove_session)
        self.sessions.append(session)
        self.refresh_layout()
        rows = (len(self.sessions) + self.COLS - 1) // self.COLS
        if self.winfo_height() < 520 * rows:
            self.geometry(f"{max(self.winfo_width(), 1280)}x{min(520 * rows + 60, self.winfo_screenheight() - 80)}")
        session.url_entry.focus_set()

    def remove_session(self, session):
        if session in self.sessions:
            session.destroy()
            self.sessions.remove(session)
            self.refresh_layout()

    def refresh_layout(self):
        for widget in self.session_frame.winfo_children():
            widget.grid_forget()
        rows = (len(self.sessions) + self.COLS - 1) // self.COLS
        for r in range(self.MAX_SESSIONS // self.COLS):
            self.session_frame.rowconfigure(r, weight=1 if r < rows else 0)
        for idx, session in enumerate(self.sessions):
            session.grid(row=idx // self.COLS, column=idx % self.COLS, padx=8, pady=8, sticky="nsew")
        self.add_btn.state(["disabled"] if len(self.sessions) >= self.MAX_SESSIONS else ["!disabled"])
        self.update_removal_states()

    def update_removal_states(self):
        for session in self.sessions:
            if len(self.sessions) <= 1 or session.running:
                session.remove_btn.state(["disabled"])
            else:
                session.remove_btn.state(["!disabled"])

    def on_close(self):
        running = [s for s in self.sessions if s.running]
        if running and not messagebox.askyesno(
                "Downloads running", f"{len(running)} session(s) still downloading. Stop them and quit?"):
            return
        for s in running:
            s.stop_download()
        self.destroy()


if __name__ == "__main__":
    app = DownloaderGUI()
    app.mainloop()
