import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATES_DIR = BASE_DIR / "app" / "templates" / "epub"

# Ensure output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o-mini"

# Token settings
MAX_TOKENS_PER_CHUNK = 6000
TOKEN_OVERLAP = 200

# Chapter detection settings
SHORT_VIDEO_THRESHOLD_MINUTES = 15

# Progress steps
PROGRESS_STEPS = {
    "validating": (0, 5),
    "fetching_metadata": (5, 15),
    "fetching_transcript": (15, 30),
    "detecting_chapters": (30, 40),
    "generating_summaries": (40, 80),
    "creating_epub": (80, 95),
    "completed": (100, 100),
}
