import os
import re
import csv
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from src.auth import authenticate_spotipy
from src.youtube import search_youtube_multiple, download_audio_from_url, is_valid_mp3
from spotipy.exceptions import SpotifyException
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TDRC, ID3NoHeaderError
from mutagen.mp3 import MP3

def clean_filename(name):
    name = re.sub(r'[\/*?:"<>|]', '', name)  # remove illegal characters
    name = re.sub(r'\s+', ' ', name).strip()  # normalize spaces
    name = os.path.splitext(name)[0]  # remove any extension
    return name

def normalize_mp3_extension(path):
    base, ext = os.path.splitext(path)
    while base.lower().endswith('.mp3'):
        base = os.path.splitext(base)[0]
    corrected_path = base + '.mp3'
    if corrected_path != path:
        os.rename(path, corrected_path)
        return corrected_path
    return path


def get_playlist_name(sp, playlist_id):
    playlist = sp.playlist(playlist_id)
    return playlist['name']

def get_playlist_tracks(sp, playlist_id):
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    while results:
        tracks.extend([item['track'] for item in results['items'] if item['track']])
        results = sp.next(results) if results['next'] else None
    return tracks

def tag_mp3(filepath, artist, title, album="", genre="", year=""):
    try:
        audio = MP3(filepath, ID3=ID3)
    except ID3NoHeaderError:
        audio = MP3(filepath)
        audio.add_tags()

    audio.tags.add(TPE1(encoding=3, text=[artist]))
    audio.tags.add(TIT2(encoding=3, text=[title]))
    if album:
        audio.tags.add(TALB(encoding=3, text=[album]))
    if genre:
        audio.tags.add(TCON(encoding=3, text=[genre]))
    if year:
        audio.tags.add(TDRC(encoding=3, text=[str(year)]))

    audio.save()
    print(f"🏷️ Tagged for Serato: {title} by {artist}")

def process_track(track, playlist_folder, writer_lock, writer):
    import time
    title = track['name']
    artist = track['artists'][0]['name']
    album = track.get('album', {}).get('name', '')
    year = track.get('album', {}).get('release_date', '')[:4]
    genre = ', '.join(track.get('artists', [])[0].get('genres', [])) if 'genres' in track['artists'][0] else ''

    search_query = f"{title} {artist} official audio"
    print(f"🔎 Searching: {search_query}")

    video_info = search_youtube_multiple(search_query)
    if not video_info:
        print(f"❌ No results found for {title} by {artist}")
        return

    yt_title = video_info['title']
    yt_url = video_info['webpage_url']

    base_filename = f"{artist} - {title}"
    safe_name = clean_filename(base_filename)
    expected_path = os.path.join(playlist_folder, safe_name + ".mp3")

    if os.path.exists(expected_path):
        print(f"✅ Already downloaded: {os.path.basename(expected_path)}")
        return

    print(f"⬇️ Downloading: {safe_name}.mp3 ({yt_title})")
    time_before = time.time()
    downloaded_path = download_audio_from_url(yt_url, os.path.join(playlist_folder, safe_name))

    # yt-dlp should now return path with .mp3 appended
    if downloaded_path and os.path.exists(downloaded_path):
        if not is_valid_mp3(downloaded_path):
            print(f"❌ Corrupted or invalid MP3 detected: {downloaded_path}")
            os.remove(downloaded_path)
            return
    else:
        # Fallback: check any new mp3s created after time_before
        mp3_files = [
            os.path.join(playlist_folder, f)
            for f in os.listdir(playlist_folder)
            if f.lower().endswith(".mp3") and os.path.getctime(os.path.join(playlist_folder, f)) >= time_before
        ]
        if mp3_files:
            downloaded_path = max(mp3_files, key=os.path.getctime)
            if not is_valid_mp3(downloaded_path):
                print(f"❌ Fallback file also invalid: {downloaded_path}")
                os.remove(downloaded_path)
                return
        else:
            print(f"⚠️ No file found after fallback for {title} by {artist}")
            return

    downloaded_path = normalize_mp3_extension(downloaded_path)
    tag_mp3(downloaded_path, artist, title, album, genre, year)

    with writer_lock:
        writer.writerow([artist, title, yt_url])

    print(f"✅ Downloaded and tagged: {os.path.basename(downloaded_path)}")



def download_playlist(sp, playlist_url):
    playlist_id = playlist_url.split("playlist/")[1].split("?")[0]
    playlist_name = clean_filename(get_playlist_name(sp, playlist_id))
    base_folder = os.path.join(os.getcwd(), "Downloaded_Music")
    playlist_folder = os.path.join(base_folder, playlist_name)
    os.makedirs(playlist_folder, exist_ok=True)

    csv_path = os.path.join(playlist_folder, 'tracklist.csv')
    writer_lock = multiprocessing.Lock()

    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Artist', 'Title', 'YouTube URL'])

        tracks = get_playlist_tracks(sp, playlist_id)
        print(f"🎵 Found {len(tracks)} tracks in playlist: {playlist_name}")

        core_count = multiprocessing.cpu_count()
        suggested_workers = min(10, core_count * 2)
        try:
            max_workers = int(input(f"\n🧐 Detected {core_count} CPU cores. Suggested max threads: {suggested_workers}\nHow many downloads should run in parallel? [Press Enter for suggested]: ") or suggested_workers)
        except ValueError:
            max_workers = suggested_workers

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(process_track, track, playlist_folder, writer_lock, writer)
                for track in tracks
            ]
            for _ in tqdm(as_completed(futures), total=len(futures), desc="📅 Downloading"):
                pass

if __name__ == "__main__":
    sp = authenticate_spotipy()
    url = input("Enter Spotify playlist URL: ").strip()
    try:
        download_playlist(sp, url)
    except SpotifyException as e:
        print(f"❌ Spotify API error: {e}")
    except Exception as e:
        print(f"❌ General error: {e}")