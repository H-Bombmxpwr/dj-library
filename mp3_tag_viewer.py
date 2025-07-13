
#run this on an mp3 to see the metadata and what tags are on it

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, ID3NoHeaderError

file_path = "Downloaded_Music/POV you have aux but don't know what to play/50 Cent - In Da Club.mp3"

try:
    audio = MP3(file_path, ID3=ID3)
    print(f"Tags in {file_path}:")
    for tag in audio.tags.keys():
        print(f"{tag}: {audio.tags[tag]}")
except ID3NoHeaderError:
    print(f"No ID3 tags found in {file_path}")
