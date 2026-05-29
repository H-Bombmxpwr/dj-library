from pathlib import Path
from mutagen.easyid3 import EasyID3
from serato_crate import SeratoCrate
from tqdm import tqdm
import re
import os

# Constants
DOWNLOADED_MUSIC = Path("Downloaded_Music")
SERATO_CRATES = Path.home() / "Music" / "_Serato_" / "Subcrates"

def extract_decade(year_str):
    if year_str and re.match(r"^\d{4}$", year_str):
        return year_str[:3] + "0s"
    return None

def extract_year(year_str):
    if year_str and re.match(r"^\d{4}$", year_str):
        return year_str
    return None

def list_playlists():
    playlists = [p for p in DOWNLOADED_MUSIC.iterdir() if p.is_dir()]
    for i, playlist in enumerate(playlists, 1):
        print(f"{i}: {playlist.name}")
    return playlists

def select_playlists(playlists):
    selected = input("Enter playlist numbers separated by commas (e.g., 1,3,5): ")
    indices = [int(x.strip()) - 1 for x in selected.split(",") if x.strip().isdigit()]
    return [playlists[i] for i in indices if 0 <= i < len(playlists)]

def get_main_crate_name():
    return input("Enter the name of the main crate (e.g., Country): ").strip()

def to_drive_relative_path(path: Path):
    return Path(os.path.relpath(path.resolve(), "/"))

def choose_mode():
    mode = input("Subcrate by decade or year? Type 'decade' or 'year': ").strip().lower()
    return mode if mode in {"decade", "year"} else "decade"

def main():
    crate_root_name = get_main_crate_name()
    mode = choose_mode()

    print("\nAvailable Playlists:")
    playlists = list_playlists()
    selected_playlists = select_playlists(playlists)

    label_to_tracks = {}
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

                year = tags.get("date", [None])[0]
                label = extract_decade(year) if mode == "decade" else extract_year(year)
                if label:
                    label_to_tracks.setdefault(label, []).append(mp3)
            except Exception:
                continue

    for label, files in label_to_tracks.items():
        crate = SeratoCrate()
        for track in files:
            crate.tracks.append(to_drive_relative_path(track))
        crate_path = SERATO_CRATES / f"{label}.crate"
        crate_path.parent.mkdir(parents=True, exist_ok=True)
        crate.write(crate_path)

    parent_crate = SeratoCrate()
    parent_crate_path = SERATO_CRATES / f"{crate_root_name}.crate"
    parent_crate.write(parent_crate_path)

    print("✅ Crates generated and written to Serato directory.")

if __name__ == "__main__":
    main()
