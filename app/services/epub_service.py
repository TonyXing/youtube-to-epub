import re
import uuid
from pathlib import Path
from ebooklib import epub

from app.config import OUTPUT_DIR, TEMPLATES_DIR
from app.models.schemas import ProcessedVideo, VideoChapter
from app.services.youtube_service import format_duration


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for filesystem compatibility."""
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Limit length
    sanitized = sanitized[:100]
    return sanitized.strip()


def create_epub(processed_video: ProcessedVideo) -> Path:
    """Generate EPUB file from processed video data."""
    book = epub.EpubBook()

    # Metadata
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(processed_video.metadata.title)
    book.set_language('en')
    book.add_author(processed_video.metadata.channel)

    # Load CSS
    css_path = TEMPLATES_DIR / "styles.css"
    with open(css_path, 'r', encoding='utf-8') as f:
        css_content = f.read()

    css = epub.EpubItem(
        uid="style",
        file_name="style/styles.css",
        media_type="text/css",
        content=css_content,
    )
    book.add_item(css)

    # Create chapters list for TOC
    epub_chapters = []

    # 1. Cover page
    cover_chapter = _create_cover_chapter(processed_video, css)
    book.add_item(cover_chapter)
    epub_chapters.append(cover_chapter)

    # 2. Summary chapter
    summary_chapter = _create_summary_chapter(processed_video, css)
    book.add_item(summary_chapter)
    epub_chapters.append(summary_chapter)

    # 3. Content chapters
    for i, chapter in enumerate(processed_video.chapters):
        content_chapter = _create_content_chapter(chapter, i, css)
        book.add_item(content_chapter)
        epub_chapters.append(content_chapter)

    # Define spine and TOC
    book.spine = ['nav'] + epub_chapters
    book.toc = epub_chapters

    # Add navigation
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Generate filename and save
    filename = f"{sanitize_filename(processed_video.metadata.title)}.epub"
    output_path = OUTPUT_DIR / filename

    epub.write_epub(str(output_path), book, {})

    return output_path


def _create_cover_chapter(processed_video: ProcessedVideo, css: epub.EpubItem) -> epub.EpubHtml:
    """Create the cover page chapter."""
    metadata = processed_video.metadata

    thumbnail_html = ""
    if metadata.thumbnail_url:
        thumbnail_html = f'<img src="{metadata.thumbnail_url}" alt="Video thumbnail" />'

    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{_escape_html(metadata.title)}</title>
    <link rel="stylesheet" type="text/css" href="style/styles.css"/>
</head>
<body>
    <div class="cover">
        {thumbnail_html}
        <div class="title">{_escape_html(metadata.title)}</div>
        <div class="channel">{_escape_html(metadata.channel)}</div>
        <div class="duration">Duration: {format_duration(metadata.duration)}</div>
    </div>
</body>
</html>"""

    chapter = epub.EpubHtml(
        title="Cover",
        file_name="cover.xhtml",
        lang="en",
    )
    chapter.content = content
    chapter.add_item(css)

    return chapter


def _create_summary_chapter(processed_video: ProcessedVideo, css: epub.EpubItem) -> epub.EpubHtml:
    """Create the summary chapter."""
    metadata = processed_video.metadata
    summary = processed_video.overall_summary

    # Format key takeaways as list
    takeaways_html = "\n".join(
        f"<li>{_escape_html(takeaway)}</li>"
        for takeaway in summary.key_takeaways
    )

    # Format overview paragraphs
    overview_paragraphs = summary.overview.split('\n\n')
    overview_html = "\n".join(
        f"<p>{_escape_html(p)}</p>"
        for p in overview_paragraphs if p.strip()
    )

    publish_info = ""
    if metadata.publish_date:
        publish_info = f"<p><strong>Published:</strong> {metadata.publish_date}</p>"

    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>Summary</title>
    <link rel="stylesheet" type="text/css" href="style/styles.css"/>
</head>
<body>
    <h1>Summary</h1>

    <div class="summary-box">
        <h2>Overview</h2>
        {overview_html}
    </div>

    <div class="key-takeaways">
        <h2>Key Takeaways</h2>
        <ul>
            {takeaways_html}
        </ul>
    </div>

    <div class="meta-info">
        <h2>Video Information</h2>
        <p><strong>Title:</strong> {_escape_html(metadata.title)}</p>
        <p><strong>Channel:</strong> {_escape_html(metadata.channel)}</p>
        <p><strong>Duration:</strong> {format_duration(metadata.duration)}</p>
        {publish_info}
        <p><strong>Chapters:</strong> {len(processed_video.chapters)}</p>
    </div>
</body>
</html>"""

    chapter = epub.EpubHtml(
        title="Summary",
        file_name="summary.xhtml",
        lang="en",
    )
    chapter.content = content
    chapter.add_item(css)

    return chapter


def _create_content_chapter(
    chapter: VideoChapter,
    index: int,
    css: epub.EpubItem,
) -> epub.EpubHtml:
    """Create a content chapter with summary and transcript."""
    # Format timestamp
    start_formatted = format_duration(int(chapter.start_time))
    end_formatted = format_duration(int(chapter.end_time)) if chapter.end_time else ""
    timestamp = f"{start_formatted} - {end_formatted}" if end_formatted else f"From {start_formatted}"

    # Format summary
    summary_html = ""
    if chapter.summary:
        summary_paragraphs = chapter.summary.split('\n\n')
        summary_content = "\n".join(
            f"<p>{_escape_html(p)}</p>"
            for p in summary_paragraphs if p.strip()
        )
        summary_html = f"""
    <div class="chapter-summary">
        <h3>Chapter Summary</h3>
        {summary_content}
    </div>"""

    # Format transcript - split into paragraphs for readability
    transcript_text = chapter.transcript
    # Split long transcript into paragraphs (roughly every 500 chars at sentence boundaries)
    transcript_paragraphs = _split_into_paragraphs(transcript_text)
    transcript_html = "\n".join(
        f"<p>{_escape_html(p)}</p>"
        for p in transcript_paragraphs if p.strip()
    )

    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{_escape_html(chapter.title)}</title>
    <link rel="stylesheet" type="text/css" href="style/styles.css"/>
</head>
<body>
    <h1>Chapter {index + 1}: {_escape_html(chapter.title)}</h1>

    <p class="timestamp">{timestamp}</p>

    {summary_html}

    <hr/>

    <div class="transcript">
        <h2>Transcript</h2>
        {transcript_html}
    </div>
</body>
</html>"""

    epub_chapter = epub.EpubHtml(
        title=f"Chapter {index + 1}: {chapter.title}",
        file_name=f"chapter_{index + 1}.xhtml",
        lang="en",
    )
    epub_chapter.content = content
    epub_chapter.add_item(css)

    return epub_chapter


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _split_into_paragraphs(text: str, target_length: int = 500) -> list[str]:
    """Split text into paragraphs at sentence boundaries."""
    if len(text) <= target_length:
        return [text]

    paragraphs = []
    current = ""

    # Split by sentences (roughly)
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sentence in sentences:
        if len(current) + len(sentence) > target_length and current:
            paragraphs.append(current.strip())
            current = sentence
        else:
            current += " " + sentence if current else sentence

    if current.strip():
        paragraphs.append(current.strip())

    return paragraphs
