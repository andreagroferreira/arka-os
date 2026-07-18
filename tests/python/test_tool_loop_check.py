"""Tool-loop detection — current-turn scan, privacy-preserving verdict."""

from __future__ import annotations

import dataclasses
import json

from core.governance.tool_loop_check import LoopVerdict, check_tool_loops


def _transcript(*records: dict) -> str:
    return "\n".join(json.dumps(r) for r in records)


def _user(text: str = "do the thing") -> dict:
    return {"role": "user", "content": text}


def _assistant_calls(*calls: tuple[str, dict]) -> dict:
    return {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "name": name, "input": payload}
            for name, payload in calls
        ],
    }


def test_consecutive_identical_calls_detected():
    raw = _transcript(
        _user(),
        _assistant_calls(*[("Read", {"file_path": "/a.py"})] * 5),
    )
    verdict = check_tool_loops(raw)
    assert verdict.detected is True
    assert verdict.pattern == "consecutive"
    assert verdict.tool == "Read"
    assert verdict.repeats == 5


def test_repeated_with_interleaving_detected():
    raw = _transcript(
        _user(),
        _assistant_calls(
            ("Grep", {"pattern": "x"}),
            ("Read", {"file_path": "/b.py"}),
            ("Grep", {"pattern": "x"}),
            ("Bash", {"command": "ls"}),
            ("Grep", {"pattern": "x"}),
            ("Grep", {"pattern": "x"}),
        ),
    )
    verdict = check_tool_loops(raw)
    assert verdict.detected is True
    assert verdict.pattern == "repeated"
    assert verdict.tool == "Grep"
    assert verdict.repeats == 4


def test_same_tool_different_inputs_is_not_a_loop():
    raw = _transcript(
        _user(),
        _assistant_calls(
            *[("Read", {"file_path": f"/f{i}.py"}) for i in range(6)]
        ),
    )
    verdict = check_tool_loops(raw)
    assert verdict.detected is False
    assert verdict.total_tool_uses == 6


def test_below_threshold_not_detected():
    raw = _transcript(
        _user(),
        _assistant_calls(*[("Read", {"file_path": "/a.py"})] * 3),
    )
    assert check_tool_loops(raw).detected is False


def test_only_current_turn_is_scanned():
    raw = _transcript(
        _user("first ask"),
        _assistant_calls(*[("Read", {"file_path": "/a.py"})] * 6),
        _user("second ask"),
        _assistant_calls(("Read", {"file_path": "/a.py"})),
    )
    verdict = check_tool_loops(raw)
    assert verdict.detected is False
    assert verdict.total_tool_uses == 1


def test_empty_and_malformed_transcripts_are_safe():
    assert check_tool_loops(None).detected is False
    assert check_tool_loops("").detected is False
    assert check_tool_loops("{not json}\n<garbage>").detected is False


def test_threshold_below_two_disables_scan():
    raw = _transcript(
        _user(),
        _assistant_calls(*[("Read", {"file_path": "/a.py"})] * 5),
    )
    assert check_tool_loops(raw, threshold=1).detected is False


def test_verdict_never_carries_tool_inputs():
    field_names = {f.name for f in dataclasses.fields(LoopVerdict)}
    assert field_names == {
        "detected", "tool", "repeats", "pattern", "total_tool_uses",
    }
    raw = _transcript(
        _user(),
        _assistant_calls(*[("Read", {"file_path": "/secret/client.py"})] * 5),
    )
    verdict = check_tool_loops(raw)
    assert "/secret/client.py" not in repr(verdict)


def test_unserializable_input_still_scans():
    records = [
        _user(),
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "name": "Odd", "input": {"k": float("nan")}}
            ] * 4,
        },
    ]
    raw = "\n".join(json.dumps(r) for r in records)
    verdict = check_tool_loops(raw)
    assert verdict.detected is True
    assert verdict.tool == "Odd"
