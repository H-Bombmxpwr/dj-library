import sqlite3

conn = sqlite3.connect('dj_music_library.db')
c = conn.cursor()

# Create the music_library table
def create_music_library_tables():
    c.execute('''CREATE TABLE IF NOT EXISTS music_library
                 (spotify_id TEXT PRIMARY KEY, title TEXT, artist TEXT, album_name TEXT, album_spotify_id TEXT, year TEXT, duration TEXT, genre TEXT, bpm INTEGER, energy_level INTEGER, file_path TEXT, album_art_path TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS playlist_song
                 (spotify_id TEXT, playlist_id TEXT, PRIMARY KEY (spotify_id, playlist_id), FOREIGN KEY(spotify_id) REFERENCES music_library(spotify_id))''')
    conn.commit()



def insert_song_to_db(track_data, playlist_id=None):
    spotify_id = track_data['id']  # The Spotify ID of the track
    # Check if the song already exists in the database
    genre_string = ", ".join(track_data['genre']) if isinstance(track_data['genre'], list) else track_data['genre']
    c.execute("SELECT spotify_id FROM music_library WHERE spotify_id=?", (spotify_id,))
    
    if c.fetchone() is None:
        # If the song doesn't exist, insert it
        c.execute('''INSERT INTO music_library (spotify_id, title, artist, album_name, album_spotify_id, year, duration, genre, bpm, energy_level, file_path, album_art_path)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (spotify_id, track_data['title'], track_data['artist'], track_data['album'], track_data['album_spotify_id'], track_data['year'], track_data['duration'], genre_string, 
                   track_data['bpm'], track_data['energy'], track_data['file_path'], track_data['art_path'] if 'art_path' in track_data else None))
    
    # Handle playlist association
    if playlist_id:
        # Check if the playlist association already exists for this song
        c.execute("SELECT 1 FROM playlist_song WHERE spotify_id=? AND playlist_id=?", (spotify_id, playlist_id))
        if c.fetchone() is None:
            # If the playlist association doesn't exist, insert it
            c.execute("INSERT INTO playlist_song (spotify_id, playlist_id) VALUES (?, ?)", (spotify_id, playlist_id))
    
    conn.commit()
    
# Ensure that the database connection is closed properly
def close_db_connection():
    conn.close()