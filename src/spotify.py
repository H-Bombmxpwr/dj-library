"""Spotify access: authentication, URL parsing and track metadata.

Everything is fetched in batches (50 tracks/artists, 20 albums per request) so
metadata for a 500-track playlist takes a handful of requests instead of
hundreds.
"""
import os
import re
from dataclasses import dataclass, field

import spotipy
from dotenv import load_dotenv
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.oauth2 import SpotifyClientCredentials

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_DIR, "keys.env"))

URL_RE = re.compile(r"(playlist|album|track)[/:]([A-Za-z0-9]{22})")


@dataclass
class Track:
    id: str
    title: str
    artists: list
    album: str = ""
    album_artist: str = ""
    release_date: str = ""
    track_number: int = 0
    total_tracks: int = 0
    disc_number: int = 0
    duration_ms: int = 0
    explicit: bool = False
    isrc: str = ""
    label: str = ""
    copyright: str = ""
    genres: list = field(default_factory=list)
    cover_url: str = ""
    album_id: str = ""
    artist_ids: list = field(default_factory=list)

    @property
    def artist(self):
        """Primary artist (used for file names so existing libraries still match)."""
        return self.artists[0] if self.artists else "Unknown Artist"

    @property
    def year(self):
        return self.release_date[:4]

    @property
    def duration(self):
        return self.duration_ms / 1000

    @property
    def url(self):
        return f"https://open.spotify.com/track/{self.id}"


def authenticate():
    """Client-credentials auth that refreshes itself, so long runs never expire."""
    manager = SpotifyClientCredentials(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        cache_handler=MemoryCacheHandler(),
    )
    return spotipy.Spotify(client_credentials_manager=manager, requests_timeout=20, retries=5)


def parse_url(url):
    """Return (kind, id) for a Spotify playlist/album/track URL or URI."""
    match = URL_RE.search(url)
    if not match:
        raise ValueError(f"Not a Spotify playlist, album or track link: {url}")
    return match.group(1), match.group(2)


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _track_from_api(t):
    album = t.get("album") or {}
    images = album.get("images") or []
    return Track(
        id=t["id"],
        title=t["name"],
        artists=[a["name"] for a in t.get("artists", [])],
        artist_ids=[a["id"] for a in t.get("artists", []) if a.get("id")],
        album=album.get("name", ""),
        album_artist=", ".join(a["name"] for a in album.get("artists", [])),
        album_id=album.get("id") or "",
        release_date=album.get("release_date", "") or "",
        track_number=t.get("track_number") or 0,
        total_tracks=album.get("total_tracks") or 0,
        disc_number=t.get("disc_number") or 0,
        duration_ms=t.get("duration_ms") or 0,
        explicit=bool(t.get("explicit")),
        isrc=(t.get("external_ids") or {}).get("isrc", ""),
        cover_url=max(images, key=lambda i: i.get("width") or 0)["url"] if images else "",
    )


def _enrich(sp, tracks):
    """Fill label/copyright (album endpoint) and genres (artist endpoint)."""
    album_ids = list({t.album_id for t in tracks if t.album_id})
    albums = {}
    for chunk in _chunks(album_ids, 20):
        try:
            for a in sp.albums(chunk)["albums"]:
                if a:
                    albums[a["id"]] = a
        except spotipy.SpotifyException:
            pass

    artist_ids = list({aid for t in tracks for aid in t.artist_ids})
    genres = {}
    for chunk in _chunks(artist_ids, 50):
        try:
            for a in sp.artists(chunk)["artists"]:
                if a:
                    genres[a["id"]] = a.get("genres") or []
        except spotipy.SpotifyException:
            pass

    for t in tracks:
        album = albums.get(t.album_id)
        if album:
            t.label = album.get("label") or ""
            copyrights = album.get("copyrights") or []
            # Prefer the (P) sound-recording copyright, fall back to (C)
            copyrights.sort(key=lambda c: c.get("type") != "P")
            t.copyright = copyrights[0]["text"] if copyrights else ""
        seen = []
        for aid in t.artist_ids:
            for g in genres.get(aid, []):
                if g not in seen:
                    seen.append(g)
        t.genres = seen


def fetch(sp, url):
    """Resolve a Spotify link into (collection_name, [Track, ...])."""
    kind, sid = parse_url(url)

    if kind == "playlist":
        name = sp.playlist(sid, fields="name")["name"]
        raw = []
        page = sp.playlist_items(sid, additional_types=("track",))
        while page:
            raw.extend(item.get("track") or item.get("item") for item in page["items"])
            page = sp.next(page) if page.get("next") else None
        raw = [t for t in raw if t and t.get("id") and t.get("type", "track") == "track"]
    elif kind == "album":
        album = sp.album(sid)
        name = f"{album['artists'][0]['name']} - {album['name']}"
        ids = []
        page = album["tracks"]
        while page:
            ids.extend(t["id"] for t in page["items"] if t.get("id"))
            page = sp.next(page) if page.get("next") else None
        raw = [t for chunk in _chunks(ids, 50) for t in sp.tracks(chunk)["tracks"] if t]
    else:
        name = "Singles"
        raw = [sp.track(sid)]

    tracks = [_track_from_api(t) for t in raw]
    _enrich(sp, tracks)
    return name, tracks
