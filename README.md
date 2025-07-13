# Spotify Playlist MP3 Downloader

This tool allows you to download songs from any public Spotify playlist as MP3 files by searching YouTube for high-quality audio, tagging them with metadata (for use in Serato and other DJ software), and saving them locally in a structured folder. Downloads run in parallel for efficiency, and a CSV tracklist is generated alongside properly tagged files.

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/spotify-mp3-downloader.git
cd spotify-mp3-downloader
````

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Authenticate with Spotify

Ensure you have a Spotify Developer App with a client ID and secret. The script will prompt you to log in with your Spotify account the first time you run it. Authentication is cached locally for future runs.

---

## Usage

To download a playlist:

```bash
python parallel_downloader.py
```

You’ll be prompted to enter a public Spotify playlist URL, such as:

```
https://open.spotify.com/playlist/390qR0tOcx0VekWOBX7RXP
```

Then, you'll be asked how many parallel downloads to run. Press Enter to use the recommended number of threads based on your CPU.

---

## Output

Each playlist is saved to:

```
Downloaded_Music/
└── <Playlist Name>/
    ├── Track 1.mp3
    ├── Track 2.mp3
    └── tracklist.csv
```

Each MP3 is:

* Named using the format `<Artist> - <Title>.mp3`
* Tagged with ID3 metadata (artist, title, album, year, genre)
* Validated to ensure it's playable and complete

---

## Notes

* YouTube is used as the source, and only non-remix, official-length tracks (between 90 and 600 seconds) are considered.
* Files that already exist will not be downloaded again.
* Corrupted or incomplete downloads are automatically removed before retrying.

---

## Requirements

* Python 3.8 or higher
* ffmpeg installed and available in system PATH
* Spotify Developer account credentials (only required for initial authentication)

---

## License

This script is intended for personal use. Be aware of and comply with YouTube’s terms of service when using this tool.


