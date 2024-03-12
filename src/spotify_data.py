import auth

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

    duration_ms = audio_features['duration_ms']
    # Convert duration from milliseconds to MM:SS format
    minutes, seconds = divmod(duration_ms // 1000, 60)
    duration_str = f"{minutes}:{seconds:02d}"
    
    # Organize the data into a dictionary
    track_data = {
        'id': track_id,
        'artist': track['artists'][0]['name'],
        'title': track['name'],
        'album': track['album']['name'],
        'release_date': track['album']['release_date'],
        'release_date_precision': track['album']['release_date_precision'],
        'year': track['album']['release_date'].split('-')[0],
        'genre': sp.artist(track['artists'][0]['id'])['genres'],
        'bpm': audio_features['tempo'],
        'energy': audio_features['energy'],
        'duration': duration_str,  # Added duration in MM:SS
        'album_art_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
        'album': track['album']['name'],
        'album_spotify_id': track['album']['id']
    }
    
    return track_data