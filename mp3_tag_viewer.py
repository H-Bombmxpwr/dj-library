"""Print the ID3 tags on one or more MP3 files.

    uv run mp3_tag_viewer.py "Downloaded_Music/<Playlist>/<Artist - Title>.mp3"
"""
import sys

from mutagen.mp3 import MP3


def show(path):
    audio = MP3(path)
    print(f"\n{path}")
    print(f"  {audio.info.bitrate // 1000} kbps, {audio.info.sample_rate} Hz, {audio.info.length:.1f}s")
    if not audio.tags:
        print("  (no ID3 tags)")
        return
    for key, frame in sorted(audio.tags.items()):
        if key.startswith("APIC"):
            value = f"<{frame.mime}, {len(frame.data) // 1024} KB>"
        else:
            value = str(frame).replace("\n", " / ")
        print(f"  {key:32} {value[:100]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        show(p)
