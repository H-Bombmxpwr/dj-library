from mutagen.id3 import ID3, TIT2, TPE1, TYER, TCON, TBPM, APIC, ID3NoHeaderError
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import sqlite3
import os
import requests
import re
from youtube_search import YoutubeSearch
import json
import pytube
from pytube import YouTube
from moviepy.editor import AudioFileClip

load_dotenv('keys.env')


def authenticate_spotipy():
    client_id = os.getenv('SPOTIPY_CLIENT_ID')
    client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')
    credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(client_credentials_manager=credentials_manager)
    return sp


def get_spotify_data(sp, search_query):
    # Check if the input is a Spotify URI
    if search_query.startswith('spotify:track:'):
        track_id = search_query.split(':')[2]
        track = sp.track(track_id)
    else:
        # Perform a search query if it's not a URI
        result = sp.search(q=search_query, limit=1, type='track')
        if not result['tracks']['items']:
            return None
        track = result['tracks']['items'][0]
   

    # Get additional track details using the track ID
    track_id = track['id']
    track_details = sp.track(track_id)

    # Get detailed audio features for the track
    audio_features = sp.audio_features(track_id)[0]

    # Organize the data into a dictionary
    track_data = {
        'artist': track['artists'][0]['name'],
        'title': track['name'],
        'album': track['album']['name'],
        'release_date': track['album']['release_date'],
        'release_date_precision': track['album']['release_date_precision'],
        'year': track['album']['release_date'].split('-')[0],
        'genre': sp.artist(track['artists'][0]['id'])['genres'],
        'bpm': audio_features['tempo'],
        'energy': audio_features['energy'],
        'album_art_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
        # ... include other fields you're interested in
    }

    return track_data

# To add the tags to the MP3 file:
def tag_mp3(file_path, tags):
    # Open the file with ID3 or create an ID3 tag if it doesn't exist
    try:
        audio = ID3(file_path)
    except ID3NoHeaderError:
        audio = ID3()
    
    audio['TIT2'] = TIT2(encoding=3, text=tags['title'])
    audio['TPE1'] = TPE1(encoding=3, text=tags['artist'])
    audio['TYER'] = TYER(encoding=3, text=str(tags['year']))
    audio['TCON'] = TCON(encoding=3, text=tags['genre'])
    audio['TBPM'] = TBPM(encoding=3, text=str(tags['bpm']))
    
    # Add album art if it exists
    if os.path.exists(tags['art_path']):
        with open(tags['art_path'], 'rb') as albumart:
            audio['APIC'] = APIC(encoding=3, mime='image/jpeg', type=3, desc=u'Cover', data=albumart.read())

    audio.save(file_path, v2_version=3)

# For the database, you could set up an SQLite database like this:
conn = sqlite3.connect('dj_music_library.db')
c = conn.cursor()

