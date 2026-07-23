"""Unit tests for departments/dev/skills/animated-website/scripts/extract_frames.py.

The script shells out to ffmpeg/ffprobe at the edges; these tests cover the
pure decision logic (fps parsing, frame budgeting, resolution parsing,
validation, manifest shaping, command construction) with the subprocess
boundary monkeypatched — no ffmpeg required.
"""

import importlib.util
import json
import sys
from pathlib import Path
from typing import ClassVar

import pytest

_ROOT = Path(__file__).parent.parent.parent
_SCRIPT = (_ROOT / "departments" / "dev" / "skills" / "animated-website"
           / "scripts" / "extract_frames.py")

# Never write bytecode next to a shipped skill script — the marketplace
# drift gate compares the departments/ tree against the generated plugins/.
_prev_dont_write = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    _spec = importlib.util.spec_from_file_location("extract_frames", _SCRIPT)
    _ef = importlib.util.module_from_spec(_spec)
    sys.modules["extract_frames"] = _ef
    _spec.loader.exec_module(_ef)
finally:
    sys.dont_write_bytecode = _prev_dont_write


class TestParseFps:
    def test_rational_form(self):
        assert _ef.parse_fps("30/1") == 30.0

    def test_ntsc_rational(self):
        assert _ef.parse_fps("30000/1001") == pytest.approx(29.97, abs=0.01)

    def test_decimal_form(self):
        assert _ef.parse_fps("29.97") == 29.97

    def test_zero_denominator_falls_back_to_30(self):
        assert _ef.parse_fps("0/0") == 30.0


class TestCalculateOptimalFrames:
    def test_short_video_hits_60_floor(self):
        frames, scroll = _ef.calculate_optimal_frames(3)
        assert frames == 60
        assert scroll == 300

    def test_standard_video_scales_by_duration(self):
        frames, scroll = _ef.calculate_optimal_frames(12)
        assert frames == 120
        assert scroll == 400

    def test_long_video_caps_at_200(self):
        frames, _ = _ef.calculate_optimal_frames(45)
        assert frames == 200

    def test_user_override_wins(self):
        frames, _ = _ef.calculate_optimal_frames(45, user_override=90)
        assert frames == 90

    def test_scroll_height_rounds_to_50vh(self):
        _, scroll = _ef.calculate_optimal_frames(0, user_override=150)
        assert scroll % 50 == 0
        assert scroll == 500


class TestParseResolution:
    def test_valid(self):
        assert _ef.parse_resolution("1920x1080") == (1920, 1080)

    def test_uppercase_x(self):
        assert _ef.parse_resolution("960X540") == (960, 540)

    def test_invalid_exits(self):
        with pytest.raises(SystemExit) as exc:
            _ef.parse_resolution("1080p")
        assert exc.value.code == 1


class TestValidation:
    def test_quality_in_range_passes(self):
        _ef.validate_quality(80)  # no exit

    @pytest.mark.parametrize("bad", [0, 101, -5])
    def test_quality_out_of_range_exits(self, bad):
        with pytest.raises(SystemExit):
            _ef.validate_quality(bad)

    def test_missing_input_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            _ef.validate_input(tmp_path / "nope.mp4")

    def test_tiny_file_exits(self, tmp_path):
        stub = tmp_path / "tiny.mp4"
        stub.write_bytes(b"x" * 10)
        with pytest.raises(SystemExit):
            _ef.validate_input(stub)

    def test_valid_input_returns_resolved_path(self, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"x" * 2048)
        assert _ef.validate_input(video) == video.resolve()


class TestBuildExtractCmd:
    def test_libwebp_single_pass(self, tmp_path):
        cmd = _ef._build_extract_cmd("in.mp4", tmp_path, 12.5, (1920, 1080), 80, True)
        assert "-c:v" in cmd and "libwebp" in cmd
        assert cmd[-1].endswith("frame-%04d.webp")
        assert "fps=12.5000,scale=1920:1080:flags=lanczos" in cmd

    def test_png_fallback(self, tmp_path):
        cmd = _ef._build_extract_cmd("in.mp4", tmp_path, 12.5, (960, 540), 80, False)
        assert "libwebp" not in cmd
        assert cmd[-1].endswith("frame-%04d.png")


