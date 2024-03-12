import os
import json
import re
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from pytube import YouTube
from moviepy.editor import AudioFileClip
from youtube_search import YoutubeSearch

def authenticate_spotipy():
    load_dotenv('keys.env')
    client_id = os.getenv('SPOTIPY_CLIENT_ID')
    client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')
    credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(client_credentials_manager=credentials_manager)
    return sp

def get_song_release_date(sp, song_name):
    results = sp.search(q=song_name, limit=1, type='track')
    track_info = results['tracks']['items'][0]
    album_id = track_info['album']['id']
    album = sp.album(album_id)
    return album['release_date'], track_info['name'], track_info['artists'][0]['name']

def download_and_convert_song(sp):
    song_input = input("Enter the song name or YouTube URL: ")
    youtube = None
    song_name = artist_name = ""

    if not os.path.exists('audio'):
        os.makedirs('audio')

    # Use Spotify to get accurate release date if possible
    release_date, song_name, artist_name = None, None, None
    if "https://www.youtube.com" not in song_input:
        release_date, song_name, artist_name = get_song_release_date(sp, song_input)

    # If a direct YouTube URL is provided, process it
    if "https://www.youtube.com" in song_input:
        youtube = YouTube(song_input)
        video_title = youtube.title

    # If no release date was found via Spotify, use the YouTube video's publish date
    if not release_date:
        if youtube:
            release_date = youtube.publish_date.strftime("%Y-%m-%d")
        else:
            print("Could not find release date information.")
            return

    year, month = release_date[:4], release_date[5:7]
    custom_directory_path = f'audio/{year}/{month}'
    if not os.path.exists(custom_directory_path):
        os.makedirs(custom_directory_path)

    if not song_name or not artist_name:
        # Extract song name and artist from YouTube video title as a fallback
        if youtube:
            # This is a naive extraction assuming the title is in "Song - Artist" format
            song_name, artist_name = video_title.split(' - ') if ' - ' in video_title else (video_title, 'Unknown')

    safe_song_name = re.sub(r'[^\w\s-]', '', song_name).replace(" ", "_")
    safe_artist_name = re.sub(r'[^\w\s-]', '', artist_name).replace(" ", "_")
    custom_filename = f"{safe_song_name}_by_{safe_artist_name}.mp3"

    try:
        # Ensure the YouTube object is available before proceeding to download
        if not youtube:
            yt_search = YoutubeSearch(song_input, max_results=1).to_json()
            yt_data = json.loads(yt_search)
            if not yt_data['videos']:
                print("Song not found on YouTube.")
                return
            song_id = yt_data['videos'][0]['id']
            youtube = YouTube(f"https://www.youtube.com/watch?v={song_id}")

        # Download the audio stream at the highest quality
        audio_stream = youtube.streams.get_audio_only()
        audio_stream.download(output_path=custom_directory_path, filename=custom_filename.replace(".mp3", ".mp4"))

        # Convert MP4 to MP3
        mp4_path = os.path.join(custom_directory_path, custom_filename.replace(".mp3", ".mp4"))
        mp3_path = os.path.join(custom_directory_path, custom_filename)

        audioclip = AudioFileClip(mp4_path)
        audioclip.write_audiofile(mp3_path)

        # Optional: Remove the original MP4 file
        audioclip.close()
        os.remove(mp4_path)

        print(f"Download and conversion complete. File saved as {mp3_path}")
    except Exception as e:
        print(f"There was an error processing your request: {e}")

if __name__ == "__main__":
    sp = authenticate_spotipy()
    download_and_convert_song(sp)
