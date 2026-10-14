# Kenyan Playlist Lyrics Finder

A small Streamlit app that loads YouTube playlist titles and creates one Google lyrics search per song. It does not fetch or save lyrics; open a search, choose a source, and copy the lyrics you want into Word.

## Requirements

- Python 3.10 or newer
- YouTube Data API v3 enabled in a Google Cloud project
- A YouTube Data API key
- Internet access for first-result previews (no additional API key required)

## Setup on Windows

1. Open a terminal in this project folder.
2. Create and activate a virtual environment:

   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   ```

3. Install the app dependencies:

   ```bat
   pip install -r requirements.txt
   ```

4. Create `.streamlit/secrets.toml` and add your API key:

   ```toml
   YOUTUBE_API_KEY = "your-key"
   ```

   Keep this file private. The app reads the key locally and does not display it.

5. Start the app:

   ```bat
   streamlit run app.py
   ```

6. Paste a YouTube playlist URL in the sidebar and click **Load playlist**.

## Setup on macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Create `.streamlit/secrets.toml` in the project folder with the same `YOUTUBE_API_KEY` entry before starting the app.

## Use

- Choose a likely language for each song if you want it included in the search.
- Song controls are displayed as cards and stack vertically on narrow screens for phone use.
- Click **Search Google for lyrics** to open a query for that song.
- **Find previewable result** uses free DuckDuckGo through the `ddgs` library; it does not need another API key. It checks several results in order, skips unreachable pages and pages whose response headers explicitly block embedding, then previews the first candidate that passes. If none pass, **Open first search result** opens the first candidate. If the hosted app cannot query DuckDuckGo, it offers direct DuckDuckGo and Google search links instead. Server-side search can be rate-limited or temporarily unavailable, and some browser-side framing restrictions cannot be detected before the iframe loads.
- Searches use unquoted song titles and exclude YouTube domains to favor lyric pages over video results. Artist/channel names are excluded by default because they can be unreliable for collaborations; turn on the checkbox to include them if useful.
- Review a source you trust, then copy the lyrics you choose into Word.
- Download the CSV to save the song list, search text, and search links.

The app does not scrape lyric pages or copy lyrics into files. Google search continues to work the same way; the DuckDuckGo-powered preview is an additional action.
