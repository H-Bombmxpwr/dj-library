import requests
import os
import re

def download_album_art(album_art_url, artist, title):
    if album_art_url:
        safe_artist = re.sub(r'[^\w\s-]', '', artist).replace(" ", "_")
        safe_title = re.sub(r'[^\w\s-]', '', title).replace(" ", "_")
        directory_path = os.path.join('album_art', safe_artist)
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
        file_path = os.path.join(directory_path, f"{safe_title}_cover.jpg")

        if not os.path.exists(file_path):  # Check if the file already exists
            response = requests.get(album_art_url)
            if response.status_code == 200:
                with open(file_path, 'wb') as img_file:
                    img_file.write(response.content)
                print(f"Album art downloaded: {file_path}")
        else:
            print(f"Album art already exists: {file_path}")
        return file_path
    else:
        print("No album art URL provided")
        return None