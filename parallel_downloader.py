"""Download Spotify playlists/albums/tracks as tagged, loudness-normalized MP3s.

    python parallel_downloader.py <spotify url> [<url> ...] [-t 8] [--target-lufs -14]

Run with no URL to be prompted for one.
"""
import argparse
import csv
import json
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from spotipy.exceptions import SpotifyException

from src import audio, matcher, spotify, tagging

OUTPUT_DIR = os.path.join(spotify.PROJECT_DIR, "Downloaded_Music")
PARTIAL_DIR = ".partial"
CSV_FIELDS = ["Artist", "Title", "Album", "Status", "Source", "YouTube URL", "Spotify URL",
              "Original LUFS", "Gain dB"]

_print_lock = threading.Lock()
GUI_MODE = False


def log(msg):
    with _print_lock:
        print(msg, flush=True)


def event(kind, **data):
    """Machine-readable line for the GUI (hidden from its console)."""
    if GUI_MODE:
        log("@@" + json.dumps({"event": kind, **data}))


def suggested_threads():
    return min(8, (os.cpu_count() or 4) * 2)


def clean_filename(name):
    name = re.sub(r'[\/*?:"<>|]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'\.(mp3|wav|flac|aac|ogg|m4a)$', '', name, flags=re.IGNORECASE)
    return name or "Untitled"


def process_track(track, folder, opts):
    """Download one track. Returns a result dict for the tracklist CSV."""
    name = clean_filename(f"{track.artist} - {track.title}")
    final_path = os.path.join(folder, name + ".mp3")
    result = {"name": name, "status": "failed", "source": "", "url": "", "lufs": "", "gain": ""}

    match = matcher.find_best(track)
    if not match:
        result["status"] = "not found"
        return result
    result.update(source=match.source, url=match.url)

    stem = os.path.join(folder, PARTIAL_DIR, track.id)
    tmp_mp3 = stem + ".tmp.mp3"
    src = None
    try:
        src = audio.download(match.url, stem)
        gain = 0.0
        loudness = None
        if opts.normalize:
            lufs, peak, seconds = audio.measure(src)
            gain = audio.compute_gain(lufs, peak, opts.target_lufs)
            if lufs is not None:
                loudness = (lufs, gain)
                result.update(lufs=f"{lufs:.1f}", gain=f"{gain:+.1f}")
            if seconds and track.duration and abs(seconds - track.duration) > 15:
                log(f"⚠️  Length differs from Spotify by {abs(seconds - track.duration):.0f}s: {name}")
        audio.encode_mp3(src, tmp_mp3, gain)
        lyrics = tagging.fetch_lyrics(track) if opts.lyrics else ""
        tagging.tag_mp3(tmp_mp3, track, match.url, lyrics, loudness)
        os.replace(tmp_mp3, final_path)  # atomic: never leaves a half-written MP3
        result["status"] = "downloaded"
    except Exception as e:
        result["error"] = str(e).splitlines()[0][:200] if str(e) else type(e).__name__
    finally:
        for path in (src, tmp_mp3):
            if path and os.path.exists(path):
                os.remove(path)
    return result


def _read_previous_csv(path):
    rows = {}
    if os.path.exists(path):
        try:
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    rows[(row.get("Artist"), row.get("Title"))] = row
        except (OSError, csv.Error):
            pass
    return rows


def _write_csv(path, tracks, results):
    previous = _read_previous_csv(path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for t in tracks:
            r = results.get(t.id, {})
            old = previous.get((t.artist, t.title), {})
            status = r.get("status", "")
            writer.writerow({
                "Artist": t.artist, "Title": t.title, "Album": t.album,
                "Status": status if status != "exists" else (old.get("Status") or "downloaded"),
                "Source": r.get("source") or old.get("Source", ""),
                "YouTube URL": r.get("url") or old.get("YouTube URL", ""),
                "Spotify URL": t.url,
                "Original LUFS": r.get("lufs") or old.get("Original LUFS", ""),
                "Gain dB": r.get("gain") or old.get("Gain dB", ""),
            })
        # Keep rows for tracks downloaded earlier that aren't in this link (e.g. Singles)
        current = {(t.artist, t.title) for t in tracks}
        for key, row in previous.items():
            if key not in current:
                writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})


