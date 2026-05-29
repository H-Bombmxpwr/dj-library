from pathlib import Path
from mutagen.easyid3 import EasyID3
from serato_crate import SeratoCrate
from tqdm import tqdm
import os

# Constants
DOWNLOADED_MUSIC = Path("Downloaded_Music")
SERATO_CRATES = Path.home() / "Music" / "_Serato_" / "Subcrates"

def get_main_crate_name():
    return input("Enter the name of the main crate (e.g., BPM_Sorted): ").strip()

def choose_bpm_interval():
    choice = input("Sort BPM by 10 or 20 BPM increments? Enter 10 or 20: ").strip()
    return 10 if choice == "10" else 20

def get_bpm_bucket(bpm, interval):
    try:
        bpm = float(bpm)
        start = int(bpm // interval * interval)
        end = start + interval
        return f"{start}-{end}"
    except:
        return "No BPM"

def to_drive_relative_path(path: Path):
    return Path(os.path.relpath(path.resolve(), "/"))

def list_playlists():
    playlists = [p for p in DOWNLOADED_MUSIC.iterdir() if p.is_dir()]
    for i, playlist in enumerate(playlists, 1):
        print(f"{i}: {playlist.name}")
    return playlists

def select_playlists(playlists):
    selected = input("Enter playlist numbers separated by commas (e.g., 1,3,5): ")
    indices = [int(x.strip()) - 1 for x in selected.split(",") if x.strip().isdigit()]
    return [playlists[i] for i in indices if 0 <= i < len(playlists)]

def main():
    crate_root_name = get_main_crate_name()
    interval = choose_bpm_interval()

    print("\nAvailable Playlists:")
    playlists = list_playlists()
    selected_playlists = select_playlists(playlists)

    bpm_to_tracks = {}
    seen = set()

    for playlist in selected_playlists:
        mp3s = list(playlist.rglob("*.mp3"))
        for mp3 in tqdm(mp3s, desc=f"Scanning {playlist.name}", leave=False):
            try:
                tags = EasyID3(mp3)
                title = tags.get("title", [""])[0]
                artist = tags.get("artist", [""])[0]
                uid = f"{title.lower()}::{artist.lower()}"
                if uid in seen:
                    continue
                seen.add(uid)

                bpm = tags.get("bpm", [None])[0]
                bucket = get_bpm_bucket(bpm, interval)
                bpm_to_tracks.setdefault(bucket, []).append(mp3)
            except Exception:
                bpm_to_tracks.setdefault("No BPM", []).append(mp3)

    for bucket, files in bpm_to_tracks.items():
        crate = SeratoCrate()
        for track in files:
            crate.tracks.append(to_drive_relative_path(track))
        crate_path = SERATO_CRATES / f"{bucket}.crate"
        crate_path.parent.mkdir(parents=True, exist_ok=True)
        crate.write(crate_path)

    parent_crate = SeratoCrate()
    parent_crate_path = SERATO_CRATES / f"{crate_root_name}.crate"
    parent_crate.write(parent_crate_path)

    print("✅ BPM crates generated and saved to Serato directory.")

if __name__ == "__main__":
    main()
