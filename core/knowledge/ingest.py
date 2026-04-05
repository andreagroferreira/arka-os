"""Knowledge ingest engine — process YouTube, PDF, audio, web, markdown.

Downloads, transcribes, extracts text, chunks, embeds, and indexes into
the vector store. Reports progress via callback for real-time UI updates.
"""

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from core.knowledge.chunker import chunk_markdown
from core.knowledge.vector_store import VectorStore


@dataclass
class IngestResult:
    """Result of an ingest operation."""
    source: str
    source_type: str
    text_length: int = 0
    chunks_created: int = 0
    title: str = ""
    error: str = ""
    success: bool = True


ProgressCallback = Callable[[int, str], None]  # (percent, message)


def detect_source_type(source: str) -> str:
    """Auto-detect content type from URL or file extension."""
    source_lower = source.lower()

    # YouTube URLs
    if any(domain in source_lower for domain in ["youtube.com", "youtu.be"]):
        return "youtube"

    # Web URLs
    if source_lower.startswith(("http://", "https://")):
        return "web"

    # File extensions
    ext = Path(source).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"):
        return "audio"
    if ext in (".md", ".txt", ".rst"):
        return "markdown"

    return "unknown"


class IngestEngine:
    """Processes content from various sources into the vector store."""

    def __init__(self, store: VectorStore, media_dir: str | Path = "") -> None:
        self._store = store
        self._media_dir = Path(media_dir) if media_dir else Path.home() / ".arkaos" / "media"
        self._media_dir.mkdir(parents=True, exist_ok=True)

    def ingest(
        self,
        source: str,
        source_type: str = "",
        on_progress: Optional[ProgressCallback] = None,
        metadata: dict | None = None,
    ) -> IngestResult:
        """Ingest content from any supported source.

        Args:
            source: URL or file path.
            source_type: youtube, pdf, audio, web, markdown. Auto-detected if empty.
            on_progress: Callback(percent, message) for progress updates.
            metadata: Extra metadata to attach to indexed chunks.
        """
        if not source_type:
            source_type = detect_source_type(source)

        progress = on_progress or (lambda p, m: None)
        progress(0, f"Starting {source_type} ingest...")

        processors = {
            "youtube": self._process_youtube,
            "pdf": self._process_pdf,
            "audio": self._process_audio,
            "web": self._process_web,
            "markdown": self._process_markdown,
        }

        processor = processors.get(source_type)
        if not processor:
            return IngestResult(source=source, source_type=source_type, error=f"Unsupported type: {source_type}", success=False)

        try:
            text, title = processor(source, progress)
        except Exception as e:
            return IngestResult(source=source, source_type=source_type, error=str(e), success=False)

        if not text or len(text.strip()) < 50:
            return IngestResult(source=source, source_type=source_type, error="Extracted text too short", success=False)

        # Chunk and index
        progress(75, "Chunking content...")
        chunks = chunk_markdown(text, max_tokens=512, source=source)
        total_chunks = len(chunks)

        if total_chunks == 0:
            progress(100, "No chunks to index")
            return IngestResult(source=source, source_type=source_type, text_length=len(text), chunks_created=0, title=title, success=True)

        # Index in batches with granular progress (85→99%)
        texts = [c.text for c in chunks]
        headings = [c.heading for c in chunks]
        batch_size = 10
        count = 0

        for i in range(0, total_chunks, batch_size):
            batch_end = min(i + batch_size, total_chunks)
            pct = 85 + int((i / total_chunks) * 14)
            progress(pct, f"Embedding & indexing chunks {i + 1}—{batch_end} of {total_chunks}...")

            batch_count = self._store.index_chunks(
                texts=texts[i:batch_end],
                headings=headings[i:batch_end] if headings else None,
                source=source,
                metadata={"type": source_type, "title": title, **(metadata or {})},
            )
            count += batch_count

        progress(100, f"Done — {count} chunks indexed")

        # Record token usage in budget
        try:
            from core.budget.manager import BudgetManager
            from pathlib import Path as BudgetPath
            budget_mgr = BudgetManager(storage_path=BudgetPath.home() / ".arkaos" / "budget-usage.json")
            tokens_est = len(text) // 4  # ~1 token per 4 chars
            budget_mgr.record_usage(
                agent_id="kb-indexer",
                tokens=tokens_est,
                tier=2,
                department="kb",
                description=f"ingest-{source_type}: {source[:60]}",
            )
        except Exception:
            pass

        return IngestResult(
            source=source,
            source_type=source_type,
            text_length=len(text),
            chunks_created=count,
            title=title,
            success=True,
        )

    def _process_youtube(self, url: str, progress: ProgressCallback) -> tuple[str, str]:
        """Download YouTube video and transcribe audio.

        5 distinct phases with clear progress:
        Phase 1: Fetch video info (0-5%)
        Phase 2: Download video (5-25%)
        Phase 3: Extract audio (25-35%)
        Phase 4: Transcribe audio (35-65%)
        Phase 5: Return text for chunking/indexing (handled by caller, 75-100%)
        """
        try:
            import yt_dlp
        except ImportError:
            raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp")

        # === Phase 1: Fetch video info ===
        progress(2, "Phase 1/4 — Fetching video info...")
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "YouTube Video")
                duration = info.get("duration", 0)
                progress(5, f"Phase 1/4 — Found: {title} ({duration}s)")
        except Exception as e:
            raise RuntimeError(f"YouTube access failed: {str(e)[:200]}")

        # === Phase 2: Download video + extract audio ===
        progress(8, f"Phase 2/4 — Downloading video...")
        audio_path = str(self._media_dir / "yt_audio.wav")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(self._media_dir / "yt_audio.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "16",
            }],
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [lambda d: progress(
                8 + int((d.get("downloaded_bytes", 0) / max(d.get("total_bytes", 1), 1)) * 17),
                f"Phase 2/4 — Downloading... {d.get('_percent_str', '').strip()}"
            ) if d.get("status") == "downloading" else None],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        # === Phase 3: Extract audio (FFmpeg post-processing) ===
        progress(28, "Phase 3/4 — Extracting audio from video...")

        # Verify audio file exists
        if not os.path.exists(audio_path):
            # Try to find the downloaded file with different extension
            for ext in ["wav", "m4a", "webm", "mp3", "opus"]:
                alt = str(self._media_dir / f"yt_audio.{ext}")
                if os.path.exists(alt):
                    audio_path = alt
                    break
            else:
                raise RuntimeError("Audio extraction failed — no output file found")

        audio_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        progress(35, f"Phase 3/4 — Audio extracted ({audio_size_mb:.1f} MB)")

        # === Phase 4: Transcribe audio ===
        progress(38, "Phase 4/4 — Transcribing audio (this may take a while)...")
        text = self._transcribe_audio(audio_path)

        if not text or len(text.strip()) < 20:
            raise RuntimeError("Transcription produced no usable text")

        word_count = len(text.split())
        progress(70, f"Phase 4/4 — Transcribed: {word_count} words")

        # Cleanup audio file
        try:
            os.remove(audio_path)
        except OSError:
            pass

        return text, title

    def _process_pdf(self, path: str, progress: ProgressCallback) -> tuple[str, str]:
        """Extract text from PDF."""
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")

        progress(10, "Opening PDF...")
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        pages_text = []
        with pdfplumber.open(filepath) as pdf:
            total_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pages_text.append(text)
                pct = 10 + int((i / total_pages) * 60)
                progress(pct, f"Extracting page {i + 1}/{total_pages}...")

        title = filepath.stem.replace("-", " ").replace("_", " ")
        return "\n\n".join(pages_text), title

    def _process_audio(self, path: str, progress: ProgressCallback) -> tuple[str, str]:
        """Transcribe audio file."""
        progress(10, "Loading audio...")
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"Audio not found: {path}")

        progress(20, "Transcribing audio...")
        text = self._transcribe_audio(str(filepath))
        title = filepath.stem.replace("-", " ").replace("_", " ")
        return text, title

    def _process_web(self, url: str, progress: ProgressCallback) -> tuple[str, str]:
        """Scrape web page content."""
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            raise RuntimeError("beautifulsoup4 and requests not installed. Run: pip install beautifulsoup4 requests")

        progress(10, "Fetching page...")
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (ArkaOS Knowledge Indexer)"
        })
        resp.raise_for_status()

        progress(40, "Parsing content...")
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Get title
        title = soup.title.string if soup.title else url

        # Get main content (article > main > body)
        main = soup.find("article") or soup.find("main") or soup.find("body")
        text = main.get_text(separator="\n\n", strip=True) if main else soup.get_text(separator="\n\n", strip=True)

        # Clean up whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text, title

    def _process_markdown(self, path: str, progress: ProgressCallback) -> tuple[str, str]:
        """Read markdown/text file directly."""
        progress(10, "Reading file...")
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {path}")

        text = filepath.read_text(encoding="utf-8")
        title = filepath.stem.replace("-", " ").replace("_", " ")
        return text, title

    def _transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio using faster-whisper (or fallback)."""
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(audio_path, beam_size=5)
            return " ".join(segment.text for segment in segments)
        except ImportError:
            pass

        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(audio_path)
            return result["text"]
        except ImportError:
            raise RuntimeError(
                "No transcription engine available. Install one:\n"
                "  pip install faster-whisper   (recommended, lighter)\n"
                "  pip install openai-whisper   (original, heavier)"
            )
