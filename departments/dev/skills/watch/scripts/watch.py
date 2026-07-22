#!/usr/bin/env python3
"""/watch entry point: download video, extract frames, parse transcript.

Prints a markdown report to stdout listing frame paths + transcript. The
agent then Reads each frame path to see the video.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from download import download, fetch_captions, is_url  # noqa: E402
from frames import (  # noqa: E402
    MAX_FPS,
    auto_fps,
    auto_fps_focus,
    extract_at_timestamps,
    extract_keyframes,
    extract_scene_or_uniform,
    format_time,
    get_metadata,
    merge_frames,
    parse_time,
    parse_timestamps,
)
from transcribe import filter_range, format_transcript, parse_vtt  # noqa: E402
from whisper import load_api_key, transcribe_video  # noqa: E402

from config import frame_cap, get_config, record_telemetry  # noqa: E402


@dataclass
class Run:
    """Mutable state threaded through the watch stages."""

    args: argparse.Namespace
    work: Path
    detail: str
    max_frames: int | None
    budget_cap: int
    cue_timestamps: list[float]
    url_source: bool = False
    dl: dict = field(
        default_factory=lambda: {"subtitle_path": None, "info": {}, "downloaded": False}
    )
    video_path: str | None = None
    meta: dict = field(default_factory=dict)
    segments: list[dict] = field(default_factory=list)
    transcript_text: str | None = None
    transcript_source: str | None = None
    start_sec: float | None = None
    end_sec: float | None = None
    effective_start: float = 0.0
    effective_end: float = 0.0
    effective_duration: float = 0.0
    focused: bool = False
    fps: float = 0.0
    target: int = 0
    frames: list[dict] = field(default_factory=list)
    frame_meta: dict = field(
        default_factory=lambda: {
            "engine": "none", "candidate_count": 0, "selected_count": 0, "fallback": False,
        }
    )
    cue_frames: list[dict] = field(default_factory=list)
    cue_meta: dict = field(default_factory=dict)
    detail_budget: int | None = None

    @property
    def full_duration(self) -> float:
        return float(self.meta.get("duration_seconds") or 0.0)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="watch",
        description="Download a video, extract auto-scaled frames, and surface the transcript.",
    )
    ap.add_argument("source", help="Video URL or local file path")
    ap.add_argument("--max-frames", type=int, default=None, help="Override frame cap")
    ap.add_argument(
        "--resolution", type=int, default=512, help="Frame width in pixels (default 512)"
    )
    ap.add_argument("--fps", type=float, default=None, help="Override auto-fps")
    ap.add_argument(
        "--detail",
        choices=["transcript", "efficient", "balanced", "token-burner"],
        default=None,
        help="Fidelity/speed dial: transcript (no frames), efficient (fast keyframes, cap 50), "
             "balanced (scene, cap 100), token-burner (scene, uncapped).",
    )
    ap.add_argument(
        "--timestamps",
        type=str,
        default=None,
        help="Comma-separated absolute timestamps (SS, MM:SS, HH:MM:SS) to grab a frame at, "
             "e.g. transcript-flagged 'look here' moments. Added on top of the detail frames "
             "(reserved against the cap); with --detail transcript these become the only frames.",
    )
    ap.add_argument("--start", type=str, default=None, help="Range start (SS, MM:SS, or HH:MM:SS)")
    ap.add_argument("--end", type=str, default=None, help="Range end (SS, MM:SS, or HH:MM:SS)")
    ap.add_argument("--out-dir", type=str, default=None, help="Working directory (default: tmp)")
    ap.add_argument(
        "--no-whisper",
        action="store_true",
        help="Disable Whisper fallback. Report frames-only if no captions available.",
    )
    ap.add_argument(
        "--whisper",
        choices=["groq", "openai"],
        default=None,
        help="Force a specific Whisper backend. Default: prefer Groq, fall back to OpenAI.",
    )
    ap.add_argument(
        "--no-dedup",
        action="store_true",
        help="Disable near-duplicate frame removal. Keeps visually identical "
             "frames (static screen recordings, held slides) instead of collapsing them.",
    )
    return ap


def prepare_run(args: argparse.Namespace) -> Run:
    config = get_config()
    detail = args.detail or str(config["detail"])
    configured_cap = frame_cap(detail)
    max_frames = args.max_frames if args.max_frames is not None else configured_cap
    if max_frames is not None and max_frames < 1:
        raise SystemExit("--max-frames must be greater than zero")
    budget_cap = max_frames if max_frames is not None else 100
    cue_timestamps = parse_timestamps(args.timestamps)

    if args.out_dir:
        work = Path(args.out_dir).expanduser().resolve()
    else:
        work = Path(tempfile.mkdtemp(prefix="watch-"))
    work.mkdir(parents=True, exist_ok=True)
    print(f"[watch] working dir: {work}", file=sys.stderr)

    return Run(
        args=args,
        work=work,
        detail=detail,
        max_frames=max_frames,
        budget_cap=budget_cap,
        cue_timestamps=cue_timestamps,
        url_source=is_url(args.source),
    )


def captions_stage(run: Run) -> None:
    """For URLs, try native captions before any download."""
    if not run.url_source:
        return
    print("[watch] checking metadata/captions via yt-dlp…", file=sys.stderr)
    run.dl = fetch_captions(run.args.source, run.work / "download")
    if run.dl.get("subtitle_path"):
        try:
            run.segments = parse_vtt(run.dl["subtitle_path"])
            run.transcript_text = format_transcript(run.segments)
            run.transcript_source = "captions"
        except Exception as exc:
            print(f"[watch] subtitle parse failed: {exc}", file=sys.stderr)
            run.segments = []


def obtain_video_stage(run: Run) -> None:
    """Download (or point at) the media the run needs, then probe metadata.

    --timestamps needs the video for frame grabs, so it overrides the
    transcript-mode download skip (and forces a full, not audio-only, fetch).
    """
    audio_only = run.detail == "transcript" and not run.cue_timestamps
    if run.detail == "transcript" and run.segments and not run.cue_timestamps:
        run.video_path = None
    else:
        if run.url_source:
            print(
                "[watch] downloading audio via yt-dlp…" if audio_only
                else "[watch] downloading video via yt-dlp…",
                file=sys.stderr,
            )
            run.dl = download(run.args.source, run.work / "download", audio_only=audio_only)
        else:
            print("[watch] using local file…", file=sys.stderr)
            run.dl = download(run.args.source, run.work / "download")
        run.video_path = run.dl["video_path"]

    run.meta = get_metadata(run.video_path) if run.video_path else {
        "duration_seconds": float((run.dl.get("info") or {}).get("duration") or 0),
        "width": None,
        "height": None,
        "codec": None,
        "has_audio": False,
    }


def range_stage(run: Run) -> None:
    """Validate --start/--end and derive the effective extraction window."""
    args = run.args
    run.start_sec = parse_time(args.start)
    run.end_sec = parse_time(args.end)
    full_duration = run.full_duration

    if run.start_sec is not None and run.start_sec < 0:
        raise SystemExit("--start must be non-negative")
    if run.end_sec is not None and run.start_sec is not None and run.end_sec <= run.start_sec:
        raise SystemExit("--end must be greater than --start")
    if full_duration > 0 and run.start_sec is not None and run.start_sec >= full_duration:
        raise SystemExit(
            f"--start {run.start_sec:.1f}s is past end of video ({full_duration:.1f}s)"
        )

    run.effective_start = run.start_sec if run.start_sec is not None else 0.0
    run.effective_end = run.end_sec if run.end_sec is not None else full_duration
    run.effective_duration = max(0.0, run.effective_end - run.effective_start)
    run.focused = run.start_sec is not None or run.end_sec is not None

    if run.focused:
        run.fps, run.target = auto_fps_focus(run.effective_duration, max_frames=run.budget_cap)
    else:
        run.fps, run.target = auto_fps(run.effective_duration, max_frames=run.budget_cap)
    if args.fps is not None:
        run.fps = min(args.fps, MAX_FPS)
        run.target = max(1, round(run.fps * run.effective_duration))

    if run.segments and run.focused:
        run.segments = filter_range(run.segments, run.start_sec, run.end_sec)
        run.transcript_text = format_transcript(run.segments)


def frames_stage(run: Run) -> None:
    """Extract cue frames first (pinned against the cap), then detail frames."""
    args = run.args
    scope = (
        f"{format_time(run.effective_start)}-{format_time(run.effective_end)} "
        f"({run.effective_duration:.1f}s)"
        if run.focused else f"full {run.effective_duration:.1f}s"
    )

    # Transcript cues are pinned: extracted first and counted against the cap so
    # the detail engine never evicts the moments the user explicitly asked for.
    if run.cue_timestamps and run.video_path:
        run.cue_frames, run.cue_meta = extract_at_timestamps(
            run.video_path,
            run.work / "frames",
            run.cue_timestamps,
            resolution=args.resolution,
            max_frames=run.max_frames,
            start_seconds=run.start_sec,
            end_seconds=run.end_sec,
        )
        if run.cue_meta.get("dropped_out_of_window"):
            print(
                f"[watch] {run.cue_meta['dropped_out_of_window']} cue timestamp(s) outside the "
                "focus range — dropped",
                file=sys.stderr,
            )

    run.detail_budget = (
        run.max_frames if run.max_frames is None else max(0, run.max_frames - len(run.cue_frames))
    )
    if run.detail != "transcript" and run.video_path and run.detail_budget != 0:
        cap_label = "unlimited" if run.detail_budget is None else str(run.detail_budget)
        engine_label = "keyframes" if run.detail == "efficient" else "scene-aware frames"
        print(
            f"[watch] extracting {engine_label} over {scope} "
            f"(target {run.target}, cap {cap_label})…",
            file=sys.stderr,
        )
        if run.detail == "efficient":
            run.frames, run.frame_meta = extract_keyframes(
                run.video_path,
                run.work / "frames",
                resolution=args.resolution,
                max_frames=run.detail_budget,
                start_seconds=run.start_sec,
                end_seconds=run.end_sec,
                dedup=not args.no_dedup,
            )
        else:  # balanced, token-burner
            run.frames, run.frame_meta = extract_scene_or_uniform(
                run.video_path,
                run.work / "frames",
                fps=run.fps,
                target_frames=run.target,
                resolution=args.resolution,
                max_frames=run.detail_budget,
                start_seconds=run.start_sec,
                end_seconds=run.end_sec,
                dedup=not args.no_dedup,
            )

    if run.cue_frames:
        run.frames = merge_frames(run.frames, run.cue_frames)


def transcript_stage(run: Run) -> None:
    """Late captions parse, then the Whisper fallback when audio exists."""
    args = run.args
    if not run.segments and run.dl.get("subtitle_path"):
        try:
            all_segments = parse_vtt(run.dl["subtitle_path"])
            run.segments = (
                filter_range(all_segments, run.start_sec, run.end_sec)
                if run.focused else all_segments
            )
            run.transcript_text = format_transcript(run.segments)
            run.transcript_source = "captions"
        except Exception as exc:
            print(f"[watch] subtitle parse failed: {exc}", file=sys.stderr)

    if not run.segments and not args.no_whisper and run.video_path and run.meta.get("has_audio"):
        backend, api_key = load_api_key(args.whisper)
        if backend and api_key:
            try:
                all_segments, used_backend = transcribe_video(
                    run.video_path,
                    run.work / "audio.mp3",
                    backend=backend,
                    api_key=api_key,
                )
                run.segments = (
                    filter_range(all_segments, run.start_sec, run.end_sec)
                    if run.focused else all_segments
                )
                run.transcript_text = format_transcript(run.segments)
                run.transcript_source = f"whisper ({used_backend})"
            except SystemExit as exc:
                print(f"[watch] whisper fallback failed: {exc}", file=sys.stderr)
        else:
            hint = (
                f"--whisper {args.whisper} was set but the matching API key is missing"
                if args.whisper else
                "no subtitles and no Whisper API key found"
            )
            print(
                f"[watch] {hint} — add one with `/arka keys` (or run "
                f"`python3 {SCRIPT_DIR / 'setup.py'}`) to enable the Whisper fallback",
                file=sys.stderr,
            )
    elif not run.segments and run.video_path and not run.meta.get("has_audio"):
        print("[watch] no audio stream found — proceeding without transcription", file=sys.stderr)


def print_header(run: Run) -> None:
    args = run.args
    info = run.dl.get("info") or {}
    print()
    print("# watch: video report")
    print()
    print(f"- **Source:** {args.source}")
    if info.get("title"):
        print(f"- **Title:** {info['title']}")
    if info.get("uploader"):
        print(f"- **Uploader:** {info['uploader']}")
    print(f"- **Duration:** {format_time(run.full_duration)} ({run.full_duration:.1f}s)")
    if run.focused:
        print(
            f"- **Focus range:** {format_time(run.effective_start)} → "
            f"{format_time(run.effective_end)} ({run.effective_duration:.1f}s)"
        )
    if run.meta.get("width") and run.meta.get("height"):
        print(
            f"- **Resolution:** {run.meta['width']}x{run.meta['height']} "
            f"({run.meta.get('codec') or 'unknown codec'})"
        )
    range_mode = "focused" if run.focused else "full"
    print(f"- **Detail:** {run.detail}")
    detail_count = run.frame_meta.get("selected_count", 0)
    if run.detail != "transcript":
        cap_label = "unlimited" if run.detail_budget is None else str(run.detail_budget)
        engine = run.frame_meta.get("engine", "scene")
        fallback = " with uniform fallback" if run.frame_meta.get("fallback") else ""
        deduped = run.frame_meta.get("deduped_count", 0)
        plural = "s" if deduped != 1 else ""
        dedup_note = f", {deduped} near-duplicate{plural} dropped" if deduped else ""
        candidates = run.frame_meta.get("candidate_count", detail_count)
        print(
            f"- **Frames:** {detail_count} selected from {candidates} candidates "
            f"({engine}{fallback}{dedup_note}, {range_mode} range, "
            f"budget {run.target}, cap {cap_label})"
        )
    elif not run.cue_frames:
        print("- **Frames:** skipped (transcript detail)")
    if run.cue_frames:
        dropped = run.cue_meta.get("dropped_out_of_window", 0)
        drop_note = f", {dropped} dropped outside range" if dropped else ""
        print(
            f"- **Cue frames:** {len(run.cue_frames)} at transcript-flagged timestamps "
            f"(transcript-cue{drop_note})"
        )
    if run.frames:
        print(f"- **Frame size:** max {args.resolution}px wide, max 1998px tall")
    if run.segments:
        in_range = " in range" if run.focused else ""
        print(
            f"- **Transcript:** {len(run.segments)} segments{in_range} "
            f"(via {run.transcript_source or 'captions'})"
        )
    else:
        print("- **Transcript:** none available")
    print_warnings(run)


def print_warnings(run: Run) -> None:
    if run.detail == "token-burner" and len(run.frames) > 250:
        print()
        print(
            f"> **Warning:** token-burner detail selected {len(run.frames)} frames. "
            "This may use a large number of image tokens."
        )

    long_uncapped = run.detail not in ("transcript", "token-burner")
    if not run.focused and run.full_duration > 600 and long_uncapped:
        mins = int(run.full_duration // 60)
        print()
        print(
            f"> **Warning:** This is a {mins}-minute video. Frame coverage is sparse "
            f"at this length under `{run.detail}` detail — its cap spreads thin across "
            "the full clip. For better results, re-run with "
            "`--start HH:MM:SS --end HH:MM:SS` to zoom into a section, or use "
            "`--detail token-burner` to keep every scene-change frame across the whole video."
        )


def print_frames_section(run: Run) -> None:
    print()
    print("## Frames")
    print()
    if run.frames:
        print(f"Frames live at: `{run.work / 'frames'}`")
        print()
        print(
            "**Read each frame path below with the Read tool to view the image.** "
            "Frames are in chronological order; `t=MM:SS` is the absolute timestamp "
            "in the source video."
        )
        print()
        for frame in run.frames:
            reason = frame.get("reason", "selected")
            print(
                f"- `{frame['path']}` "
                f"(t={format_time(frame['timestamp_seconds'])}, reason={reason})"
            )
    else:
        print("_No frames extracted._")


def print_transcript_section(run: Run) -> None:
    print()
    print("## Transcript")
    print()
    if run.transcript_text:
        label = run.transcript_source or "captions"
        if run.focused:
            print(
                f"_Source: {label}. Filtered to {format_time(run.effective_start)} → "
                f"{format_time(run.effective_end)}:_"
            )
        else:
            print(f"_Source: {label}._")
        print()
        print("```")
        print(run.transcript_text)
        print("```")
    elif run.detail == "transcript":
        print(
            "_No transcript available at transcript detail. Captions were missing and Whisper was "
            "unavailable or failed, so there is no visual fallback here. Re-run with "
            "`--detail balanced` for frames._"
        )
    elif run.focused and run.dl.get("subtitle_path"):
        print(
            f"_No transcript lines fell inside {format_time(run.effective_start)} → "
            f"{format_time(run.effective_end)}._"
        )
    else:
        print(
            "_No transcript available — proceed with frames only. "
            "Captions were missing and the Whisper fallback was unavailable "
            "(no API key set, or `--no-whisper` was used). "
            "Add a key with `/arka keys` to enable Whisper, then re-run._"
        )

    print()
    print("---")
    print(f"_Work dir: `{run.work}` — delete when done._")


def estimate_image_tokens(frame_count: int, width: int) -> int:
    """Anthropic's (width x height) / 750 with an assumed 16:9 aspect."""
    return frame_count * round(width * width * 9 / 16 / 750)


def telemetry_stage(run: Run) -> None:
    record_telemetry({
        "source_kind": "url" if run.url_source else "file",
        "detail": run.detail,
        "focused": run.focused,
        "duration_seconds": round(run.full_duration, 1),
        "frames": len(run.frames),
        "est_image_tokens": estimate_image_tokens(len(run.frames), run.args.resolution),
        "transcript_source": run.transcript_source,
        "transcript_segments": len(run.segments),
    })


def main() -> int:
    args = build_parser().parse_args()
    run = prepare_run(args)
    captions_stage(run)
    obtain_video_stage(run)
    range_stage(run)
    frames_stage(run)
    transcript_stage(run)
    print_header(run)
    print_frames_section(run)
    print_transcript_section(run)
    telemetry_stage(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
