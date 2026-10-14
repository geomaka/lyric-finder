import csv
import io
import os
from urllib.parse import parse_qs, quote_plus, urlparse

import requests
import streamlit as st
from ddgs import DDGS

st.set_page_config(page_title="Playlist Lyrics Finder", page_icon="🎵", layout="wide")
st.markdown(
    """<style>
    .main .block-container { max-width: 1100px; padding-left: clamp(1rem, 4vw, 3rem); padding-right: clamp(1rem, 4vw, 3rem); }
    [data-testid="stCode"] pre { white-space: pre-wrap; overflow-wrap: anywhere; }
    iframe { max-width: 100%; }
    @media (max-width: 640px) {
      .main .block-container { padding: 1rem 0.75rem 2rem; }
      h1 { font-size: 1.8rem !important; }
      [data-testid="stHorizontalBlock"] { flex-direction: column; gap: 0.5rem; }
      [data-testid="stHorizontalBlock"] [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
      [data-testid="stButton"] button, [data-testid="stLinkButton"] a { min-height: 2.75rem; width: 100%; }
      iframe { height: 70vh; }
    }
    </style>""",
    unsafe_allow_html=True,
)
st.title("Playlist Lyrics Finder")
st.caption("Open one Google lyrics search per song, then copy the lyrics you choose into Word.")

LANGUAGES = [
    "Unknown / detect manually", "Kikuyu", "Dholuo", "Luhya", "Kamba",
    "Kalenjin", "Ekegusii", "Kiswahili", "Sheng", "Other Kenyan language",
]
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
                "language": "Unknown / detect manually",
            })
        token = data.get("nextPageToken")
        if not token:
            break
    print(f"[playlist-finder] Playlist fetch complete: songs={len(rows)}")
    return rows


def google_search_url(title: str, language: str, artist: str = "", include_artist: bool = False) -> str:
    # The artist is optional because playlist channel names often misidentify collaborators.
    terms = f"lyrics {title}"
    if language != "Unknown / detect manually":
        terms += f" {language}"
    if include_artist and artist.strip():
        terms += f" {artist.strip()}"
    terms += " -site:youtube.com -site:youtu.be"
    return "https://www.google.com/search?q=" + quote_plus(terms)


def find_previewable_result(title: str, language: str, artist: str = "", include_artist: bool = False):
    """Return the first reachable search result that does not explicitly block framing."""
    terms = f"lyrics {title}"
    if language != "Unknown / detect manually":
        terms += f" {language}"
    if include_artist and artist.strip():
        terms += f" {artist.strip()}"
    terms += " -site:youtube.com -site:youtu.be"
    results = DDGS(timeout=10).text(
        terms,
        region="wt-wt",
        max_results=8,
        backend="duckduckgo",
    )
    skipped = []
    for position, item in enumerate(results, start=1):
        candidate_url = item.get("href", "")
        parsed_url = urlparse(candidate_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            skipped.append(item)
            continue
        try:
            response = requests.get(
                candidate_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PlaylistLyricsFinder/1.0)"},
                timeout=6,
                allow_redirects=True,
                stream=True,
            )
            status = response.status_code
            final_url = response.url
            headers = response.headers
            content_type = headers.get("Content-Type", "").lower()
            x_frame_options = headers.get("X-Frame-Options", "").lower()
            csp = headers.get("Content-Security-Policy", "").lower()
            response.close()
        except requests.RequestException:
            skipped.append(item)
            continue

        if status < 200 or status >= 300 or "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            skipped.append(item)
            continue
        if any(value in x_frame_options for value in ("deny", "sameorigin", "allow-from")):
            skipped.append(item)
            continue

        frame_ancestors = next(
            (directive.strip() for directive in csp.split(";") if directive.strip().startswith("frame-ancestors ")),
            "",
        )
        if frame_ancestors:
            sources = frame_ancestors.split()[1:]
            if not sources or "*" not in sources:
                skipped.append(item)
                continue

        return {
            "title": item.get("title", "Search result"),
            "url": final_url,
            "position": position,
            "skipped": skipped,
            "other_results": results,
        }
    return {"result": None, "skipped": skipped, "other_results": results}


