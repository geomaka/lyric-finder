# Kenyan Playlist Lyrics Finder

A small Streamlit app that loads YouTube playlist titles and creates one Google lyrics search per song. It does not fetch or save lyrics; open a search, choose a source, and copy the lyrics you want into Word.

## Requirements

- Python 3.10 or newer
- YouTube Data API v3 enabled in a Google Cloud project
- A YouTube Data API key
- Optional: an OpenRouter API key for AI-assisted web searches for lyric sources

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
   # Optional; required only for AI-assisted online lyric-source searches
   OPENROUTER_API_KEY = "your-openrouter-api-key"
   # Optional model override (default: openrouter/free)
   # OPENROUTER_MODEL = "openrouter/free"
   ```

   Create a key in [OpenRouter](https://openrouter.ai/settings/keys). Keep this file private. The app reads the keys locally and does not display them. The `openrouter/free` model router can choose different available models over time. OpenRouter's web search is a separate service and may require credits; this app caps it at one search request per song click.

   For a Streamlit Community Cloud deployment, add `OPENROUTER_API_KEY` under the app's **Settings > Secrets** as well. The deployed app will not read your local `secrets.toml` file.

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

- Song controls are displayed as cards and stack vertically on narrow screens for phone use.
- Click **Search Google for lyrics** to open a query for that song.
- **Find lyric sources with AI** uses OpenRouter's web-search tool to find candidate lyric pages using the song's title spelling, then shows source links, match details, and the likely lyrics language when the source indicates it. It does not reproduce lyrics in the app. Each search uses OpenRouter credits (currently about $0.005); the AI model itself uses the `openrouter/free` router.
- Searches use unquoted song titles and exclude YouTube domains to favor lyric pages over video results. Artist/channel names are excluded by default because they can be unreliable for collaborations; turn on the checkbox to include them if useful.
- Review a source you trust, then copy the lyrics you choose into Word.
- Download the CSV to save the song list, search text, and search links.

The app does not scrape lyric pages or copy lyrics into files. It only creates Google search links and a CSV of those links.