class TestProbeVideo:
    def _probe_payload(self):
        return {
            "streams": [
                {"codec_type": "audio"},
                {"codec_type": "video", "r_frame_rate": "30/1", "width": 3840,
                 "height": 2160, "codec_name": "h264"},
            ],
            "format": {"duration": "12.4"},
        }

    def test_parses_video_stream(self, monkeypatch):
        monkeypatch.setattr(_ef, "_run_ffprobe", lambda _: self._probe_payload())
        info = _ef.probe_video("/tmp/clip.mp4")
        assert info["duration"] == 12.4
        assert info["width"] == 3840
        assert info["fps"] == 30.0
        assert info["total_frames"] == 372
        assert info["filename"] == "clip.mp4"

    def test_stream_duration_fallback(self, monkeypatch):
        payload = self._probe_payload()
        payload["format"] = {}
        payload["streams"][1]["duration"] = "8.0"
        monkeypatch.setattr(_ef, "_run_ffprobe", lambda _: payload)
        assert _ef.probe_video("/tmp/clip.mp4")["duration"] == 8.0

    def test_no_video_stream_exits(self, monkeypatch):
        monkeypatch.setattr(_ef, "_run_ffprobe", lambda _: {"streams": [], "format": {}})
        with pytest.raises(SystemExit):
            _ef.probe_video("/tmp/clip.mp4")


class TestMeasureFrames:
    def test_counts_and_sizes(self, tmp_path, capsys):
        for i in range(3):
            (tmp_path / f"frame-{i:04d}.webp").write_bytes(b"x" * 1000)
        info = _ef._measure_frames(tmp_path, (1920, 1080), "  ")
        assert info["count"] == 3
        assert info["total_bytes"] == 3000
        assert info["resolution"] == "1920x1080"

    def test_empty_dir_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            _ef._measure_frames(tmp_path, (1920, 1080), "  ")


class TestManifest:
    _VIDEO: ClassVar[dict] = {
        "filename": "clip.mp4", "duration": 12.4, "width": 3840, "height": 2160,
        "fps": 30.0, "codec": "h264", "total_frames": 372,
    }
    _INFO: ClassVar[dict] = {
        "count": 120, "total_bytes": 8_000_000, "avg_bytes": 66_666,
        "resolution": "1920x1080",
    }

    def test_writes_manifest_json(self, tmp_path):
        manifest = _ef.generate_manifest(
            tmp_path, self._VIDEO, 120, 400, 80,
            desktop_info=self._INFO, mobile_info=None,
        )
        on_disk = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
        assert on_disk == json.loads(json.dumps(manifest))
        assert manifest["recommended_scroll_height"] == "400vh"
        assert manifest["desktop"]["total_mb"] == 7.63
        assert "mobile" not in manifest

    def test_budget_warning_over_10mb_desktop(self, capsys):
        manifest = {"desktop": {"total_mb": 12.5}}
        _ef._print_budget_warnings(manifest)
        err = capsys.readouterr().err
        assert "exceeds 10MB target" in err

    def test_no_warning_under_budget(self, capsys):
        _ef._print_budget_warnings({"desktop": {"total_mb": 8.0}, "mobile": {"total_mb": 4.9}})
        assert "WARNING" not in capsys.readouterr().err


