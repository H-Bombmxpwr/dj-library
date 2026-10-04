"""Find the cleanest YouTube source for a Spotify track.

Primary source is YouTube Music's "songs" search, which returns the label's
official Art Tracks (videoType ATV) - studio audio uploaded by the label, with
no music-video intros, skits or sound effects. Only if no acceptable Art Track
exists do we fall back to a regular YouTube search, where "- Topic" channels,
official audio and lyric videos are preferred and music videos are penalised.

Every candidate must also be within a few seconds of the Spotify duration,
which filters out music-video cuts, extended versions and live takes.
"""
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import yt_dlp
from ytmusicapi import YTMusic

_local = threading.local()

# Words that indicate a different version of the song. Only penalised when
# the Spotify title doesn't contain them too (so real remixes still match).
VERSION_TERMS = [
    "live", "remix", "cover", "karaoke", "instrumental", "acapella", "a cappella",
    "sped up", "speed up", "slowed", "reverb", "nightcore", "8d", "bass boosted",
    "extended", "acoustic", "demo", "mashup", "reaction", "tutorial", "1 hour",
    "loop", "chipmunk", "piano", "orchestral", "clean", "dirty", "lofi", "lo fi",
    "made popular by", "in the style of", "originally by", "originally performed", "tribute",
]
# Phrases that indicate the audio came from a music video
VIDEO_TERMS = ["official video", "music video", "official hd video", "(video)", "[video]", "official 4k video", "short film", "dance video"]
AUDIO_TERMS = ["official audio", "audio only", "(audio)", "[audio]"]
LYRIC_TERMS = ["lyric", "lyrics"]


@dataclass
class Match:
    url: str
    title: str
    source: str  # "YT Music art track", "YouTube Topic", "YouTube lyric video", ...
    duration: float
    score: float


def _ytmusic():
    if not hasattr(_local, "ytm"):
        _local.ytm = YTMusic()
    return _local.ytm


def normalize(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = text.replace("&", " and ").replace("$", "s")
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def core_title(title):
    """'Song (feat. X) - Remastered 2011' -> 'song'"""
    title = re.split(r"\s+-\s+", title)[0]
    title = re.sub(r"[\(\[].*?[\)\]]", "", title)
    return normalize(title)


def _strip_feat(title):
    title = re.sub(r"[\(\[]\s*(feat|ft|featuring|with)\b[^\)\]]*[\)\]]", "", title, flags=re.I)
    return re.sub(r"\s\b(feat|ft|featuring)\b\.?\s.*$", "", title, flags=re.I)


def _has_term(text, term):
    return re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", text) is not None


def _score(track, title, artists_text, duration, kind, explicit=None):
    """Higher is better. Returns None if the candidate is clearly wrong.

    ``artists_text`` is where the artist name must appear: the credited artists
    for YT Music results, channel + title for plain YouTube results.
    """
    cand = title.lower()
    cand_norm = normalize(f"{title} {artists_text}")
    artists_norm = normalize(artists_text)
    want_full = track.title.lower()

    # Duration must line up with the Spotify version
    if track.duration_ms and duration:
        diff = abs(duration - track.duration)
        if diff > max(15, track.duration * 0.07):
            return None
    else:
        diff = 10

    want = core_title(track.title)
    got = core_title(title)
    if not got:
        return None
    sim = SequenceMatcher(None, want, got).ratio()
    if want and (want in cand_norm):
        sim = max(sim, 0.9)
    if sim < 0.55:
        return None

    artists_found = sum(1 for a in track.artists if normalize(a) and normalize(a) in artists_norm)
    if artists_found == 0:
        return None

    score = {"atv": 100, "topic": 95, "lyric": 75, "audio": 80, "omv": 35, "video": 50}[kind]
    score += 40 * sim
    # Reward matching version info too ("Remix", "Radio Edit", "Remastered"...)
    score += 15 * SequenceMatcher(None, normalize(_strip_feat(track.title)), normalize(_strip_feat(title))).ratio()
    score += 15 * artists_found / len(track.artists)
    score -= 2.0 * diff

    for term in VERSION_TERMS:
        if _has_term(cand, term) and not _has_term(want_full, term):
            score -= 60
    if kind not in ("atv", "topic"):
        if any(t in cand for t in VIDEO_TERMS) and not any(t in cand for t in LYRIC_TERMS):
            score -= 40
    if explicit is not None and explicit == track.explicit:
        score += 8
    return score


def _ytmusic_candidates(track):
    query = f"{track.artist} {track.title}"
    results = []
    for attempt in range(3):  # searches occasionally fail transiently under load
        try:
            results = _ytmusic().search(query, filter="songs", limit=10)
            break
        except Exception:
            _local.__dict__.pop("ytm", None)  # reset a broken session
            time.sleep(1 + attempt)
    out = []
    for r in results[:10]:
        if not r.get("videoId"):
            continue
        artists = ", ".join(a["name"] for a in r.get("artists") or [])
        kind = "atv" if r.get("videoType") == "MUSIC_VIDEO_TYPE_ATV" else "omv"
        duration = r.get("duration_seconds") or 0
        score = _score(track, r.get("title", ""), artists, duration, kind, r.get("isExplicit"))
        if score is not None:
            source = "YT Music art track" if kind == "atv" else "YT Music video"
            out.append(Match(f"https://music.youtube.com/watch?v={r['videoId']}",
                             f"{artists} - {r.get('title', '')}", source, duration, score))
    return out


def _youtube_candidates(track):
    query = f"ytsearch10:{track.artist} - {track.title} audio"
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            entries = ydl.extract_info(query, download=False).get("entries") or []
    except Exception:
        return []
    out = []
    for e in entries:
        title = e.get("title") or ""
        channel = e.get("channel") or e.get("uploader") or ""
        lower = title.lower()
        if channel.endswith(" - Topic"):
            kind, source = "topic", "YouTube Topic channel"
        elif any(t in lower for t in AUDIO_TERMS):
            kind, source = "audio", "YouTube official audio"
        elif any(t in lower for t in LYRIC_TERMS):
            kind, source = "lyric", "YouTube lyric video"
        else:
            kind, source = "video", "YouTube video"
        score = _score(track, title, f"{channel} {title}", e.get("duration") or 0, kind)
        if score is not None and e.get("id"):
            out.append(Match(f"https://www.youtube.com/watch?v={e['id']}", title, source,
                             e.get("duration") or 0, score))
    return out


def find_best(track):
    """Return the best Match for a Track, or None."""
    candidates = _ytmusic_candidates(track)
    best = max(candidates, key=lambda m: m.score, default=None)
    if best and best.source == "YT Music art track" and best.score >= 120:
        return best
    candidates += _youtube_candidates(track)
    return max(candidates, key=lambda m: m.score, default=None)
