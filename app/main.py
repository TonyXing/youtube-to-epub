from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.api.routes import router
from app.config import BASE_DIR

app = FastAPI(
    title="YouTube to EPUB Converter",
    description="Convert YouTube videos to EPUB format with AI-generated summaries",
    version="1.0.0",
)

# Include API routes
app.include_router(router)

# Mount static files
static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Serve the frontend."""
    return FileResponse(str(static_dir / "index.html"))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