class _FakeCompleted:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class TestDependencyAndSubprocessBoundary:
    def test_validate_dependencies_pass(self, monkeypatch):
        monkeypatch.setattr(_ef.shutil, "which", lambda _: "/usr/bin/ffmpeg")
        _ef.validate_dependencies()  # no exit

    def test_validate_dependencies_missing_exits(self, monkeypatch):
        monkeypatch.setattr(_ef.shutil, "which", lambda _: None)
        with pytest.raises(SystemExit):
            _ef.validate_dependencies()

    def test_has_libwebp_true_and_false(self, monkeypatch):
        monkeypatch.setattr(
            _ef.subprocess, "run",
            lambda *a, **k: _FakeCompleted(stdout="... libwebp ..."),
        )
        assert _ef.has_libwebp() is True
        monkeypatch.setattr(
            _ef.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout="none")
        )
        assert _ef.has_libwebp() is False

    def test_probe_duration_and_fallback(self, monkeypatch):
        monkeypatch.setattr(
            _ef.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout="12.4\n")
        )
        assert _ef._probe_duration("in.mp4") == 12.4
        monkeypatch.setattr(
            _ef.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout="")
        )
        assert _ef._probe_duration("in.mp4") == 10.0

    def test_run_ffmpeg_success_and_failure(self, monkeypatch):
        monkeypatch.setattr(
            _ef.subprocess, "run", lambda *a, **k: _FakeCompleted(returncode=0)
        )
        _ef._run_ffmpeg(["ffmpeg"])  # no exit
        monkeypatch.setattr(
            _ef.subprocess, "run",
            lambda *a, **k: _FakeCompleted(returncode=1, stderr="boom"),
        )
        with pytest.raises(SystemExit):
            _ef._run_ffmpeg(["ffmpeg"])

    def test_run_ffmpeg_timeout_exits(self, monkeypatch):
        def raise_timeout(*a, **k):
            raise _ef.subprocess.TimeoutExpired(cmd="ffmpeg", timeout=300)
        monkeypatch.setattr(_ef.subprocess, "run", raise_timeout)
        with pytest.raises(SystemExit):
            _ef._run_ffmpeg(["ffmpeg"])

    def test_run_ffprobe_success(self, monkeypatch):
        monkeypatch.setattr(
            _ef.subprocess, "run",
            lambda *a, **k: _FakeCompleted(stdout='{"streams": []}'),
        )
        assert _ef._run_ffprobe("in.mp4") == {"streams": []}

    def test_run_ffprobe_process_error_exits(self, monkeypatch):
        def raise_cpe(*a, **k):
            raise _ef.subprocess.CalledProcessError(1, "ffprobe", stderr="bad file")
        monkeypatch.setattr(_ef.subprocess, "run", raise_cpe)
        with pytest.raises(SystemExit):
            _ef._run_ffprobe("in.mp4")

    def test_run_ffprobe_bad_json_exits(self, monkeypatch):
        monkeypatch.setattr(
            _ef.subprocess, "run", lambda *a, **k: _FakeCompleted(stdout="not json")
        )
        with pytest.raises(SystemExit):
            _ef._run_ffprobe("in.mp4")

    def test_convert_pngs_missing_pillow_exits(self, monkeypatch, tmp_path):
        monkeypatch.setitem(sys.modules, "PIL", None)
        with pytest.raises(SystemExit):
            _ef._convert_pngs_to_webp(tmp_path, 80, "  ")


class TestExtractFramesOrchestration:
    def test_libwebp_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_ef, "_probe_duration", lambda _: 10.0)
        monkeypatch.setattr(_ef, "has_libwebp", lambda: True)

        def fake_ffmpeg(cmd):
            out_dir = Path(cmd[-1]).parent
            for i in range(3):
                (out_dir / f"frame-{i:04d}.webp").write_bytes(b"x" * 100)
        monkeypatch.setattr(_ef, "_run_ffmpeg", fake_ffmpeg)

        info = _ef.extract_frames("in.mp4", tmp_path / "desktop", 120,
                                  (1920, 1080), 80, label="desktop")
        assert info["count"] == 3
        assert info["resolution"] == "1920x1080"

    def test_png_fallback_path_calls_converter(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_ef, "_probe_duration", lambda _: 10.0)
        monkeypatch.setattr(_ef, "has_libwebp", lambda: False)
        converted = []

        def fake_ffmpeg(cmd):
            out_dir = Path(cmd[-1]).parent
            (out_dir / "frame-0001.webp").write_bytes(b"x" * 100)
        monkeypatch.setattr(_ef, "_run_ffmpeg", fake_ffmpeg)
        monkeypatch.setattr(
            _ef, "_convert_pngs_to_webp",
            lambda out, q, prefix: converted.append(str(out)),
        )
        _ef.extract_frames("in.mp4", tmp_path / "mobile", 60, (960, 540), 80)
        assert converted == [str(tmp_path / "mobile")]

    def test_fps_clamped_between_1_and_60(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_ef, "_probe_duration", lambda _: 1.0)
        monkeypatch.setattr(_ef, "has_libwebp", lambda: True)
        captured = {}

        def fake_ffmpeg(cmd):
            captured["vf"] = cmd[cmd.index("-vf") + 1]
            out_dir = Path(cmd[-1]).parent
            (out_dir / "frame-0001.webp").write_bytes(b"x")
        monkeypatch.setattr(_ef, "_run_ffmpeg", fake_ffmpeg)
        _ef.extract_frames("in.mp4", tmp_path, 200, (1920, 1080), 80)
        assert captured["vf"].startswith("fps=60.0000")


