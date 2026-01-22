# YouTube to EPUB Converter

A local web app that converts YouTube videos to EPUB format with AI-generated summaries and chapter organization.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- **Video Preview** - Preview video info before conversion
- **Automatic Transcription** - Fetches YouTube video transcripts
- **Smart Chapter Detection** - Uses video chapters if available, or AI-based segmentation for long videos
- **AI Summaries** - Generates overall summary with key takeaways and per-chapter summaries
- **EPUB Generation** - Creates well-formatted EPUB with cover, summary, and transcript chapters
- **In-Browser Reader** - Read the generated EPUB directly in your browser
- **Real-time Progress** - Live progress updates via Server-Sent Events

## Tech Stack

- **Backend**: Python, FastAPI, Uvicorn
- **AI**: Azure OpenAI (GPT-4o-mini)
- **YouTube**: youtube-transcript-api, pytubefix
- **EPUB**: EbookLib, epub.js (reader)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/TonyXing/youtube-to-epub.git
cd youtube-to-epub
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Azure OpenAI

Copy the example environment file and add your Azure OpenAI credentials:

```bash
cp .env.example .env
```

Edit `.env` with your Azure OpenAI settings:

```
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2025-04-01-preview
```

**Where to find these values:**
1. Go to [Azure Portal](https://portal.azure.com/)
2. Open your Azure OpenAI resource
3. **Endpoint & API Key**: Found in "Keys and Endpoint" section
4. **Deployment name**: Found in "Model deployments" → Azure OpenAI Studio

## Usage

### Start the server

```bash
python run.py
```

### Open the web app

Navigate to http://localhost:8000 in your browser.

### Convert a video

1. Paste a YouTube URL (supports `youtube.com/watch`, `youtu.be`, and embed links)
2. Click **Preview** to see video info
3. Click **Convert** to start conversion
4. Once complete:
   - Click **Read Online** to read in the browser
   - Click **Download EPUB** to save the file

## EPUB Structure

The generated EPUB includes:

```
Video Title.epub
├── Cover Page (title, channel, duration)
├── Summary
│   ├── Overview (2-3 paragraphs)
│   ├── Key Takeaways (bullet points)
│   └── Video Information
├── Chapter 1: [Title]
│   ├── Chapter Summary
│   ├── Timestamp
│   └── Full Transcript
├── Chapter 2...
└── Chapter N...
```

## Project Structure

```
youtube-to-epub/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Settings & environment vars
│   ├── api/
│   │   └── routes.py           # API endpoints
│   ├── services/
│   │   ├── youtube_service.py  # Transcript & metadata
│   │   ├── chapter_service.py  # Chapter detection
│   │   ├── summarization_service.py  # AI summarization
│   │   ├── epub_service.py     # EPUB generation
│   │   └── progress_service.py # SSE progress tracking
│   ├── models/
│   │   └── schemas.py          # Pydantic models
│   └── templates/epub/
│       └── styles.css          # EPUB stylesheet
├── static/
│   ├── index.html              # Frontend
│   ├── styles.css
│   └── app.js
├── output/                     # Generated EPUBs
├── .env                        # Configuration (not in repo)
├── .env.example                # Example configuration
├── requirements.txt
└── run.py                      # Startup script
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/preview?url=` | Preview video info |
| POST | `/api/v1/convert` | Start conversion (returns job_id) |
| GET | `/api/v1/convert/{job_id}/progress` | SSE stream for progress |
| GET | `/api/v1/convert/{job_id}/download` | Download EPUB file |

## Requirements

- Python 3.10+
- Azure OpenAI account with a deployed model
- Internet connection (for YouTube access and AI API)

## License

MIT License
