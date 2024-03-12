# DJ Music Library Manager

## Introduction
DJ Library Maager is tool designed to manage music libraries for DJs. It integrates with Spotify to fetch track data, downloads songs from YouTube, adds metadata to MP3 files, and maintains a SQLite database for easy management and retrieval of song information.

## Features
- Spotify Integration: Fetch track details using Spotify's robust API.
- YouTube Downloads: Download songs directly from YouTube.
- MP3 Tagging: Automate the tagging of MP3 files with metadata.
- Database Management: Use SQLite to manage song and playlist information.
- Album Art Management: Download and associate album art with songs.

## Installation

Before installation, ensure that Python 3 is installed on your system.

For Mac users, make sure you have ffmpeg installed to handle media files. You can install it using Homebrew with the command:
```
brew install ffmpeg
```
1. Clone the repository:
```
   git clone https://github.com/H-Bombmxpwr/dj-library.git
   cd dj-library
   ```

2. Install the required Python packages:
```
   pip install -r requirements.txt
   ```

3. Set up the environment variables by renaming [keys.env.example](keys.env.example) to keys.env and filling in your Spotify API credentials.

## Usage

Run the main.py script from the command line:

```
python main.py
```

When prompted, enter the Spotify URL or track name to begin fetching and organizing tracks. The script will handle the downloading, tagging, and database management.

