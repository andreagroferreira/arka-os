#!/usr/bin/env python3
"""
Extract frames from video and convert to optimized WebP for scroll animation.

Extracts evenly-spaced frames from an MP4 video, converts to WebP at dual
resolutions (desktop + mobile), and generates a manifest.json with metadata.

Usage:
    python3 extract_frames.py \
        --input /path/to/video.mp4 \
        --output workspace/2026-03-04/animated-sites/my-project/frames

    Custom frame count:
    python3 extract_frames.py \
        --input /path/to/video.mp4 \
        --output workspace/.../frames \
        --frames 120

    Custom quality and resolution:
    python3 extract_frames.py \
        --input /path/to/video.mp4 \
        --output workspace/.../frames \
        --quality 75 \
        --desktop-res 1920x1080 \
        --mobile-res 960x540

    Desktop only (skip mobile):
    python3 extract_frames.py \
        --input /path/to/video.mp4 \
        --output workspace/.../frames \
        --desktop-only

Environment:
    Requires ffmpeg and ffprobe installed (brew install ffmpeg).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract frames from video for scroll animation"
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to source MP4 video file"
    )
    parser.add_argument(
        "--output", required=True,
        help="Output directory for extracted frames"
    )
    parser.add_argument(
        "--frames", type=int, default=0,
        help="Target frame count (default: auto-calculated from video duration)"
    )
    parser.add_argument(
        "--quality", type=int, default=80,
        help="WebP quality 1-100 (default: 80)"
    )
    parser.add_argument(
        "--desktop-res", default="1920x1080",
        help="Desktop frame resolution (default: 1920x1080)"
    )
    parser.add_argument(
        "--mobile-res", default="960x540",
        help="Mobile frame resolution (default: 960x540)"
    )
    parser.add_argument(
        "--desktop-only", action="store_true",
        help="Skip mobile frame generation"
    )
    parser.add_argument(
        "--mobile-only", action="store_true",
        help="Skip desktop frame generation"
    )
    return parser.parse_args()


def validate_dependencies():
    """Check that ffmpeg and ffprobe are installed."""
    for cmd in ("ffmpeg", "ffprobe"):
        if not shutil.which(cmd):
            print(
                f"Error: '{cmd}' not found. Install with: brew install ffmpeg",
                file=sys.stderr,
            )
            sys.exit(1)


def validate_input(input_path):
    """Check that the input file exists and looks like a video."""
    p = Path(input_path)
    if not p.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    if p.stat().st_size < 1024:
        print(f"Error: File too small to be a video: {input_path}", file=sys.stderr)
        sys.exit(1)


def probe_video(input_path):
    """Run ffprobe and return video metadata."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(input_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: ffprobe failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Could not parse ffprobe output", file=sys.stderr)
        sys.exit(1)

    # Find the video stream
    video_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        print("Error: No video stream found in file", file=sys.stderr)
        sys.exit(1)

    # Parse frame rate (can be "30/1" or "29.97")
    fps_str = video_stream.get("r_frame_rate", "30/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 30.0
    else:
        fps = float(fps_str)

    duration = float(data.get("format", {}).get("duration", 0))
    if duration == 0:
        # Fallback: try stream duration
        duration = float(video_stream.get("duration", 0))

    width = int(video_stream.get("width", 1920))
    height = int(video_stream.get("height", 1080))
    codec = video_stream.get("codec_name", "unknown")
    total_frames = int(round(duration * fps))

    return {
        "duration": round(duration, 2),
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "codec": codec,
        "total_frames": total_frames,
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
    if user_override > 0:
        frame_count = user_override
    else:
        frame_count = min(200, max(60, int(duration * 10)))

    # Scroll height: ~3.3vh per frame, minimum 300vh
    scroll_height = max(300, int(frame_count * 3.3))
    # Round to nearest 50vh
    scroll_height = round(scroll_height / 50) * 50

    return frame_count, scroll_height


def parse_resolution(res_str):
    """Parse 'WIDTHxHEIGHT' string into (width, height) tuple."""
    try:
        w, h = res_str.lower().split("x")
        return int(w), int(h)
    except (ValueError, AttributeError):
        print(f"Error: Invalid resolution format: {res_str}. Use WIDTHxHEIGHT.", file=sys.stderr)
        sys.exit(1)


def has_libwebp():
    """Check if FFmpeg has libwebp encoder support."""
    result = subprocess.run(
        ["ffmpeg", "-encoders"], capture_output=True, text=True,
    )
    return "libwebp" in result.stdout


def extract_frames(input_path, output_dir, frame_count, resolution, quality, label=""):
    """Extract evenly-spaced frames from video as WebP.

    Strategy:
    1. If FFmpeg has libwebp: single-pass extraction to WebP (fastest)
    2. Otherwise: extract as PNG, then convert to WebP via Pillow (universal)
    """
    w, h = resolution
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get duration for fps calculation
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(input_path),
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    duration = float(result.stdout.strip()) if result.stdout.strip() else 10.0

    target_fps = frame_count / duration
    target_fps = max(1, min(60, target_fps))

    prefix = f"  [{label}] " if label else "  "
    use_libwebp = has_libwebp()

    if use_libwebp:
        # Fast path: single-pass FFmpeg → WebP
        print(f"{prefix}Extracting {frame_count} frames at {w}x{h} (FFmpeg libwebp)...", file=sys.stderr)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"fps={target_fps:.4f},scale={w}:{h}:flags=lanczos",
            "-c:v", "libwebp",
            "-quality", str(quality),
            "-compression_level", "6",
            "-an",
            "-frames:v", str(frame_count),
            str(output_dir / "frame-%04d.webp"),
        ]
    else:
        # Universal path: FFmpeg → PNG, then Pillow → WebP
        print(f"{prefix}Extracting {frame_count} frames at {w}x{h} (FFmpeg + Pillow)...", file=sys.stderr)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"fps={target_fps:.4f},scale={w}:{h}:flags=lanczos",
            "-an",
            "-frames:v", str(frame_count),
            str(output_dir / "frame-%04d.png"),
        ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=300,
        )
        if result.returncode != 0:
            print(f"Error: FFmpeg failed:\n{result.stderr[-500:]}", file=sys.stderr)
            sys.exit(1)
    except subprocess.TimeoutExpired:
        print("Error: FFmpeg timed out (5 min limit)", file=sys.stderr)
        sys.exit(1)

    # If we extracted PNGs, convert to WebP with Pillow
    if not use_libwebp:
        try:
            from PIL import Image as PILImage
        except ImportError:
            print(
                "Error: Neither libwebp (FFmpeg) nor Pillow is available.\n"
                "Fix: pip install Pillow  OR  brew reinstall ffmpeg",
                file=sys.stderr,
            )
            sys.exit(1)

        png_files = sorted(output_dir.glob("frame-*.png"))
        print(f"{prefix}Converting {len(png_files)} PNGs to WebP via Pillow...", file=sys.stderr)

        for png_path in png_files:
            webp_path = png_path.with_suffix(".webp")
            img = PILImage.open(png_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(str(webp_path), "WEBP", quality=quality, method=6)
            png_path.unlink()  # Remove PNG to save disk space

    # Count actual extracted frames
    frames = sorted(output_dir.glob("frame-*.webp"))
    actual_count = len(frames)

    if actual_count == 0:
        print(f"Error: No frames extracted to {output_dir}", file=sys.stderr)
        sys.exit(1)

    # Calculate total size
    total_bytes = sum(f.stat().st_size for f in frames)
    avg_bytes = total_bytes // actual_count if actual_count > 0 else 0

    print(
        f"{prefix}{actual_count} frames extracted "
        f"({total_bytes / 1024 / 1024:.1f}MB total, "
        f"{avg_bytes / 1024:.0f}KB avg per frame)",
        file=sys.stderr,
    )

    return {
        "count": actual_count,
        "total_bytes": total_bytes,
        "avg_bytes": avg_bytes,
        "resolution": f"{w}x{h}",
    }


def generate_manifest(output_dir, video_info, frame_count, scroll_height,
                       quality, desktop_info=None, mobile_info=None):
    """Generate manifest.json with full metadata."""
    manifest = {
        "source": {
            "filename": video_info["filename"],
            "duration": video_info["duration"],
            "resolution": f"{video_info['width']}x{video_info['height']}",
            "fps": video_info["fps"],
            "codec": video_info["codec"],
            "total_source_frames": video_info["total_frames"],
        },
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
        manifest["desktop"] = {
            "resolution": desktop_info["resolution"],
            "actual_count": desktop_info["count"],
            "total_bytes": desktop_info["total_bytes"],
            "avg_frame_bytes": desktop_info["avg_bytes"],
            "total_mb": round(desktop_info["total_bytes"] / 1024 / 1024, 2),
        }

    if mobile_info:
        manifest["mobile"] = {
            "resolution": mobile_info["resolution"],
            "actual_count": mobile_info["count"],
            "total_bytes": mobile_info["total_bytes"],
            "avg_frame_bytes": mobile_info["avg_bytes"],
            "total_mb": round(mobile_info["total_bytes"] / 1024 / 1024, 2),
        }

    manifest_path = Path(output_dir) / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n  Manifest saved to: {manifest_path}", file=sys.stderr)
    return manifest


def print_summary(video_info, frame_count, scroll_height, manifest):
    """Print a human-readable summary."""
    print("\n" + "=" * 56, file=sys.stderr)
    print("  VIDEO ANALYSIS", file=sys.stderr)
    print("=" * 56, file=sys.stderr)
    print(f"  Source:      {video_info['filename']}", file=sys.stderr)
    print(f"  Duration:    {video_info['duration']}s", file=sys.stderr)
    print(f"  Resolution:  {video_info['width']}x{video_info['height']}", file=sys.stderr)
    print(f"  Frame Rate:  {video_info['fps']}fps", file=sys.stderr)
    print(f"  Codec:       {video_info['codec']}", file=sys.stderr)
    print(f"  Src Frames:  {video_info['total_frames']}", file=sys.stderr)
    print("-" * 56, file=sys.stderr)
    print("  EXTRACTION RESULTS", file=sys.stderr)
    print("-" * 56, file=sys.stderr)
    print(f"  Target:      {frame_count} frames", file=sys.stderr)
    print(f"  Scroll:      {scroll_height}vh recommended", file=sys.stderr)

    if "desktop" in manifest:
        d = manifest["desktop"]
        print(f"  Desktop:     {d['actual_count']} frames @ {d['resolution']} ({d['total_mb']}MB)", file=sys.stderr)

    if "mobile" in manifest:
        m = manifest["mobile"]
        print(f"  Mobile:      {m['actual_count']} frames @ {m['resolution']} ({m['total_mb']}MB)", file=sys.stderr)

    print("=" * 56, file=sys.stderr)

    # Warnings
    desktop_mb = manifest.get("desktop", {}).get("total_mb", 0)
    mobile_mb = manifest.get("mobile", {}).get("total_mb", 0)
    if desktop_mb > 15:
        print(f"\n  WARNING: Desktop payload ({desktop_mb}MB) exceeds 15MB target.", file=sys.stderr)
        print("  Consider: --quality 60 or --frames (lower count)", file=sys.stderr)
    if mobile_mb > 5:
        print(f"\n  WARNING: Mobile payload ({mobile_mb}MB) exceeds 5MB target.", file=sys.stderr)
        print("  Consider: --quality 60 or --frames (lower count)", file=sys.stderr)


def main():
    args = parse_args()

    # Validate
    validate_dependencies()
    validate_input(args.input)

    # Probe video
    print("\nProbing video...", file=sys.stderr)
    video_info = probe_video(args.input)

    # Calculate frame count
    frame_count, scroll_height = calculate_optimal_frames(
        video_info["duration"], args.frames
    )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    desktop_res = parse_resolution(args.desktop_res)
    mobile_res = parse_resolution(args.mobile_res)

    desktop_info = None
    mobile_info = None

    # Extract desktop frames
    if not args.mobile_only:
        desktop_dir = output_dir / "desktop"
        desktop_info = extract_frames(
            args.input, desktop_dir, frame_count,
            desktop_res, args.quality, label="desktop"
        )

    # Extract mobile frames
    if not args.desktop_only:
        mobile_dir = output_dir / "mobile"
        mobile_info = extract_frames(
            args.input, mobile_dir, frame_count,
            mobile_res, args.quality, label="mobile"
        )

    # Generate manifest
    manifest = generate_manifest(
        output_dir, video_info, frame_count, scroll_height,
        args.quality, desktop_info, mobile_info,
    )

    # Print summary
    print_summary(video_info, frame_count, scroll_height, manifest)

    # Print machine-readable output on stdout for Claude Code to parse
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
