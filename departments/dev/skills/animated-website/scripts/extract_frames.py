#!/usr/bin/env python3
"""
Extract frames from video and convert to optimized WebP for scroll animation.

Extracts evenly-spaced frames from an MP4 video, converts to WebP at dual
resolutions (desktop + mobile), and generates a manifest.json with metadata.

Usage:
    python3 extract_frames.py \
        --input /path/to/video.mp4 \
        --output animated-sites/my-project/frames

    Custom frame count:        --frames 120
    Custom quality/resolution: --quality 75 --desktop-res 1920x1080 --mobile-res 960x540
    Single variant:            --desktop-only  (or --mobile-only)

Environment:
    Requires ffmpeg and ffprobe installed (brew install ffmpeg).
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DESKTOP_BUDGET_MB = 10
MOBILE_BUDGET_MB = 5
FFMPEG_TIMEOUT_S = 300


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract frames from video for scroll animation"
    )
    _add_io_args(parser)
    _add_encoding_args(parser)
    return parser.parse_args()


def _add_io_args(parser):
    parser.add_argument("--input", required=True, help="Path to source MP4 video file")
    parser.add_argument("--output", required=True, help="Output directory for extracted frames")
    parser.add_argument("--desktop-only", action="store_true", help="Skip mobile frame generation")
    parser.add_argument("--mobile-only", action="store_true", help="Skip desktop frame generation")


def _add_encoding_args(parser):
    parser.add_argument(
        "--frames", type=int, default=0,
        help="Target frame count (default: auto-calculated from video duration)",
    )
    parser.add_argument("--quality", type=int, default=80, help="WebP quality 1-100 (default: 80)")
    parser.add_argument(
        "--desktop-res", default="1920x1080", help="Desktop frame resolution (default: 1920x1080)"
    )
    parser.add_argument(
        "--mobile-res", default="960x540", help="Mobile frame resolution (default: 960x540)"
    )


def fail(message):
    """Print an error to stderr and exit 1."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def validate_dependencies():
    """Check that ffmpeg and ffprobe are installed."""
    for cmd in ("ffmpeg", "ffprobe"):
        if not shutil.which(cmd):
            fail(f"'{cmd}' not found. Install with: brew install ffmpeg")


def validate_input(input_path):
    """Check the input file exists and looks like a video; return the resolved path."""
    p = Path(input_path).resolve()
    if not p.exists():
        fail(f"File not found: {input_path}")
    if p.stat().st_size < 1024:
        fail(f"File too small to be a video: {input_path}")
    return p


def validate_quality(quality):
    """Enforce the documented WebP quality range (1-100)."""
    if not 1 <= quality <= 100:
        fail(f"--quality must be between 1 and 100, got {quality}")


def parse_fps(fps_str):
    """Parse an ffprobe r_frame_rate value ('30/1' or '29.97') into a float."""
    if "/" in fps_str:
        num, den = fps_str.split("/")
        return float(num) / float(den) if float(den) != 0 else 30.0
    return float(fps_str)


