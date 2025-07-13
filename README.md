# Spotify Playlist MP3 Downloader

This script downloads all songs from a public Spotify playlist by searching YouTube for each track's official audio, downloading it as an MP3, tagging it with metadata (compatible with Serato and other DJ software), and saving them locally. All downloads are validated and run in parallel for speed.

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

---

## 4. Set Up Spotify API Authentication

To access Spotify's playlist data, you need to authenticate via the Spotify Web API.

#### Step-by-step:

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2. Log in and click "Create an App".
3. Copy your **Client ID** and **Client Secret**.

#### Create a `.env` file:

Copy the example file:

```bash
cp keys.env.example .env
```

Then edit `.env` to contain your credentials:

```
SPOTIPY_CLIENT_ID='your_client_id_here'
SPOTIPY_CLIENT_SECRET='your_client_secret_here'
```

These values are loaded automatically by the script using `python-dotenv`.

---

## 5. Install FFmpeg

FFmpeg is required by `yt-dlp` to extract audio from YouTube videos into MP3.

### macOS (using Homebrew):

```bash
brew install ffmpeg
```

### Windows:

* Download FFmpeg from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html).
* Extract the ZIP and place it in a folder (e.g., `C:\ffmpeg\`).
* Add `C:\ffmpeg\bin` to your system PATH:

  * Search for "Environment Variables"
  * Under "System variables", find `Path`, click Edit, and add `C:\ffmpeg\bin`.

### Linux:

```bash
sudo apt update && sudo apt install ffmpeg
```

To confirm it's working:

```bash
ffmpeg -version
```

The script uses FFmpeg via `yt-dlp` for converting downloaded audio into `.mp3` format.

---

## Usage

Run the script:

```bash
python parallel_downloader.py
```

Paste in a Spotify playlist URL when prompted:

```
https://open.spotify.com/playlist/390qR0tOcx0VekWOBX7RXP
```

Then enter the number of parallel download threads (or press Enter to auto-select).

---

## Output

Each playlist is saved to:

```
Downloaded_Music/
└── <Playlist Name>/
    ├── Artist - Title.mp3
    ├── ...
    └── tracklist.csv
```

Each `.mp3` is:

* Named `<Artist> - <Title>.mp3`
* Tagged with artist, title, album, year, and genre
* Verified to be valid before moving to the next song

---

## Requirements

* Python 3.8+
* Spotify Developer credentials in `.env`
* FFmpeg installed and added to system PATH

---

## License

For personal use only. Respect YouTube's and Spotify's terms of service when using this tool.

