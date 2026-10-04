"""ID3 tagging (v2.3 - the version Serato, Traktor, rekordbox and CDJs all read)."""
import threading

import requests
from mutagen.id3 import (APIC, COMM, ID3, TALB, TCON, TCOP, TDRC, TIT2, TLEN, TPE1, TPE2,
                         TPOS, TPUB, TRCK, TSRC, TXXX, USLT, WOAF, WOAS)

_http = threading.local()
_cover_cache = {}
_cover_lock = threading.Lock()


def _session():
    if not hasattr(_http, "s"):
        _http.s = requests.Session()
    return _http.s


def fetch_cover(url):
    """Download album art once per album, shared across threads."""
    if not url:
        return None
    with _cover_lock:
        if url in _cover_cache:
            return _cover_cache[url]
    try:
        r = _session().get(url, timeout=15)
        data = r.content if r.ok else None
    except requests.RequestException:
        data = None
    with _cover_lock:
        _cover_cache[url] = data
    return data


def fetch_lyrics(track):
    """Plain lyrics from LRCLIB (free, no key). Best effort - returns '' on miss."""
    params = {"artist_name": track.artist, "track_name": track.title,
              "album_name": track.album, "duration": round(track.duration)}
    try:
        r = _session().get("https://lrclib.net/api/get", params=params, timeout=10,
                           headers={"User-Agent": "dj-library (personal use)"})
        if r.ok:
            data = r.json()
            return "" if data.get("instrumental") else (data.get("plainLyrics") or "")
    except (requests.RequestException, ValueError):
        pass
    return ""


def _genre(genres):
    return ", ".join(g.title() for g in genres[:3])


def tag_mp3(path, track, source_url="", lyrics="", loudness=None):
    tags = ID3()
    tags.add(TIT2(encoding=3, text=track.title))
    tags.add(TPE1(encoding=3, text=", ".join(track.artists)))
    if track.album:
        tags.add(TALB(encoding=3, text=track.album))
    if track.album_artist:
        tags.add(TPE2(encoding=3, text=track.album_artist))
    if track.release_date:
        tags.add(TDRC(encoding=3, text=track.release_date))
    if track.track_number:
        n = f"{track.track_number}/{track.total_tracks}" if track.total_tracks else str(track.track_number)
        tags.add(TRCK(encoding=3, text=n))
    if track.disc_number:
        tags.add(TPOS(encoding=3, text=str(track.disc_number)))
    if track.genres:
        tags.add(TCON(encoding=3, text=_genre(track.genres)))
    if track.isrc:
        tags.add(TSRC(encoding=3, text=track.isrc))
    if track.label:
        tags.add(TPUB(encoding=3, text=track.label))
    if track.copyright:
        tags.add(TCOP(encoding=3, text=track.copyright))
    if track.duration_ms:
        tags.add(TLEN(encoding=3, text=str(track.duration_ms)))

    tags.add(COMM(encoding=3, lang="eng", desc="", text="Explicit" if track.explicit else "Clean"))
    tags.add(TXXX(encoding=3, desc="ITUNESADVISORY", text="1" if track.explicit else "0"))
    tags.add(TXXX(encoding=3, desc="SPOTIFY_TRACK_ID", text=track.id))
    tags.add(WOAF(url=track.url))
    if source_url:
        tags.add(WOAS(url=source_url))
    if loudness is not None:
        lufs, gain = loudness
        tags.add(TXXX(encoding=3, desc="LOUDNESS_ORIGINAL_LUFS", text=f"{lufs:.1f}"))
        tags.add(TXXX(encoding=3, desc="LOUDNESS_GAIN_APPLIED_DB", text=f"{gain:+.2f}"))
    if lyrics:
        tags.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))

    cover = fetch_cover(track.cover_url)
    if cover:
        mime = "image/png" if cover[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
        tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=cover))

    tags.save(path, v2_version=3)
