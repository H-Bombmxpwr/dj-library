from mutagen.id3 import ID3, TIT2, TPE1, TYER, TCON, TBPM, APIC, ID3NoHeaderError
from dotenv import load_dotenv
import os
import requests
import sys
import spotipy
import pytube
sys.path.insert(0, 'src')
from src import album_art
from src import auth
from src import database
from src import spotify_data
from src import youtube

# To addthe tags to the MP3 file:
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




def main():
    sp = auth.authenticate_spotipy()  # Updated this line
    database.create_music_library_tables()

    input_url = input("Enter the Spotify URL (track or playlist) or track name: ")
    try:
        if "open.spotify.com/track/" in input_url:
            track_id = input_url.split("track/")[1].split("?")[0]
            track_data = spotify_data.get_spotify_data(sp, 'spotify:track:' + track_id)
            if track_data:
                process_track(sp, track_data)
        elif "open.spotify.com/playlist/" in input_url:
            playlist_id = input_url.split("playlist/")[1].split("?")[0]
            playlist_tracks = get_playlist_tracks(sp, playlist_id)
            for item in playlist_tracks:
                track_data = spotify_data.get_spotify_data(sp, 'spotify:track:' + item['track']['id'])
                if track_data:
                    process_track(sp, track_data, playlist_id)
        else:
            track_data = spotify_data.get_spotify_data(sp, input_url)
            if track_data:
                process_track(sp, track_data)
    except spotipy.SpotifyException as e:
        print(f"An error occurred while fetching data from Spotify: {e}")
    except (requests.exceptions.RequestException, OSError, pytube.exceptions.PytubeError) as e:
        print(f"An error occurred: {e}")

    database.close_db_connection()

def process_track(sp, track_data, playlist_id=None):
    # Join the genre list into a string separated by commas
    track_data['genre'] = ', '.join(track_data['genre']) if isinstance(track_data['genre'], list) else track_data['genre']
    
    track_data['art_path'] = album_art.download_album_art(track_data['album_art_url'], track_data['artist'], track_data['title'])
    track_data['file_path'] = youtube.download_from_youtube(track_data['title'] + ' ' + track_data['artist'], track_data['title'], track_data['artist'])
    if track_data['file_path']:
        tag_mp3(track_data['file_path'], track_data)
        database.insert_song_to_db(track_data, playlist_id)

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