def _run_ffprobe(input_path):
    """Run ffprobe and return the parsed JSON document."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(input_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        fail(f"ffprobe failed: {e.stderr}")
    except json.JSONDecodeError:
        fail("Could not parse ffprobe output")


def probe_video(input_path):
    """Probe the video and return duration/resolution/fps/codec metadata."""
    data = _run_ffprobe(input_path)
    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"), None
    )
    if not video_stream:
        fail("No video stream found in file")

    fps = parse_fps(video_stream.get("r_frame_rate", "30/1"))
    duration = float(data.get("format", {}).get("duration", 0))
    if duration == 0:
        duration = float(video_stream.get("duration", 0))

    return {
        "duration": round(duration, 2),
        "width": int(video_stream.get("width", 1920)),
        "height": int(video_stream.get("height", 1080)),
        "fps": round(fps, 2),
        "codec": video_stream.get("codec_name", "unknown"),
        "total_frames": round(duration * fps),
        "filename": Path(input_path).name,
    }


def calculate_optimal_frames(duration, user_override=0):
    """Calculate optimal frame count and scroll height from video duration.

    Formula: min(200, max(60, duration * 10))
    - 0-5s videos: 60-90 frames (simple reveals)
    - 5-15s: 120-150 (standard, the sweet spot)
    - 15-30s: 150-200 (complex sequences)
    - 30s+: capped at 200 (increase scroll height instead)
    """
    frame_count = user_override if user_override > 0 else min(200, max(60, int(duration * 10)))
    # Scroll height: ~3.3vh per frame, minimum 300vh, rounded to nearest 50vh
    scroll_height = round(max(300, int(frame_count * 3.3)) / 50) * 50
    return frame_count, scroll_height


def parse_resolution(res_str):
    """Parse 'WIDTHxHEIGHT' string into (width, height) tuple."""
    try:
        w, h = res_str.lower().split("x")
        return int(w), int(h)
    except (ValueError, AttributeError):
        fail(f"Invalid resolution format: {res_str}. Use WIDTHxHEIGHT.")


def has_libwebp():
    """Check if FFmpeg has libwebp encoder support."""
    result = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
    return "libwebp" in result.stdout


def _probe_duration(input_path):
    """Return the container duration in seconds (10.0 fallback)."""
    cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip()) if result.stdout.strip() else 10.0


def _build_extract_cmd(input_path, output_dir, target_fps, resolution, quality, use_libwebp):
    """Build the ffmpeg command: single-pass WebP when libwebp exists, else PNG."""
    w, h = resolution
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", f"fps={target_fps:.4f},scale={w}:{h}:flags=lanczos",
        "-an",
    ]
    if use_libwebp:
        cmd += ["-c:v", "libwebp", "-quality", str(quality), "-compression_level", "6"]
    ext = "webp" if use_libwebp else "png"
    return [*cmd, str(output_dir / f"frame-%04d.{ext}")]


def _run_ffmpeg(cmd):
    """Run ffmpeg with a hard timeout; exit 1 on any failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_S)
        if result.returncode != 0:
            fail(f"FFmpeg failed:\n{result.stderr[-500:]}")
    except subprocess.TimeoutExpired:
        fail("FFmpeg timed out (5 min limit)")


