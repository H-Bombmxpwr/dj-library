from pytube import YouTube
from moviepy.editor import AudioFileClip
import os
import re
import json
from youtube_search import YoutubeSearch

def download_from_youtube(song_input, title, artist):
    safe_song_title = re.sub(r'[^\w\s-]', '', title).replace(" ", "_")
    safe_artist_name = re.sub(r'[^\w\s-]', '', artist).replace(" ", "_")
    custom_filename = f"{safe_song_title}_by_{safe_artist_name}.mp3"
    custom_directory_path = os.path.join('mp3_lib', safe_artist_name, safe_song_title)

    if not os.path.exists(custom_directory_path):
        os.makedirs(custom_directory_path)

    mp3_path = os.path.join(custom_directory_path, custom_filename)

    if not os.path.exists(mp3_path):  # Check if the file already exists
        try:
            youtube = YouTube(song_input) if "https://www.youtube.com" in song_input else None
            if not youtube:
                yt_search = YoutubeSearch(song_input, max_results=1).to_json()
                yt_data = json.loads(yt_search)
                if not yt_data['videos']:
                    print("Song not found on YouTube.")
                    return None
                youtube = YouTube(f"https://www.youtube.com/watch?v={yt_data['videos'][0]['id']}")

            audio_stream = youtube.streams.get_audio_only()
            download_path = audio_stream.download(output_path=custom_directory_path, filename=custom_filename.replace(".mp3", ".mp4"))
            audioclip = AudioFileClip(download_path)
            audioclip.write_audiofile(mp3_path)
            audioclip.close()
            os.remove(download_path)
            print(f"Download and conversion complete. File saved as {mp3_path}")
        except Exception as e:
            print(f"There was an error processing your request: {e}")
            return None
    else:
        print(f"File already exists: {mp3_path}")

    return mp3_path