import csv
import io
import os
from urllib.parse import parse_qs, quote_plus, urlparse

import requests
import streamlit as st

st.set_page_config(page_title="Playlist Lyrics Finder", page_icon="🎵", layout="wide")
st.markdown(
    """<style>
    .main .block-container { max-width: 1100px; padding-left: clamp(1rem, 4vw, 3rem); padding-right: clamp(1rem, 4vw, 3rem); }
    [data-testid="stCode"] pre { white-space: pre-wrap; overflow-wrap: anywhere; }
    .mobile-sidebar-hint { display: none; }
    @media (max-width: 640px) {
      .main .block-container { padding: 1rem 0.75rem 2rem; }
      h1 { font-size: 1.8rem !important; }
      [data-testid="stHorizontalBlock"] { flex-direction: column; gap: 0.5rem; }
      [data-testid="stHorizontalBlock"] [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
      [data-testid="stButton"] button, [data-testid="stLinkButton"] a { min-height: 2.75rem; width: 100%; }
      [data-testid="stSidebarCollapsedControl"] button { min-width: 2.75rem; min-height: 2.75rem; }
      [data-testid="stSidebarCollapsedControl"] button svg { display: none !important; }
      [data-testid="stSidebarCollapsedControl"] button::before {
        content: "";
        display: block;
        width: 1.25rem;
        height: 2px;
        margin: auto;
        background: currentColor;
        box-shadow: 0 -6px currentColor, 0 6px currentColor;
      }
      .mobile-sidebar-hint { display: flex; align-items: center; gap: 0.65rem; margin: 0.75rem 0 1rem; padding: 0.8rem; border: 1px solid rgba(128, 128, 128, 0.4); border-radius: 0.6rem; font-size: 0.95rem; }
      .mobile-sidebar-hint-icon { font-size: 1.4rem; line-height: 1; }
    }
    </style>""",
    unsafe_allow_html=True,
)
st.title("Playlist Lyrics Finder")
st.caption("Open one Google lyrics search per song, then copy the lyrics you choose into Word.")
st.markdown(
    '<div class="mobile-sidebar-hint"><span class="mobile-sidebar-hint-icon"> >> </span><span><strong>Playlist controls</strong><br>Tap the arrow icon at the top left to load a playlist or change the song limit.</span></div>',
    unsafe_allow_html=True,
)

YOUTUBE_API = "https://www.googleapis.com/youtube/v3/playlistItems"


def configured_api_key() -> str:
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if key:
        return key
    try:
        return str(st.secrets.get("YOUTUBE_API_KEY", "")).strip()
    except (FileNotFoundError, RuntimeError):
        return ""


def playlist_id_from_url(value: str) -> str:
    value = value.strip()
    parsed = urlparse(value)
    if parsed.path == "/playlist":
        return parse_qs(parsed.query).get("list", [""])[0]
    if not parsed.scheme and "list=" not in value and "/" not in value:
        return value
    return parse_qs(parsed.query).get("list", [""])[0]


def fetch_playlist(api_key: str, playlist_id: str, limit: int = 100):
    rows, token = [], None
    print(f"[playlist-finder] Starting playlist fetch: playlist_id={playlist_id}, limit={limit}")
    while len(rows) < limit:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": min(50, limit - len(rows)),
            "key": api_key,
        }
        if token:
            params["pageToken"] = token
        try:
            response = requests.get(YOUTUBE_API, params=params, timeout=25)
        except requests.RequestException as exc:
            print(f"[playlist-finder] Network request failed: {type(exc).__name__}: {exc}")
            raise RuntimeError(f"Could not contact the YouTube API: {exc}") from exc
        print(
            f"[playlist-finder] YouTube response: HTTP {response.status_code}, "
            f"content-type={response.headers.get('Content-Type', 'unknown')}, body_bytes={len(response.content)}"
        )
        if response.status_code != 200:
            try:
                message = response.json().get("error", {}).get("message", response.text)
            except ValueError:
                message = response.text
            print(f"[playlist-finder] API error: {str(message)[:500]}")
            raise RuntimeError(f"YouTube API error ({response.status_code}): {message}")
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            print(f"[playlist-finder] Invalid JSON response: {response.text[:250]!r}")
            raise RuntimeError("YouTube returned invalid JSON. Check the terminal for the response preview.") from exc

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            video_id = snippet.get("resourceId", {}).get("videoId", "")
            title = snippet.get("title", "Untitled")
            if title in {"Deleted video", "Private video"}:
                continue
            rows.append({
                "title": title,
                "artist": snippet.get("videoOwnerChannelTitle", "") or snippet.get("channelTitle", ""),
                "video_id": video_id,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
            })
        token = data.get("nextPageToken")
        if not token:
            break
    print(f"[playlist-finder] Playlist fetch complete: songs={len(rows)}")
    return rows


