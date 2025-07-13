import os
import re
import json
import subprocess
from youtube_search import YoutubeSearch
import yt_dlp

from mutagen.mp3 import MP3
from mutagen import MutagenError

def search_youtube(query, max_results=5):
    ydl_opts = {
        "quiet": True,
        "format": "bestaudio/best",
        "noplaylist": True,
        "extract_flat": "in_playlist",
        "default_search": "ytsearch",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            results = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            videos = []
            for video in results["entries"]:
                videos.append({
                    "title": video.get("title", ""),
                    "duration": video.get("duration", 0),
                    "webpage_url": f"https://www.youtube.com/watch?v={video.get('id')}"
                })
            return videos

        except Exception as e:
            print(f"❌ YouTube search failed: {e}")
            return []

def is_valid_video(title, duration):
    title = title.lower()
    banned_keywords = [
        "live", "remix", "cover", "performance", "music video",
        "sped up", "slowed", "reverb", "nightcore", "8d", "#shorts"
    ]
    if any(bad in title for bad in banned_keywords):
        return False
    return 90 <= duration <= 600  # 1.5 to 10 minutes

def search_youtube_multiple(query, fallback_limit=5):
    entries = search_youtube(query, max_results=fallback_limit)
    for video in entries:
        title = video.get("title", "")
        duration = video.get("duration", 0)
        if is_valid_video(title, duration):
            return {
                "title": title,
                "duration": duration,
                "webpage_url": video["webpage_url"]  # ✅ Fix this key
            }
    return None



def download_audio_from_url(url, output_path):
    from yt_dlp import YoutubeDL

    # Remove existing .mp3 extension explicitly to avoid duplication
    output_path = re.sub(r'(\.mp3)+$', '', output_path)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,  # NO .mp3 here; yt-dlp adds it automatically
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'noplaylist': True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
            final_output = output_path + ".mp3"
            return final_output if os.path.exists(final_output) else None
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return None





def is_valid_mp3(file_path):
    try:
        audio = MP3(file_path)
        return audio.info.length > 0
    except MutagenError:
        return False
    except Exception:
        return False