class TestPrintSummary:
    def test_prints_both_variants(self, capsys):
        manifest = {
            "desktop": {"actual_count": 120, "resolution": "1920x1080", "total_mb": 7.5},
            "mobile": {"actual_count": 120, "resolution": "960x540", "total_mb": 3.1},
        }
        video = {"filename": "clip.mp4", "duration": 12.4, "width": 3840,
                 "height": 2160, "fps": 30.0, "codec": "h264", "total_frames": 372}
        _ef.print_summary(video, 120, 400, manifest)
        err = capsys.readouterr().err
        assert "VIDEO ANALYSIS" in err
        assert "Desktop" in err and "Mobile" in err
        assert "WARNING" not in err


class TestMainEndToEnd:
    def test_main_happy_path(self, monkeypatch, tmp_path, capsys):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"x" * 2048)
        out = tmp_path / "frames"
        monkeypatch.setattr(sys, "argv", [
            "extract_frames.py", "--input", str(video), "--output", str(out),
            "--frames", "3", "--desktop-only",
        ])
        monkeypatch.setattr(_ef, "validate_dependencies", lambda: None)
        monkeypatch.setattr(_ef, "probe_video", lambda _: {
            "filename": "clip.mp4", "duration": 12.4, "width": 1920,
            "height": 1080, "fps": 30.0, "codec": "h264", "total_frames": 372,
        })
        monkeypatch.setattr(_ef, "extract_frames",
                            lambda *a, **k: {"count": 3, "total_bytes": 300,
                                             "avg_bytes": 100, "resolution": "1920x1080"})
        _ef.main()
        stdout = capsys.readouterr().out
        manifest = json.loads(stdout)
        assert manifest["frames"]["target_count"] == 3
        assert manifest["desktop"]["actual_count"] == 3
        assert "mobile" not in manifest
        assert (out / "manifest.json").exists()


class TestExtractVariants:
    class _Args:
        output = None
        desktop_res = "1920x1080"
        mobile_res = "960x540"
        quality = 80
        desktop_only = False
        mobile_only = False

    def _patch_extract(self, monkeypatch, calls):
        def stub(input_path, out_dir, frame_count, resolution, quality, label=""):
            calls.append((str(out_dir), resolution, label))
            return {"count": frame_count, "total_bytes": 1, "avg_bytes": 1,
                    "resolution": f"{resolution[0]}x{resolution[1]}"}
        monkeypatch.setattr(_ef, "extract_frames", stub)

    def test_both_variants_by_default(self, monkeypatch, tmp_path):
        calls = []
        self._patch_extract(monkeypatch, calls)
        args = self._Args()
        args.output = str(tmp_path)
        desktop, mobile = _ef._extract_variants(args, "in.mp4", 120)
        assert desktop and mobile
        assert [c[2] for c in calls] == ["desktop", "mobile"]

    def test_desktop_only_skips_mobile(self, monkeypatch, tmp_path):
        calls = []
        self._patch_extract(monkeypatch, calls)
        args = self._Args()
        args.output = str(tmp_path)
        args.desktop_only = True
        desktop, mobile = _ef._extract_variants(args, "in.mp4", 120)
        assert desktop is not None
        assert mobile is None
        assert [c[2] for c in calls] == ["desktop"]
