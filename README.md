# Multilevel Essays Telegram Publisher

Production-ready scaffold for a Telegram publishing workflow with aiogram 3, Flask, React, PostgreSQL, APScheduler, Google Drive-backed content storage, OpenAI TTS, SQLAlchemy, and Pillow image rendering.

## Features

- Upload vocabulary CSV files into Google Drive or reuse Drive-hosted CSVs already inside the project folder structure.
- Review rows, choose a saved template, and pre-generate Drive-backed image/audio/caption assets before scheduling.
- Auto-publish image posts to the configured Telegram channel
- Generate one British English pronunciation audio file with OpenAI TTS
- Template-based PNG rendering with Pillow onto static background images
- JSON-configurable template coordinates, fonts, colors, line spacing, text widths, and dynamic font resizing
- Flask authenticated admin API with React admin panel
- Scheduler management: days, multiple times per day, timezone, pause/resume, manual publish, random jitter
- Queue, calendar, preview, audio/template upload, analytics, and failed jobs endpoints
- Docker + docker-compose with PostgreSQL

## Project Structure

```text
project/
├── bot/                     # aiogram command runner
├── admin/                   # Flask admin API and built React assets
├── scheduler/               # APScheduler setup and jobs
├── integrations/            # External service integrations
├── services/
│   ├── image_renderer/      # Pillow template renderer
│   ├── tts/                 # OpenAI TTS service
│   └── telegram/            # async Telegram publishing service
├── assets/
│   ├── templates/           # static template PNGs + JSON configs
│   ├── fonts/               # uploaded custom fonts
│   ├── generated/           # generated Telegram-ready PNGs
│   └── audio/               # generated TTS audio
├── database/                # SQLAlchemy models/repositories
├── config/                  # settings and logging
├── frontend/                # React admin UI
└── main.py
```

## Local Setup

1. Copy environment config:

```bash
cp .env.example .env
```

2. Fill `.env` with Telegram, OpenAI, Google Drive, and PostgreSQL values.

3. Install Python libraries into your existing virtual environment:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

4. Generate the sample static template image:

```bash
python scripts/create_sample_assets.py
```

5. Start PostgreSQL locally or with Docker, then initialize tables and the default admin:

```bash
python main.py init-db
```

6. Start the Flask admin API. By default this also starts the embedded scheduler, controlled by `START_SCHEDULER_WITH_ADMIN=true`:

```bash
python main.py admin
```

7. For production-style deployments, set `START_SCHEDULER_WITH_ADMIN=false` and start the scheduler in another terminal:

```bash
python main.py scheduler
```

8. Optional aiogram polling process:

```bash
python main.py bot
```

The default admin login is controlled by `DEFAULT_ADMIN_USERNAME` and `DEFAULT_ADMIN_PASSWORD`.

## React Admin UI

```bash
cd frontend
npm install
npm run dev
```

For production, Docker builds the React app and serves it through Flask from `admin/static`.

## Docker

```bash
docker compose up --build
```

The app is available at `http://localhost:5050`.

## Google Drive

Enable the **Google Drive API** in Google Cloud and create an OAuth web client. Configure `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`, then sign in to the admin panel and use **Connect Drive** from the Dashboard. The app stores the resulting refresh token in PostgreSQL and writes files into that Google account's My Drive storage.

Use the Dashboard's displayed redirect URL as an authorized redirect URI for the OAuth client. In production it is:

```text
https://web-production-b60f9.up.railway.app/api/drive/oauth/callback
```

The app manages this Drive layout automatically:

```text
writing-telegram-channel/
└── vocabulary/
    ├── new-words/
    │   ├── source-files/
    │   └── generated-posts/
    ├── idioms/
    │   ├── source-files/
    │   └── generated-posts/
    └── templates/
```

The app creates and reuses the vocabulary, template, source, and generated-post folders below `GOOGLE_DRIVE_ROOT_FOLDER_NAME`. If `GOOGLE_DRIVE_ROOT_FOLDER_ID` is set, that folder is used directly.

Vocabulary CSV files must use a header row. Supported starter columns are:

```text
Name,Word-Type,Definition,Example
```

Extra future columns are preserved in the stored row payload.

## Template System

Each template has:

- A static PNG background in `assets/templates/`
- A JSON config in `assets/templates/`
- Field boxes for `word`, `word_type`, `phonetic`, `definition`, `example`, and `level`

Example config fields:

```json
{
  "background_image": "assets/templates/default.png",
  "fields": {
    "word": {
      "x": 96,
      "y": 250,
      "width": 888,
      "font_path": "assets/fonts/Inter-Bold.ttf",
      "font_size": 92,
      "min_font_size": 48,
      "color": "#101828",
      "line_spacing": 10,
      "max_lines": 2
    }
  }
}
```

The renderer wraps text automatically, shrinks long words, supports custom fonts via `ImageFont.truetype`, and exports Telegram-ready PNG files before publishing.
