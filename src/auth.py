import os
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy

load_dotenv('keys.env')

def authenticate_spotipy():
    client_id = os.getenv('SPOTIPY_CLIENT_ID')
    client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')

    # Manually get the token
    credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    token_info = credentials_manager.get_access_token(as_dict=True)
    token = token_info['access_token']

    # Log proof
    print(f"✅ Access token: {token[:10]}... (length: {len(token)})")

    # Manually inject the token into Spotipy
    sp = spotipy.Spotify(auth=token)
    return sp
