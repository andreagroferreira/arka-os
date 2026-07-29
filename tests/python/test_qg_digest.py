"""PR-B2 — integrity digests for the Quality Gate chain."""

from __future__ import annotations

import json
import re
import typing

import pytest
from pydantic import ValidationError

from core.governance.qg_digest import (
    evidence_digest,
    verdict_digest,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class TestEvidenceDigest:
    def test_key_order_does_not_matter(self):
        a = {"overall": "pass", "results": [1, 2], "project_dir": "/x"}
        b = {"project_dir": "/x", "results": [1, 2], "overall": "pass"}
        assert evidence_digest(a) == evidence_digest(b)

    def test_content_matters(self):
        a = {"overall": "pass"}
        b = {"overall": "fail"}
        assert evidence_digest(a) != evidence_digest(b)

    def test_embedded_report_digest_is_excluded(self):
        base = {"overall": "pass", "results": []}
        digest = evidence_digest(base)
        embedded = {**base, "report_digest": digest}
        assert evidence_digest(embedded) == digest

    def test_hex64_shape(self):
        assert _HEX64.match(evidence_digest({"overall": "pass"}))

    def test_golden_vector_pins_canonical_serialization(self):
        # Frozen canonical bytes: the digest is recomputed from this
        # exact byte string {"nested":{"k":1},"s":"café"} (sorted keys,
        # compact separators, ensure_ascii=False, UTF-8). Two independent
        # implementations must agree on THIS value or digests stop
        # being comparable across versions.
        payload = {"s": "café", "nested": {"k": 1}}
        import hashlib
        expected = hashlib.sha256(
            '{"nested":{"k":1},"s":"café"}'.encode()
        ).hexdigest()
        assert evidence_digest(payload) == expected


class TestVerdictDigest:
    def test_deterministic_and_content_sensitive(self):
        approved = {"verdict": "APPROVED", "reviewer": "francisca-tech"}
        rejected = {"verdict": "REJECTED", "reviewer": "francisca-tech"}
        assert verdict_digest(approved) == verdict_digest(dict(approved))
        assert verdict_digest(approved) != verdict_digest(rejected)


class TestEvidenceReportCarriesDigest:
    def test_to_dict_embeds_a_self_consistent_digest(self, tmp_path):
        from core.governance.evidence_checks import EvidenceReport

        report = EvidenceReport(project_dir=str(tmp_path), overall="pass")
        payload = report.to_dict()
        assert _HEX64.match(payload["report_digest"])
        # Recomputing over the embedded dict must reproduce it (the
        # digest excludes its own key).
        assert evidence_digest(payload) == payload["report_digest"]

    def test_json_round_trip_keeps_digest_valid(self, tmp_path):
        from core.governance.evidence_checks import EvidenceReport

        report = EvidenceReport(project_dir=str(tmp_path), overall="fail")
        payload = json.loads(json.dumps(report.to_dict()))
        assert evidence_digest(payload) == payload["report_digest"]


class TestQGVerdictOptionalDigestFields:
    def _base(self, **extra):
        return {
            "verdict": "REJECTED",
            "evidence_report": {"overall": "fail"},
            "reviewer": "francisca-tech",
            "model_used": "opus",
            **extra,
        }

    def test_verdict_without_digest_fields_still_validates(self):
        from core.governance.qg_verdict import QGVerdict

        verdict = QGVerdict.model_validate(self._base())
        assert verdict.evidence_digest == ""
        assert verdict.tree_digest == ""
        assert verdict.reviewer_output_sha256 == ""

    def test_valid_hex64_accepted(self):
        from core.governance.qg_verdict import QGVerdict

        digest = "a" * 64
        verdict = QGVerdict.model_validate(self._base(
            evidence_digest=digest,
            reviewer_output_sha256=digest,
        ))
        assert verdict.evidence_digest == digest

    def test_tree_digest_is_reserved_and_rejects_any_value(self):
        # Even a well-formed hex64 is rejected: the producer was cut
        # from this PR, and an unverifiable digest must not enter the
        # corpus through a reserved field.
        from core.governance.qg_verdict import QGVerdict

        with pytest.raises(ValidationError):
            QGVerdict.model_validate(self._base(tree_digest="a" * 64))

    def test_nan_raises_instead_of_undefined_canonical_form(self):
        with pytest.raises(ValueError):
            evidence_digest({"coverage": float("nan")})

    @pytest.mark.parametrize("bad", ["xyz", "A" * 64, "a" * 63, "a" * 65])
    def test_non_hex64_rejected(self, bad):
        from core.governance.qg_verdict import QGVerdict

        with pytest.raises(ValidationError):
            QGVerdict.model_validate(self._base(evidence_digest=bad))


class TestJudgeVerdictSha256:
    _BASE: typing.ClassVar[dict] = {
        "gate": "G4", "role": "output-judge", "verdict": "PASS",
        "reviewer": "output-judge-g4", "model_used": "opus",
    }

    def test_judged_sha256_optional_and_validated(self):
        from core.governance.judge import JudgeVerdict

        assert JudgeVerdict.model_validate(self._BASE).judged_sha256 == ""
        ok = JudgeVerdict.model_validate(
            {**self._BASE, "judged_sha256": "b" * 64}
        )
        assert ok.judged_sha256 == "b" * 64

    @pytest.mark.parametrize("bad", ["xyz", "A" * 64, "a" * 63, "a" * 65])
    def test_judged_sha256_non_hex64_rejected(self, bad):
        from core.governance.judge import JudgeVerdict

        with pytest.raises(ValidationError):
            JudgeVerdict.model_validate({**self._BASE, "judged_sha256": bad})
