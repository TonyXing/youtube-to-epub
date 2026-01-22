#!/usr/bin/env python3
"""
YouTube to EPUB Converter - Startup Script

Usage:
    python run.py

This will start the FastAPI server on http://localhost:8000
"""

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def check_env():
    """Check if required environment variables are set."""
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        print("\n" + "=" * 60)
        print("WARNING: OpenAI API key not configured!")
        print("=" * 60)
        print("\nPlease set your OpenAI API key in the .env file:")
        print(f"  {os.path.join(project_root, '.env')}")
        print("\nExample:")
        print("  OPENAI_API_KEY=sk-...")
        print("=" * 60 + "\n")
        return False
    return True


def main():
    """Start the FastAPI server."""
    import uvicorn

    # Check environment
    if not check_env():
        print("Starting anyway - some features may not work without API key.\n")

    print("Starting YouTube to EPUB Converter...")
    print("Open http://localhost:8000 in your browser\n")

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