def download_collection(sp, url, opts):
    log("🔗 Reading Spotify link...")
    name, tracks = spotify.fetch(sp, url)
    folder_name = clean_filename(name)
    folder = os.path.join(opts.output, folder_name)
    partial = os.path.join(folder, PARTIAL_DIR)
    shutil.rmtree(partial, ignore_errors=True)  # leftovers from a stopped run
    os.makedirs(partial, exist_ok=True)

    # Skip files that already exist and duplicate entries before doing any network work
    results, todo, seen = {}, [], set()
    for t in tracks:
        fname = clean_filename(f"{t.artist} - {t.title}")
        if fname.lower() in seen:
            results[t.id] = {"status": "duplicate"}
            continue
        seen.add(fname.lower())
        if os.path.exists(os.path.join(folder, fname + ".mp3")):
            results[t.id] = {"status": "exists"}
        else:
            todo.append(t)

    existing = len(tracks) - len(todo)
    log(f"🎵 {name}: {len(tracks)} tracks ({existing} already in library, {len(todo)} to download)")
    event("start", playlist=name, folder=folder, total=len(tracks), existing=existing)

    counts = {"downloaded": 0, "failed": 0}
    started = time.time()
    try:
        with ThreadPoolExecutor(max_workers=max(1, opts.threads)) as pool:
            futures = {pool.submit(process_track, t, folder, opts): t for t in todo}
            for done, future in enumerate(as_completed(futures), 1):
                t = futures[future]
                try:
                    r = future.result()
                except Exception as e:
                    r = {"name": f"{t.artist} - {t.title}", "status": "failed", "error": str(e)}
                results[t.id] = r
                prefix = f"[{done}/{len(todo)}]"
                if r["status"] == "downloaded":
                    counts["downloaded"] += 1
                    gain = f", {r['gain']} dB" if r.get("gain") else ""
                    log(f"{prefix} ✅ {r['name']}  ({r['source']}{gain})")
                elif r["status"] == "not found":
                    counts["failed"] += 1
                    log(f"{prefix} ❌ No clean match found: {r['name']}")
                else:
                    counts["failed"] += 1
                    log(f"{prefix} ❌ Failed: {r['name']} - {r.get('error', 'unknown error')}")
                event("progress", done=done, total=len(todo), **counts)
    finally:
        _write_csv(os.path.join(folder, "tracklist.csv"), tracks, results)
        shutil.rmtree(partial, ignore_errors=True)

    elapsed = time.time() - started
    log(f"🏁 {name}: {counts['downloaded']} downloaded, {existing} already had, "
        f"{counts['failed']} failed in {elapsed:.0f}s")
    failed = [r["name"] for r in results.values() if r.get("status") in ("failed", "not found")]
    if failed:
        log("   Not downloaded:\n   - " + "\n   - ".join(failed))
    event("done", **counts, existing=existing)


def main():
    global GUI_MODE
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("urls", nargs="*", help="Spotify playlist, album or track links")
    parser.add_argument("-t", "--threads", type=int, default=suggested_threads(),
                        help=f"parallel downloads (default {suggested_threads()})")
    parser.add_argument("--target-lufs", type=float, default=audio.DEFAULT_TARGET_LUFS,
                        help=f"loudness target (default {audio.DEFAULT_TARGET_LUFS})")
    parser.add_argument("--no-normalize", dest="normalize", action="store_false",
                        help="keep original loudness")
    parser.add_argument("--no-lyrics", dest="lyrics", action="store_false", help="skip embedding lyrics")
    parser.add_argument("-o", "--output", default=OUTPUT_DIR, help="output folder")
    parser.add_argument("--gui", action="store_true", help=argparse.SUPPRESS)
    opts = parser.parse_args()
    GUI_MODE = opts.gui

    urls = opts.urls or input("Enter Spotify playlist/album/track URL: ").split()
    sp = spotify.authenticate()
    exit_code = 0
    for url in urls:
        try:
            download_collection(sp, url, opts)
        except SpotifyException as e:
            log(f"❌ Spotify API error for {url}: {e.msg if hasattr(e, 'msg') else e}")
            exit_code = 1
        except ValueError as e:
            log(f"❌ {e}")
            exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n⏹️  Stopped.")
        sys.exit(130)