def _convert_pngs_to_webp(output_dir, quality, prefix):
    """Universal fallback: convert extracted PNGs to WebP via Pillow, then delete them."""
    try:
        from PIL import Image as PILImage
    except ImportError:
        fail(
            "Neither libwebp (FFmpeg) nor Pillow is available.\n"
            "Fix: pip install Pillow  OR  brew reinstall ffmpeg"
        )

    png_files = sorted(output_dir.glob("frame-*.png"))
    print(f"{prefix}Converting {len(png_files)} PNGs to WebP via Pillow...", file=sys.stderr)
    for png_path in png_files:
        img = PILImage.open(png_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(str(png_path.with_suffix(".webp")), "WEBP", quality=quality, method=6)
        png_path.unlink()  # Remove PNG to save disk space


def _measure_frames(output_dir, resolution, prefix):
    """Count extracted WebP frames and report sizes; exit 1 when none exist."""
    frames = sorted(output_dir.glob("frame-*.webp"))
    if not frames:
        fail(f"No frames extracted to {output_dir}")

    total_bytes = sum(f.stat().st_size for f in frames)
    avg_bytes = total_bytes // len(frames)
    print(
        f"{prefix}{len(frames)} frames extracted "
        f"({total_bytes / 1024 / 1024:.1f}MB total, {avg_bytes / 1024:.0f}KB avg per frame)",
        file=sys.stderr,
    )
    w, h = resolution
    return {
        "count": len(frames),
        "total_bytes": total_bytes,
        "avg_bytes": avg_bytes,
        "resolution": f"{w}x{h}",
    }


def extract_frames(input_path, output_dir, frame_count, resolution, quality, label=""):
    """Extract evenly-spaced frames from video as WebP.

    Strategy:
    1. If FFmpeg has libwebp: single-pass extraction to WebP (fastest)
    2. Otherwise: extract as PNG, then convert to WebP via Pillow (universal)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    duration = _probe_duration(input_path)
    target_fps = max(1, min(60, frame_count / duration))

    prefix = f"  [{label}] " if label else "  "
    use_libwebp = has_libwebp()
    encoder = "FFmpeg libwebp" if use_libwebp else "FFmpeg + Pillow"
    w, h = resolution
    print(f"{prefix}Extracting {frame_count} frames at {w}x{h} ({encoder})...", file=sys.stderr)

    cmd = _build_extract_cmd(input_path, output_dir, target_fps, resolution, quality, use_libwebp)
    _run_ffmpeg(cmd)
    if not use_libwebp:
        _convert_pngs_to_webp(output_dir, quality, prefix)

    return _measure_frames(output_dir, resolution, prefix)


def _variant_summary(info):
    """Shape one resolution variant's extraction info for the manifest."""
    return {
        "resolution": info["resolution"],
        "actual_count": info["count"],
        "total_bytes": info["total_bytes"],
        "avg_frame_bytes": info["avg_bytes"],
        "total_mb": round(info["total_bytes"] / 1024 / 1024, 2),
    }


def _source_summary(video_info):
    """Shape the source-video block of the manifest."""
    return {
        "filename": video_info["filename"],
        "duration": video_info["duration"],
        "resolution": f"{video_info['width']}x{video_info['height']}",
        "fps": video_info["fps"],
        "codec": video_info["codec"],
        "total_source_frames": video_info["total_frames"],
    }


def generate_manifest(output_dir, video_info, frame_count, scroll_height,
                      quality, desktop_info=None, mobile_info=None):
    """Generate manifest.json with full metadata."""
    manifest = {
        "source": _source_summary(video_info),
        "frames": {
            "target_count": frame_count,
            "format": "webp",
            "quality": quality,
            "naming_pattern": "frame-{NNNN}.webp",
        },
        "recommended_scroll_height": f"{scroll_height}vh",
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    if desktop_info:
        manifest["desktop"] = _variant_summary(desktop_info)
    if mobile_info:
        manifest["mobile"] = _variant_summary(mobile_info)

    manifest_path = Path(output_dir) / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n  Manifest saved to: {manifest_path}", file=sys.stderr)
    return manifest


def _print_budget_warnings(manifest):
    """Warn when a variant's payload exceeds its budget."""
    budgets = (("desktop", DESKTOP_BUDGET_MB), ("mobile", MOBILE_BUDGET_MB))
    for variant, budget_mb in budgets:
        total_mb = manifest.get(variant, {}).get("total_mb", 0)
        if total_mb > budget_mb:
            print(
                f"\n  WARNING: {variant.capitalize()} payload ({total_mb}MB) "
                f"exceeds {budget_mb}MB target.",
                file=sys.stderr,
            )
            print("  Consider: --quality 60 or --frames (lower count)", file=sys.stderr)


def print_summary(video_info, frame_count, scroll_height, manifest):
    """Print a human-readable summary."""
    err = sys.stderr
    print("\n" + "=" * 56, file=err)
    print("  VIDEO ANALYSIS", file=err)
    print("=" * 56, file=err)
    print(f"  Source:      {video_info['filename']}", file=err)
    print(f"  Duration:    {video_info['duration']}s", file=err)
    print(f"  Resolution:  {video_info['width']}x{video_info['height']}", file=err)
    print(f"  Frame Rate:  {video_info['fps']}fps", file=err)
    print(f"  Codec:       {video_info['codec']}", file=err)
    print(f"  Src Frames:  {video_info['total_frames']}", file=err)
    print("-" * 56, file=err)
    print("  EXTRACTION RESULTS", file=err)
    print("-" * 56, file=err)
    print(f"  Target:      {frame_count} frames", file=err)
    print(f"  Scroll:      {scroll_height}vh recommended", file=err)
    for variant in ("desktop", "mobile"):
        if variant in manifest:
            v = manifest[variant]
            print(
                f"  {variant.capitalize():<12} {v['actual_count']} frames "
                f"@ {v['resolution']} ({v['total_mb']}MB)",
                file=err,
            )
    print("=" * 56, file=err)
    _print_budget_warnings(manifest)


def _extract_variants(args, input_path, frame_count):
    """Extract the desktop and/or mobile frame sets per the CLI flags."""
    output_dir = Path(args.output)
    desktop_info = None
    mobile_info = None
    if not args.mobile_only:
        desktop_info = extract_frames(
            input_path, output_dir / "desktop", frame_count,
            parse_resolution(args.desktop_res), args.quality, label="desktop",
        )
    if not args.desktop_only:
        mobile_info = extract_frames(
            input_path, output_dir / "mobile", frame_count,
            parse_resolution(args.mobile_res), args.quality, label="mobile",
        )
    return desktop_info, mobile_info


def main():
    args = parse_args()
    validate_dependencies()
    validate_quality(args.quality)
    input_path = validate_input(args.input)

    print("\nProbing video...", file=sys.stderr)
    video_info = probe_video(input_path)
    frame_count, scroll_height = calculate_optimal_frames(video_info["duration"], args.frames)

    Path(args.output).mkdir(parents=True, exist_ok=True)
    desktop_info, mobile_info = _extract_variants(args, input_path, frame_count)

    manifest = generate_manifest(
        args.output, video_info, frame_count, scroll_height,
        args.quality, desktop_info, mobile_info,
    )
    print_summary(video_info, frame_count, scroll_height, manifest)
    # Machine-readable output on stdout for the calling agent to parse
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