def google_search_url(title: str, artist: str = "", include_artist: bool = False) -> str:
    # The artist is optional because playlist channel names often misidentify collaborators.
    terms = f"lyrics {title}"
    if include_artist and artist.strip():
        terms += f" {artist.strip()}"
    terms += " -site:youtube.com -site:youtu.be"
    return "https://www.google.com/search?q=" + quote_plus(terms)


def export_csv(rows, include_artist: bool) -> bytes:
    buffer = io.StringIO()
    fields = ["title", "artist", "youtube_url", "google_search_query", "google_search_url"]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for song in rows:
        url = google_search_url(song["title"], song.get("artist", ""), include_artist)
        query = urlparse(url).query
        search_text = parse_qs(query).get("q", [""])[0]
        writer.writerow({
            "title": song["title"],
            "artist": song.get("artist", ""),
            "youtube_url": song.get("youtube_url", ""),
            "google_search_query": search_text,
            "google_search_url": url,
        })
    return buffer.getvalue().encode("utf-8-sig")


with st.sidebar:
    st.subheader("Playlist controls")
    st.caption("Load a YouTube playlist and choose how many songs to include.")
    api_key = configured_api_key()
    playlist_url = st.text_input("YouTube playlist URL", placeholder="https://www.youtube.com/playlist?list=...")
    limit = st.number_input("Maximum songs", min_value=1, max_value=100, value=100, step=1)
    load = st.button("Load playlist", type="primary", use_container_width=True)

if load:
    playlist_id = playlist_id_from_url(playlist_url)
    if not api_key:
        st.error("No YouTube API key is configured. See the README setup instructions.")
    elif not playlist_id:
        st.error("Paste a YouTube playlist URL containing list=...")
    else:
        try:
            with st.spinner("Loading playlist metadata from YouTube..."):
                st.session_state["songs"] = fetch_playlist(api_key, playlist_id, int(limit))
            st.success(f"Loaded {len(st.session_state['songs'])} songs.")
        except Exception as exc:
            st.error(str(exc))

songs = st.session_state.get("songs", [])
if songs:
    st.subheader("Playlist songs")
    include_artist = st.checkbox(
        "Include the playlist artist/channel name in Google searches",
        value=False,
        help="Leave this off for collaborations or uncertain artist names. Searches then use the song title and lyrics only.",
    )
    st.write("Click a Google button to search for a song. Review a source you trust, then copy the lyrics you choose into Word.")
    edited = []
    for index, original_song in enumerate(songs, start=1):
        song = dict(original_song)
        song.pop("language", None)
        song_key = song.get("video_id") or str(index)
        with st.container(border=True):
            st.markdown(f"**{index}. {song['title']}**")
            if song.get("artist"):
                st.caption(f"Playlist channel / artist: {song['artist']}")
            if song.get("youtube_url"):
                st.link_button("Open YouTube video", song["youtube_url"], key=f"youtube_{song_key}")
            edited.append(song)
            url = google_search_url(song["title"], song.get("artist", ""), include_artist)
            with st.expander("Google search query"):
                st.code(parse_qs(urlparse(url).query).get("q", [""])[0], language=None)
            st.link_button(
                "Search Google for lyrics",
                url,
                key=f"google_{song_key}",
                use_container_width=True,
            )
    st.session_state["songs"] = edited
    st.download_button(
        "Download song list + Google searches (CSV)",
        data=export_csv(edited, include_artist),
        file_name="kenyan_playlist_google_lyrics_searches.csv",
        mime="text/csv",
    )
else:
    st.markdown(
        """### What this app does

1. Loads song titles from a YouTube playlist.
2. Builds a Google lyrics search for each song. Artist names are optional because playlist channel names can be unreliable.

The app does not fetch, store, or reproduce lyrics. It only creates Google search links and a CSV of those links."""
    )
