# DJ Library Downloader (GUI Version)

A modern, parallelized Spotify playlist downloader built for DJs. Instead of using a command-line interface, this version provides an intuitive GUI to:

* Paste a public Spotify playlist link
* Download each track by locating its official audio on YouTube
* Convert to `.mp3`, tag it with metadata (artist, title, album, year, genre)
* Save and organize tracks by playlist
* Run multiple sessions in parallel with live progress

---

## How It Works

* `dj_gui.py` opens a GUI window.
* Each session downloads a playlist and displays live console output and a progress bar.
* Multiple sessions can be run simultaneously (up to 6 by default).
* Tracks are saved in a structured format with Serato/Traktor-compatible tags.

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/spotify-mp3-downloader.git
cd spotify-mp3-downloader
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Spotify API Setup

This tool fetches playlist data via the Spotify Web API.

### Steps:

1. Visit [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
2. Create an app and copy:

   * `Client ID`
   * `Client Secret`

### Create `.env` file:

```bash
cp keys.env.example .env
```

Paste your credentials inside:

```
SPOTIPY_CLIENT_ID='your_client_id'
SPOTIPY_CLIENT_SECRET='your_client_secret'
```

---

## FFmpeg Installation

Required by `yt-dlp` to convert YouTube videos to MP3.

### macOS:

```bash
brew install ffmpeg
```

### Windows:

* Download from: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
* Extract it to `C:\ffmpeg\`
* Add `C:\ffmpeg\bin` to your System Environment Variables → `Path`

### Linux:

```bash
sudo apt update && sudo apt install ffmpeg
```

---

## Running the GUI

From the project root:

```bash
python dj_gui.py
```

The GUI allows you to:

* Paste in a Spotify playlist link
* Choose number of parallel download threads (or use the default)
* Monitor download logs and progress
* Add or remove sessions
* Run up to 6 sessions simultaneously

Each session runs in its own subprocess and will not interfere with the others. The GUI prevents session removal while a download is active.

---

## Output Structure

Downloaded songs are stored under:

```
Downloaded_Music/
└── <Playlist Name>/
    ├── Artist - Title.mp3
    ├── ...
    └── tracklist.csv
```

Each MP3 includes tags for `artist`, `title`, `album`, `year`, and `genre`, making the files compatible with Serato and other DJ software.

---

## Limitations

* Requires internet access to access Spotify metadata and download from YouTube.
* Public playlists only (no support for private playlists).
* Search-based download means the quality of the match depends on YouTube search accuracy.
* The GUI requires Python 3.8+ and `tkinter` (installed with most Python distributions by default).

---

## MP3 Tag Viewer

Use `mp3_tag_viewer.py` to view existing tags on any MP3. Set the file path in the script to inspect your file:

```python
file_path = 'path/to/your/file.mp3'
```

---

## License

This project is intended for personal, non-commercial use. Be mindful of Spotify and YouTube terms of service when using this tool.