# Insert a row of data
def insert_song_to_db(song_data):
    genre_string = ', '.join(song_data['genre']) if isinstance(song_data['genre'], list) else song_data['genre']
    
    insert_sql = """
    INSERT INTO music_library (title, artist, year, genre, bpm, energy_level, file_path, album_art_path)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    data_tuple = (
        song_data['title'],
        song_data['artist'],
        song_data['year'],
        genre_string,
        song_data['bpm'],
        song_data['energy'],
        song_data['file_path'],
        song_data['art_path']  # Include the path to the album art
    )

    try:
        c.execute(insert_sql, data_tuple)
        conn.commit()
    except sqlite3.Error as e:
        print(f"An error occurred while inserting to the database: {e}")


# Ensure that the database connection is closed properly
def close_db_connection():
    conn.close()


# Create the music_library table
def create_music_library_table():
    c.execute('''CREATE TABLE IF NOT EXISTS music_library
                (title text, artist text, year text, genre text, bpm integer, energy_level integer, file_path text, album_art_path text)''')
    conn.commit()

# To search for a song:
def search_songs_by_tag(tag_name, tag_value):
    c.execute(f"SELECT * FROM music_library WHERE {tag_name}=?", (tag_value,))
    return c.fetchall()


def download_from_youtube(song_input, title, artist):
    youtube = None

    # Use the sanitized Spotify title and artist for the filename
    safe_song_title = re.sub(r'[^\w\s-]', '', title).replace(" ", "_")
    safe_artist_name = re.sub(r'[^\w\s-]', '', artist).replace(" ", "_")
    custom_filename = f"{safe_song_title}_by_{safe_artist_name}.mp3"
    custom_directory_path = os.path.join('audio', safe_artist_name, safe_song_title)

    if not os.path.exists(custom_directory_path):
        os.makedirs(custom_directory_path)

    try:
        # If the input is a YouTube URL
        if "https://www.youtube.com" in song_input:
            youtube = YouTube(song_input)
        else:
            # If the input is not a YouTube URL, search for it
            yt_search = YoutubeSearch(song_input, max_results=1).to_json()
            yt_data = json.loads(yt_search)
            if not yt_data['videos']:
                print("Song not found on YouTube.")
                return None
            song_id = yt_data['videos'][0]['id']
            youtube = YouTube(f"https://www.youtube.com/watch?v={song_id}")

        # Download the audio stream at the highest quality
        audio_stream = youtube.streams.get_audio_only()
        download_path = audio_stream.download(output_path=custom_directory_path, filename=custom_filename.replace(".mp3", ".mp4"))

        # Convert MP4 to MP3
        mp4_path = download_path
        mp3_path = os.path.join(custom_directory_path, custom_filename)

        audioclip = AudioFileClip(mp4_path)
        audioclip.write_audiofile(mp3_path)

        # Remove the original MP4 file
        audioclip.close()
        os.remove(mp4_path)

        print(f"Download and conversion complete. File saved as {mp3_path}")
        return mp3_path
    except Exception as e:
        print(f"There was an error processing your request: {e}")
        return None


def download_album_art(album_art_url, artist, title):
    if album_art_url:
        # Make the artist and title filesystem safe by removing potentially problematic characters
        safe_artist = re.sub(r'[^\w\s-]', '', artist).replace(" ", "_")
        safe_title = re.sub(r'[^\w\s-]', '', title).replace(" ", "_")
        
        # Determine the directory and file name for the album art
        directory_path = os.path.join('album_art', safe_artist)
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
        file_path = os.path.join(directory_path, f"{safe_title}_cover.jpg")
        
        # Download the image
        response = requests.get(album_art_url)
        if response.status_code == 200:
            with open(file_path, 'wb') as img_file:
                img_file.write(response.content)
            print(f"Album art downloaded: {file_path}")
            return file_path
        else:
            print(f"Failed to download album art from {album_art_url}")
            return None
    else:
        print("No album art URL provided")
        return None



# Main function to control the flow of the program
def main():
    sp = authenticate_spotipy()
    create_music_library_table()

    input_url = input("Enter the Spotify URL (track or playlist) or track name: ")
    try:
        if "open.spotify.com/track/" in input_url:
            # It's a track link
            track_id = input_url.split("track/")[1].split("?")[0]
            track_data = get_spotify_data(sp, 'spotify:track:' + track_id)
            if track_data:
                # Process the individual track
                process_track(sp, track_data)
        elif "open.spotify.com/playlist/" in input_url:
            # It's a playlist link
            playlist_id = input_url.split("playlist/")[1].split("?")[0]
            playlist_tracks = get_playlist_tracks(sp, playlist_id)
            for item in playlist_tracks:
                track_data = get_spotify_data(sp, 'spotify:track:' + item['track']['id'])
                if track_data:
                    # Process each track in the playlist
                    process_track(sp, track_data)
        else:
            # Assume it's a track name
            track_data = get_spotify_data(sp, input_url)
            if track_data:
                # Process the individual track
                process_track(sp, track_data)
    except spotipy.SpotifyException as e:
        print(f"An error occurred while fetching data from Spotify: {e}")
    except (requests.exceptions.RequestException, OSError, pytube.exceptions.PytubeError) as e:
        print(f"An error occurred: {e}")

    close_db_connection()

def process_track(sp, track_data):
    track_data['art_path'] = download_album_art(track_data['album_art_url'], track_data['artist'], track_data['title'])
    track_data['file_path'] = download_from_youtube(track_data['title'] + ' ' + track_data['artist'], track_data['title'], track_data['artist'])
    if track_data['file_path']:
        tag_mp3(track_data['file_path'], track_data)
        insert_song_to_db(track_data)

# Helper function to get tracks from a Spotify playlist
def get_playlist_tracks(sp, playlist_id):
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    while results:
        # Filter out empty or None track items before extending the list
        tracks.extend([item for item in results['items'] if item['track'] is not None])
        if results['next']:
            results = sp.next(results)
        else:
            break
    return tracks

if __name__ == "__main__":
    main()
# Remember to close the connection when you're done
