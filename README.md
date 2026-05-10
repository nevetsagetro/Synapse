# Synapse

![Python](https://img.shields.io/badge/python-3.10+-blue?style=flat-square)
![Node](https://img.shields.io/badge/node-18+-green?style=flat-square)

A local-first personal library for your Kindle highlights. Import your `My Clippings.txt`, browse your books, and optionally use Google's Gemini API to find connections between highlights or get book recommendations based on what you actually read.

Everything lives in a local SQLite database. Nothing is sent anywhere unless you add a Gemini key.

## Setup

```bash
./setup.sh
./synapse start
```

Opens at `http://localhost:8000`. The frontend is built automatically.

To import highlights, you have two options:

1. **Automated Web Scraper:** Run `python -m scripts.scrape_kindle_notebook` inside the `backend/` directory (with your `.venv` activated). It will open a browser, let you log into Amazon, and automatically download all your highlights from `read.amazon.com/notebook`.
2. **Manual File Upload:** Plug in your Kindle, grab `My Clippings.txt` from the `documents` folder, and upload it on the Import tab.

Both methods share the same database, and any duplicate highlights are smartly merged!

## Gemini (optional)

The app works fine without it. If you want semantic search or AI book recommendations:

1. Get a free key at [Google AI Studio](https://aistudio.google.com/)
2. `cp .env.example .env` and paste your key in
3. Restart

Uses `gemini-2.5-flash` for recommendations and `text-embedding-004` for semantic matching.

## What it does

- **Daily Spark** resurfaces one highlight per day so old books don't get forgotten
- **Personal Thoughts** lets you write timestamped reflections on any highlight, saved locally
- **Insights** shows your highlighting activity, top authors, and books you have marked up most
- **Related Ideas** runs semantic search across your whole library (requires Gemini key)
- **Book Discovery** asks Gemini for recommendations grouped by genre, cached locally, never repeats
- **Recommendation History** keeps every past generation with its timestamp, collapsible in the UI
- **Export** to JSON, CSV, Obsidian Markdown, or the raw `.db` file

## Dev

```bash
./synapse dev              # hot-reload backend + frontend
./synapse test
./synapse import-clippings # CLI import
./synapse rebuild-db       # nuke and re-import from scratch
```

Stack: FastAPI + SQLModel on the backend, React + Vite + Tailwind on the front. Embeddings are stored as JSON in SQLite and similarity is computed with numpy, so there is no Chroma, no Pinecone, no infrastructure to manage.