"""Knowledge ingest engine — process YouTube, PDF, audio, web, markdown.

Downloads, transcribes, extracts text, chunks, embeds, and indexes into
the vector store. Reports progress via callback for real-time UI updates.
"""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from core.knowledge.chunker import chunk_markdown
from core.knowledge.sources import source_id
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
    duration: int = 0
    language: str = ""
    media_path: str = ""
    thumbnail_path: str = ""
    transcript: str = ""


ProgressCallback = Callable[[int, str], None]  # (percent, message)


def detect_source_type(source: str) -> str:
    """Auto-detect content type from URL or file extension."""
    source_lower = source.lower()

    # YouTube URLs
    if any(domain in source_lower for domain in ["youtube.com", "youtu.be"]):
        return "youtube"

    # Video: a URL or file path ending in a video container extension.
    # Checked *before* the generic web fallback so a non-youtube CDN clip
    # (https://.../clip.mp4) resolves to "video", per PR1 spec Task 2.3.
    ext = Path(source.split("?", 1)[0]).suffix.lower()
    if ext in IngestEngine.VIDEO_EXTS:
        return "video"

    # Web URLs (no recognised media extension)
    if source_lower.startswith(("http://", "https://")):
        return "web"

    if ext == ".pdf":
        return "pdf"
    if ext in (".mp3", ".wav", ".m4a", ".ogg", ".flac"):
        return "audio"
    if ext in (".md", ".txt", ".rst"):
        return "markdown"

    return "unknown"


