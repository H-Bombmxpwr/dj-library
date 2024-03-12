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
    # Search for the track on Spotify
    result = sp.search(q=search_query, limit=1, type='track')
    if result['tracks']['items']:
        # Get the first track from the search results
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
    else:
        return None

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
    # Convert genre list to a string if it's not already
    genre_string = ', '.join(song_data['genre']) if isinstance(song_data['genre'], list) else song_data['genre']
    
    # Prepare SQL statement and data
    insert_sql = """
    INSERT INTO music_library (title, artist, year, genre, bpm, energy_level, file_path)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    data_tuple = (
        song_data['title'],
        song_data['artist'],
        song_data['year'],
        genre_string,
        song_data['bpm'],
        song_data['energy'],
        song_data['file_path']
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
                (title text, artist text, year text, genre text, bpm integer, energy_level integer, file_path text)''')
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

    song_input = input("Enter the song name or YouTube URL: ")
    try:
        track_data = get_spotify_data(sp, song_input)
    except spotipy.SpotifyException as e:
        print(f"An error occurred while fetching data from Spotify: {e}")
        return

    if track_data:
        try:
            track_data['art_path'] = download_album_art(track_data['album_art_url'], track_data['artist'], track_data['title'])
            track_data['file_path'] = download_from_youtube(song_input, track_data['title'], track_data['artist'])

            if track_data['file_path']:
                tag_mp3(track_data['file_path'], track_data)
                insert_song_to_db(track_data)
        except (requests.exceptions.RequestException, OSError, pytube.exceptions.PytubeError) as e:
            print(f"An error occurred: {e}")

    close_db_connection()

if __name__ == "__main__":
    main()
# Remember to close the connection when you're done
