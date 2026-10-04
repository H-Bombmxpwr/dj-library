"""Download, loudness-normalize and encode audio.

YouTube serves Opus/AAC, so every track has to be decoded and encoded to MP3
exactly once no matter what. Loudness normalization is folded into that one
encode as a plain linear gain (``volume`` filter, 32-bit float), so it adds
no extra generation loss, no compression and no limiting - the waveform is
just scaled. The gain is capped so the true peak never exceeds -1 dBTP,
meaning normalization can never introduce clipping. Output is 320 kbps CBR,
the highest MP3 quality and the format every DJ app/CDJ handles best.
"""
import glob
import os
import re
import shutil
import subprocess

import yt_dlp

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_TARGET_LUFS = -14.0
TRUE_PEAK_CEILING = -1.0
BITRATE = "320k"


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    bundled = os.path.join(PROJECT_DIR, "ffmpeg", "bin", "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if os.path.exists(bundled):
        return bundled
    raise RuntimeError("FFmpeg not found. Install it (brew install ffmpeg) or add it to PATH.")


FFMPEG = find_ffmpeg()


def download(url, dest_stem):
    """Download the best audio-only stream. Returns the downloaded file path."""
    opts = {
        "format": "bestaudio[acodec=opus]/bestaudio/best",
        "outtmpl": dest_stem + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "ffmpeg_location": os.path.dirname(FFMPEG),
        "cachedir": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
    if not os.path.exists(path):
        found = [p for p in glob.glob(glob.escape(dest_stem) + ".*") if not p.endswith(".part")]
        if not found:
            raise RuntimeError("yt-dlp finished but no file was written")
        path = found[0]
    return path


def measure(path):
    """Return (integrated_lufs, true_peak_dbtp, duration_seconds) via EBU R128."""
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0",
           "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"]
    out = subprocess.run(cmd, capture_output=True, text=True, errors="replace").stderr
    summary = out[out.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    dur = re.findall(r"time=(\d+):(\d+):([\d.]+)", out)
    lufs = float(i.group(1)) if i and i.group(1) != "-inf" else None
    peak = float(tp.group(1)) if tp and tp.group(1) != "-inf" else None
    seconds = None
    if dur:
        h, m, s = dur[-1]
        seconds = int(h) * 3600 + int(m) * 60 + float(s)
    return lufs, peak, seconds


def compute_gain(lufs, peak, target=DEFAULT_TARGET_LUFS):
    if lufs is None:
        return 0.0
    gain = target - lufs
    if peak is not None:
        gain = min(gain, TRUE_PEAK_CEILING - peak)
    return round(gain, 2)


def encode_mp3(src, dest, gain_db=0.0):
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", src,
           "-map", "0:a:0", "-vn", "-map_metadata", "-1"]
    if abs(gain_db) >= 0.01:
        cmd += ["-af", f"volume={gain_db}dB"]
    cmd += ["-c:a", "libmp3lame", "-b:a", BITRATE, "-id3v2_version", "3", "-write_xing", "1", dest]
    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if result.returncode != 0 or not os.path.exists(dest):
        raise RuntimeError(f"ffmpeg encode failed: {result.stderr.strip()[-300:]}")