class IngestEngine:
    """Processes content from various sources into the vector store."""

    VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".avi")

    def __init__(self, store: VectorStore, media_dir: str | Path = "", registry=None) -> None:
        self._store = store
        self._registry = registry
        self._media_dir = Path(media_dir) if media_dir else Path.home() / ".arkaos" / "media"
        self._media_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def detect_source_type(source: str) -> str:
        """Detect the source type for a URL or file path (class-level alias)."""
        return detect_source_type(source)

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
            "video": self._process_video,
            "web": self._process_web,
            "markdown": self._process_markdown,
        }

        processor = processors.get(source_type)
        if not processor:
            return IngestResult(source=source, source_type=source_type, error=f"Unsupported type: {source_type}", success=False)

        try:
            text, title, extra = self._invoke_processor(processor, source, progress)
        except Exception as e:
            self._register_failure(source, source_type, str(e))
            return IngestResult(source=source, source_type=source_type, error=str(e), success=False)

        if not text or len(text.strip()) < 50:
            self._register_failure(source, source_type, "Extracted text too short")
            return IngestResult(source=source, source_type=source_type, error="Extracted text too short", success=False)

        # Chunk and index
        progress(75, "Chunking content...")
        chunks = chunk_markdown(text, max_tokens=512, source=source)
        total_chunks = len(chunks)

        if total_chunks == 0:
            progress(100, "No chunks to index")
            empty = self._make_result(source, source_type, text, title, 0, extra)
            self._register_success(empty)
            return empty

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

        result = self._make_result(source, source_type, text, title, count, extra)
        self._register_success(result)
        return result

    @staticmethod
    def _invoke_processor(
        processor: Callable, source: str, progress: ProgressCallback
    ) -> tuple[str, str, dict]:
        """Call a processor, normalizing 2-tuple and 3-tuple returns."""
        out = processor(source, progress)
        if len(out) == 3:
            return out[0], out[1], out[2] or {}
        return out[0], out[1], {}

    @staticmethod
    def _make_result(
        source: str, source_type: str, text: str, title: str,
        count: int, extra: dict,
    ) -> IngestResult:
        """Assemble a successful IngestResult including media metadata."""
        return IngestResult(
            source=source, source_type=source_type, text_length=len(text),
            chunks_created=count, title=title, success=True, transcript=text,
            duration=int(extra.get("duration", 0)),
            language=extra.get("language", ""),
            media_path=extra.get("media_path", ""),
            thumbnail_path=extra.get("thumbnail_path", ""),
        )

    def _register_success(self, result: IngestResult) -> None:
        """Persist a successful ingest to the source registry, if present."""
        if self._registry is None:
            return
        self._registry.upsert(
            result.source, type=result.source_type, title=result.title,
            duration=result.duration, language=result.language,
            thumbnail_path=result.thumbnail_path, media_path=result.media_path,
            transcript=result.transcript, chunk_count=result.chunks_created,
            status="ready",
        )

    def _register_failure(self, source: str, stype: str, error: str) -> None:
        """Persist a failed ingest to the source registry, if present."""
        if self._registry is None:
            return
        self._registry.upsert(source, type=stype, status="failed", error=error)

    def _process_youtube(self, url: str, progress: ProgressCallback) -> tuple[str, str, dict]:
        """Download a YouTube video (kept as media) and transcribe it.

        Phase 1: Fetch info (title, duration, language, thumbnail).
        Phase 2: Download best video+audio merged to mp4 (kept as media).
        Phase 3: Extract a WAV audio track for transcription.
        Phase 4: Transcribe. Returns (text, title, extra-metadata).
        """
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp")

        progress(2, "Phase 1/4 — Fetching video info...")
        info = self._youtube_info(url, progress)
        title = info.get("title", "YouTube Video")

        progress(8, "Phase 2/4 — Downloading video...")
        video_path = self._download_video(url, progress)

        progress(40, "Phase 3/4 — Extracting audio from video...")
        audio_path = self._extract_audio(video_path)

        progress(50, "Phase 4/4 — Transcribing audio (this may take a while)...")
        text = self._transcribe_audio(str(audio_path))
        if not text or len(text.strip()) < 20:
            raise RuntimeError("Transcription produced no usable text")
        progress(70, f"Phase 4/4 — Transcribed: {len(text.split())} words")

        return text, title, self._youtube_extra(info, video_path)

    @staticmethod
    def _youtube_extra(info: dict, video_path: Path) -> dict:
        """Build the extra-metadata dict from yt-dlp info + saved video."""
        return {
            "duration": int(info.get("duration") or 0),
            "language": info.get("language") or "",
            "thumbnail_path": info.get("thumbnail") or "",
            "media_path": str(video_path),
        }

    def _youtube_info(self, url: str, progress: ProgressCallback) -> dict:
        """Fetch YouTube metadata without downloading."""
        import yt_dlp
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                progress(5, f"Phase 1/4 — Found: {info.get('title')}")
                return info
        except Exception as e:
            raise RuntimeError(f"YouTube access failed: {str(e)[:200]}")

    def _download_video(self, url: str, progress: ProgressCallback) -> Path:
        """Download best video+audio merged to mp4, keyed by stable id."""
        import yt_dlp
        stable_id = source_id(url)
        out = self._media_dir / stable_id
        ydl_opts = {
            "format": "bestvideo*+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": str(out) + ".%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._dl_hook(progress)],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        return self._media_dir / f"{stable_id}.mp4"

    @staticmethod
    def _dl_hook(progress: ProgressCallback) -> Callable:
        """Build a yt-dlp progress hook mapping download % to 8-38%."""
        def hook(d: dict) -> None:
            if d.get("status") != "downloading":
                return
            ratio = d.get("downloaded_bytes", 0) / max(d.get("total_bytes", 1), 1)
            progress(8 + int(ratio * 30),
                     f"Phase 2/4 — Downloading... {d.get('_percent_str', '').strip()}")
        return hook

    def _extract_audio(self, video_path: Path) -> Path:
        """Extract a 16kHz mono WAV track from a video via ffmpeg."""
        audio_path = video_path.with_suffix(".wav")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-vn",
             "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
             str(audio_path)],
            check=True, capture_output=True,
        )
        return audio_path

    def _process_video(self, path: str, progress: ProgressCallback) -> tuple[str, str, dict]:
        """Ingest a local video file; the video itself is the media."""
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"Video not found: {path}")
        progress(30, "Transcribing video...")
        text = self._transcribe_audio(str(filepath))
        title = filepath.stem.replace("-", " ").replace("_", " ")
        return text, title, {"media_path": str(filepath)}

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
