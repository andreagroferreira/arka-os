"""Tests for core.shared.safe_session_id — the session-id allowlist.

The helper is security-critical: every module that uses a session id as
part of a filesystem path relies on this allowlist to block traversal
and shell injection. The tests below lock in the exact contract.
"""

from __future__ import annotations

import pytest

from core.shared import safe_session_id as ssi
from core.shared.safe_session_id import SAFE_SESSION_ID_RE, safe_session_id


class TestSafeSessionId:
    """Behaviour tests for ``safe_session_id``."""

    def test_accepts_plain_ascii(self) -> None:
        assert safe_session_id("session-abc-123") == "session-abc-123"

    def test_accepts_alphanumeric(self) -> None:
        assert safe_session_id("abc123XYZ") == "abc123XYZ"

    def test_accepts_separators_allowlist(self) -> None:
        assert safe_session_id("session_123.abc-def") == "session_123.abc-def"

    def test_accepts_single_char(self) -> None:
        assert safe_session_id("a") == "a"

    def test_accepts_max_length(self) -> None:
        token = "a" * 128
        assert safe_session_id(token) == token

    def test_rejects_empty(self) -> None:
        assert safe_session_id("") is None

    def test_rejects_none(self) -> None:
        assert safe_session_id(None) is None  # type: ignore[arg-type]

    def test_rejects_non_str_int(self) -> None:
        assert safe_session_id(12345) is None  # type: ignore[arg-type]

    def test_rejects_non_str_list(self) -> None:
        assert safe_session_id(["abc"]) is None  # type: ignore[arg-type]

    def test_rejects_non_str_dict(self) -> None:
        assert safe_session_id({"id": "abc"}) is None  # type: ignore[arg-type]

    def test_rejects_slash_traversal(self) -> None:
        assert safe_session_id("../etc/passwd") is None

    def test_rejects_backslash_traversal(self) -> None:
        assert safe_session_id("..\\windows\\system32") is None

    def test_rejects_absolute_path(self) -> None:
        assert safe_session_id("/tmp/evil") is None

    def test_rejects_parent_fragment_alone(self) -> None:
        # `..` contains dots only (which are allowed), but combined with
        # a separator it becomes a traversal — here we reject the bare
        # form too to keep the allowlist conservative.
        assert safe_session_id("/..") is None

    def test_rejects_unicode(self) -> None:
        assert safe_session_id("sessão-ñ") is None

    def test_rejects_emoji(self) -> None:
        assert safe_session_id("session-🔥") is None

    def test_rejects_oversize(self) -> None:
        assert safe_session_id("a" * 129) is None

    def test_rejects_way_oversize(self) -> None:
        assert safe_session_id("a" * 10_000) is None

    def test_rejects_space(self) -> None:
        assert safe_session_id("session abc") is None

    def test_rejects_tab(self) -> None:
        assert safe_session_id("session\tabc") is None

    def test_rejects_newline(self) -> None:
        assert safe_session_id("session\nabc") is None

    def test_rejects_crlf(self) -> None:
        assert safe_session_id("session\r\nabc") is None

    def test_rejects_null_byte(self) -> None:
        assert safe_session_id("session\x00abc") is None

    def test_rejects_shell_metachars(self) -> None:
        for bad in (";", "|", "&", "$", "`", "(", ")", "<", ">", "*", "?", "'", '"'):
            assert safe_session_id(f"session{bad}abc") is None, bad

    def test_rejects_colon(self) -> None:
        # Colon is a Windows drive separator and an ADS-path character
        # on NTFS; reject for cross-platform safety.
        assert safe_session_id("session:abc") is None


class TestRegexReexport:
    """Locks in module surface expected by the legacy call sites."""

    def test_re_pattern_matches_helper_contract(self) -> None:
        assert SAFE_SESSION_ID_RE.match("safe-123")
        assert not SAFE_SESSION_ID_RE.match("../bad")

    def test_module_exposes_symbols(self) -> None:
        assert hasattr(ssi, "safe_session_id")
        assert hasattr(ssi, "SAFE_SESSION_ID_RE")


class TestBackwardCompatReexports:
    """Every legacy call site must continue to expose the symbols."""

    def test_flow_enforcer_reexports(self) -> None:
        from core.workflow import flow_enforcer

        assert flow_enforcer.SAFE_SESSION_ID_RE is SAFE_SESSION_ID_RE
        assert flow_enforcer._safe_session_id is safe_session_id

    def test_marker_cache_reexports(self) -> None:
        from core.workflow import marker_cache

        assert marker_cache.SAFE_SESSION_ID_RE is SAFE_SESSION_ID_RE
        assert marker_cache._safe_session_id is safe_session_id

    def test_research_gate_reexports(self) -> None:
        from core.workflow import research_gate

        assert research_gate.SAFE_SESSION_ID_RE is SAFE_SESSION_ID_RE
        assert research_gate._safe_session_id is safe_session_id

    def test_kb_cache_reexports(self) -> None:
        from core.synapse import kb_cache

        assert kb_cache.SAFE_SESSION_ID_RE is SAFE_SESSION_ID_RE

    def test_auto_documentor_reexports(self) -> None:
        from core.cognition import auto_documentor

        assert auto_documentor.SAFE_SESSION_ID_RE is SAFE_SESSION_ID_RE

    def test_auto_doc_worker_reexports(self) -> None:
        from core.jobs import auto_doc_worker

        assert auto_doc_worker.SAFE_SESSION_ID_RE is SAFE_SESSION_ID_RE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