def export_csv(rows, include_artist: bool) -> bytes:
    buffer = io.StringIO()
    fields = ["title", "artist", "language", "youtube_url", "google_search_query", "google_search_url"]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for song in rows:
        language = song.get("language", "Unknown / detect manually")
        url = google_search_url(song["title"], language, song.get("artist", ""), include_artist)
        query = urlparse(url).query
        search_text = parse_qs(query).get("q", [""])[0]
        writer.writerow({
            "title": song["title"],
            "artist": song.get("artist", ""),
            "language": language,
            "youtube_url": song.get("youtube_url", ""),
            "google_search_query": search_text,
            "google_search_url": url,
        })
    return buffer.getvalue().encode("utf-8-sig")


with st.sidebar:
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
        song_key = song.get("video_id") or str(index)
        current_language = song.get("language") or "Unknown / detect manually"
        language_index = LANGUAGES.index(current_language) if current_language in LANGUAGES else 0
        with st.container(border=True):
            st.markdown(f"**{index}. {song['title']}**")
            if song.get("artist"):
                st.caption(f"Playlist channel / artist: {song['artist']}")
            if song.get("youtube_url"):
                st.link_button("Open YouTube video", song["youtube_url"], key=f"youtube_{song_key}")
            song["language"] = st.selectbox(
                "Likely language",
                options=LANGUAGES,
                index=language_index,
                key=f"language_{song_key}",
            )
            edited.append(song)
            language = song.get("language") or "Unknown / detect manually"
            url = google_search_url(song["title"], language, song.get("artist", ""), include_artist)
            with st.expander("Google search query"):
                st.code(parse_qs(urlparse(url).query).get("q", [""])[0], language=None)
            actions = st.columns(2)
            actions[0].link_button("Search Google for lyrics", url, key=f"google_{song_key}", use_container_width=True)
            preview_key = f"preview_result_{song_key}"
            if actions[1].button("Find previewable result", key=f"preview_button_{song_key}", use_container_width=True):
                try:
                    with st.spinner("Checking search results for a page that allows previews..."):
                        search = find_previewable_result(song["title"], language, song.get("artist", ""), include_artist)
                    if search and search.get("url"):
                        st.session_state[preview_key] = search
                    else:
                        st.session_state[preview_key] = search or {"other_results": []}
                        if search and search.get("other_results"):
                            st.warning("None of the checked pages appears previewable. You can still open a result directly.")
                        else:
                            st.info("DuckDuckGo returned no result links. Open the Google lyrics search instead.")
                except Exception:
                    st.session_state[preview_key] = {"other_results": []}
                    st.warning("DuckDuckGo could not return results. Open the Google lyrics search instead.")
            result = st.session_state.get(preview_key)
            if result:
                result_url = result.get("url", "")
                if result_url:
                    st.markdown(f"**Previewable result (search result {result['position']}):** [{result.get('title', result_url)}]({result_url})")
                    st.caption("A page can still block framing through browser-side rules. Use Open in browser if the preview is blank.")
                    st.link_button("Open in browser", result_url, key=f"open_preview_{song_key}")
                    st.components.v1.iframe(result_url, height=600, scrolling=True)
                else:
                    other_results = result.get("other_results", [])
                    if other_results:
                        first_result = other_results[0]
                        first_url = first_result.get("href", "")
                        if first_url:
                            st.write("No result allowed an embedded preview. Open the first search result to view the lyrics:")
                            st.link_button(
                                "Open first search result",
                                first_url,
                                key=f"open_first_result_{song_key}",
                            )
                    else:
                        st.link_button(
                            "Open Google search results",
                            url,
                            key=f"google_fallback_{song_key}",
                        )
                    if other_results:
                        with st.expander("Search results (none passed the preview checks)"):
                            for result_index, item in enumerate(other_results, start=1):
                                link = item.get("href", "")
                                if link:
                                    st.markdown(f"{result_index}. [{item.get('title', link)}]({link})")
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
