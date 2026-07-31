"""core.egress — deny-by-default policy, fail-closed at every joint.

Fixture secrets use the Slack-token and private-key-header shapes from
``secret_labels`` — deliberately NOT the AWS/GitHub/OpenAI shapes, so
the evidence engine's own security-grep never fires on this file.
Fixture client identifiers are SYNTHETIC (acme-alpha, betacorp,
synthesis-co) — real client names never enter the repo (QG D1 r1 B3;
the release preflight leak gate blocks on them).
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.egress import allowlist, audit, policy
from core.egress.allowlist import AllowlistEntry
from core.egress.policy import EgressDeniedError, enforce, evaluate

NOW = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
DEST = "notebooklm"
CLIENTS = ("acme-alpha", "betacorp", "synthesis-co")


def write_clients(tmp_path, names=CLIENTS):
    cfg = tmp_path / "redaction-clients.json"
    cfg.write_text(json.dumps({"clients": list(names)}), encoding="utf-8")
    return cfg


def write_allowlist(tmp_path, entries):
    path = tmp_path / "allowlist.json"
    path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return path


def run(tmp_path, text, *, clients=True, entries=None, **kwargs):
    cfg = write_clients(tmp_path) if clients else tmp_path / "absent.json"
    allow = write_allowlist(tmp_path, entries or [])
    kwargs.setdefault("now", NOW)
    return evaluate(
        text,
        DEST,
        config_path=cfg,
        home=tmp_path / "home",
        allowlist_path=allow,
        audit_path=tmp_path / "audit.jsonl",
        **kwargs,
    )


def kinds(decision):
    return [f.kind for f in decision.findings]


class TestFailClosed:
    def test_missing_config_denies_everything(self, tmp_path):
        decision = run(tmp_path, "totally harmless text", clients=False)
        assert not decision.allowed
        assert kinds(decision) == ["redaction-config-missing"]
        assert decision.redacted_text is None

    def test_empty_config_denies(self, tmp_path):
        cfg = tmp_path / "redaction-clients.json"
        cfg.write_text('{"clients": []}', encoding="utf-8")
        decision = evaluate(
            "hello", DEST, config_path=cfg, home=tmp_path / "home",
            allowlist_path=tmp_path / "a.json",
            audit_path=tmp_path / "audit.jsonl", now=NOW,
        )
        assert kinds(decision) == ["redaction-config-missing"]

    def test_enforce_raises_and_names_the_reason(self, tmp_path):
        with pytest.raises(
            EgressDeniedError, match="redaction-config-missing"
        ):
            enforce(
                "hello", DEST,
                config_path=tmp_path / "absent.json",
                home=tmp_path / "home",
                allowlist_path=tmp_path / "a.json",
                audit_path=tmp_path / "audit.jsonl", now=NOW,
            )

    def test_enforce_happy_path_returns_redacted_text(self, tmp_path):
        cfg = write_clients(tmp_path)
        cleared = enforce(
            "report on acme-alpha margins", DEST, config_path=cfg,
            home=tmp_path / "home",
            allowlist_path=tmp_path / "a.json",
            audit_path=tmp_path / "audit.jsonl", now=NOW,
        )
        assert cleared == "report on [CLIENT-1] margins"


class TestRedaction:
    def test_client_names_leave_only_redacted(self, tmp_path):
        decision = run(tmp_path, "the Acme-Alpha quarterly numbers")
        assert decision.allowed
        assert "acme" not in decision.redacted_text.lower()
        assert "[CLIENT-1]" in decision.redacted_text
        assert decision.redacted_sha256 != decision.payload_sha256

    def test_clean_payload_passes_unchanged(self, tmp_path):
        decision = run(tmp_path, "generic research question")
        assert decision.allowed
        assert decision.redacted_text == "generic research question"

    @pytest.mark.parametrize(
        "payload",
        [
            "Q3 numbers for betacorp2026",
            "the BetacorpEU migration",
            "branch feat/betacorpShop-checkout",
            "#betacorp1 chat channel",
        ],
    )
    def test_compound_identifier_tokens_are_denied(self, tmp_path, payload):
        """The sanitizer's word boundary skips <client>2026-style
        compounds, so the RESIDUAL layer must catch them — substring,
        no boundary (QG D1 r1 B2). Deny, never leak."""
        decision = run(tmp_path, payload)
        assert not decision.allowed
        assert kinds(decision) == ["client-identifier"]

    def test_redacted_compound_forms_still_pass(self, tmp_path):
        """Forms the sanitizer CAN redact keep passing — the looser
        residual layer runs on the already-redacted text."""
        decision = run(tmp_path, "repo acme-alpha_api and betacorp tools")
        assert decision.allowed
        assert "acme" not in decision.redacted_text.lower()
        assert "betacorp" not in decision.redacted_text.lower()

    def test_residual_identifier_denies_never_allowlists(self, tmp_path):
        entry = {
            "kind": "client-identifier", "token": "betacorp",
            "reason": "try",
            "expires": (NOW + timedelta(days=1)).isoformat(),
        }
        decision = run(tmp_path, "betacorp2026 report", entries=[entry])
        assert not decision.allowed
        assert kinds(decision) == ["client-identifier"]
        assert decision.allowlisted == []


class TestNeverRaises:
    def test_long_s_payload_is_denied_not_a_keyerror(self, tmp_path):
        """U+017F LATIN SMALL LETTER LONG S inside the identifier
        match: the IGNORECASE regex matches it but str.lower() does
        not normalise it, so the sanitizer raises KeyError (QG D1 r1
        B1 trigger shape). The guard must deny, audit, and never
        propagate."""
        payload = "numbers for \u017fynthe\u017fis-co end"
        decision = run(tmp_path, payload)
        assert not decision.allowed
        assert kinds(decision) == ["redaction-failed"]
        assert decision.audited is True

    def test_non_list_clients_config_is_denied(self, tmp_path):
        cfg = tmp_path / "redaction-clients.json"
        cfg.write_text('{"clients": 5}', encoding="utf-8")
        decision = evaluate(
            "hello", DEST, config_path=cfg, home=tmp_path / "home",
            allowlist_path=tmp_path / "a.json",
            audit_path=tmp_path / "audit.jsonl", now=NOW,
        )
        assert not decision.allowed
        assert kinds(decision) == ["redaction-failed"]

    def test_latin1_redaction_config_is_denied(self, tmp_path):
        cfg = tmp_path / "redaction-clients.json"
        cfg.write_bytes('{"clients": ["são-cliente"]}'.encode("latin-1"))
        decision = evaluate(
            "hello", DEST, config_path=cfg, home=tmp_path / "home",
            allowlist_path=tmp_path / "a.json",
            audit_path=tmp_path / "audit.jsonl", now=NOW,
        )
        assert not decision.allowed
        assert kinds(decision) == ["redaction-failed"]

    def test_latin1_allowlist_permits_nothing_and_never_raises(
        self, tmp_path
    ):
        path = tmp_path / "allowlist.json"
        path.write_bytes('{"entries": ["são"]}'.encode("latin-1"))
        assert allowlist.active_entries(path, NOW) == []

    def test_naive_now_denies_instead_of_typeerror(self, tmp_path):
        entry = {
            "kind": "secret", "token": "Slack token", "reason": "demo",
            "expires": (NOW + timedelta(days=1)).isoformat(),
        }
        decision = run(
            tmp_path, "token: xoxb-1234567890-abcdef",
            entries=[entry], now=datetime(2026, 7, 31, 12, 0),
        )
        assert not decision.allowed  # naive now -> no live entries

    def test_non_string_destination_never_raises(self, tmp_path):
        cfg = write_clients(tmp_path)
        decision = evaluate(
            "hello", object(), config_path=cfg, home=tmp_path / "home",
            allowlist_path=tmp_path / "a.json",
            audit_path=tmp_path / "audit.jsonl", now=NOW,
        )
        assert decision.audited is True

    def test_non_string_payload_is_a_decision_not_a_traceback(self, tmp_path):
        decision = run(tmp_path, b"\xff\xfebytes")
        assert not decision.allowed
        assert kinds(decision) == ["payload-not-text"]

    def test_empty_string_is_judged_normally(self, tmp_path):
        decision = run(tmp_path, "")
        assert decision.allowed
        assert decision.redacted_text == ""

    def test_huge_payload_never_raises(self, tmp_path):
        decision = run(tmp_path, "x" * 2_000_000)
        assert decision.allowed

    def test_internal_failure_hits_the_guard_boundary(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            policy, "_collect_findings",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        decision = run(tmp_path, "hello")
        assert not decision.allowed
        assert kinds(decision) == ["guard-failure"]
        assert decision.findings[0].token == "RuntimeError"
        # The boundary decision carries the real payload digest — pins
        # the precomputed payload_digest (QG D1 r3 F-M2).
        assert len(decision.payload_sha256) == 64

    def test_lone_surrogate_payload_never_raises(self, tmp_path):
        """A str holding a lone surrogate (routine from
        errors='surrogateescape' or json.loads of an escape) crashed
        the digest INSIDE the r2 boundary handler (QG D1 r2 E-B1).
        _sha256 is now total via surrogatepass — the payload is judged
        and audited, never a UnicodeEncodeError."""
        decision = run(tmp_path, "\udc80 lone surrogate payload")
        assert decision.audited is True
        assert len(decision.payload_sha256) == 64

    def test_raising_destination_str_never_raises(self, tmp_path):
        class Hostile:
            def __str__(self):
                raise ValueError("no rendering")

        cfg = write_clients(tmp_path)
        decision = evaluate(
            "hello", Hostile(), config_path=cfg, home=tmp_path / "home",
            allowlist_path=tmp_path / "a.json",
            audit_path=tmp_path / "audit.jsonl", now=NOW,
        )
        assert decision.destination == "<unprintable Hostile>"
        assert decision.audited is True

    def test_home_as_str_with_no_audit_path_denies_not_raises(self):
        """home passed as str with audit_path=None sat outside the try
        in r2 (QG D1 r2 F-M5) — now it denies via the path guard."""
        decision = evaluate("hello", DEST, home="not-a-path")
        assert not decision.allowed


class TestSecretsAndPaths:
    def test_secret_denies(self, tmp_path):
        decision = run(tmp_path, "token: xoxb-1234567890-abcdef")
        assert not decision.allowed
        assert kinds(decision) == ["secret"]

    def test_private_key_header_denies(self, tmp_path):
        decision = run(tmp_path, "-----BEGIN RSA PRIVATE KEY-----")
        assert not decision.allowed
        assert kinds(decision) == ["secret"]

    def test_home_path_denies_and_names_the_path(self, tmp_path):
        home = tmp_path / "home"
        decision = run(tmp_path, f"see {home}/Herd/shop/config.php please")
        assert not decision.allowed
        assert decision.findings[0].kind == "home-path"
        assert decision.findings[0].token == f"{home}/Herd/shop/config.php"

    def test_tilde_path_is_a_finding(self, tmp_path):
        decision = run(tmp_path, "the file lives at ~/Work/shop/api.ts")
        assert not decision.allowed
        assert kinds(decision) == ["home-path"]
        assert decision.findings[0].token == "~/Work/shop/api.ts"

    def test_case_variant_home_path_is_a_finding(self, tmp_path):
        home = str(tmp_path / "home").upper()
        decision = run(tmp_path, f"see {home}/Work/x.ts")
        assert not decision.allowed
        assert kinds(decision) == ["home-path"]

    def test_path_outside_home_is_not_a_finding(self, tmp_path):
        decision = run(tmp_path, "logs at /var/log/system.log")
        assert decision.allowed


class TestAllowlist:
    def secret_entry(self, expires, **extra):
        return {
            "kind": "secret", "token": "Slack token",
            "reason": "sanctioned demo token", "expires": expires, **extra,
        }

    def test_live_entry_permits_exact_finding(self, tmp_path):
        entry = self.secret_entry((NOW + timedelta(days=1)).isoformat())
        decision = run(
            tmp_path, "token: xoxb-1234567890-abcdef", entries=[entry]
        )
        assert decision.allowed
        assert [f.kind for f in decision.allowlisted] == ["secret"]

    def test_live_entry_with_wrong_token_permits_nothing(self, tmp_path):
        """A live entry must match the finding TOKEN, not just the
        kind — pins AllowlistEntry.permits token equality (QG D1 r1
        M1, mutant M24)."""
        entry = self.secret_entry(
            (NOW + timedelta(days=1)).isoformat(), token="OpenAI key"
        )
        decision = run(
            tmp_path, "token: xoxb-1234567890-abcdef", entries=[entry]
        )
        assert not decision.allowed

    def test_live_entry_with_wrong_kind_permits_nothing(self, tmp_path):
        """A home-path entry whose token equals the secret label must
        not clear a secret finding — pins kind equality (mutant M25)."""
        entry = {
            "kind": "home-path", "token": "Slack token",
            "reason": "wrong kind on purpose",
            "expires": (NOW + timedelta(days=1)).isoformat(),
        }
        decision = run(
            tmp_path, "token: xoxb-1234567890-abcdef", entries=[entry]
        )
        assert not decision.allowed

    def test_entry_without_reason_permits_nothing(self, tmp_path):
        entry = {
            "kind": "secret", "token": "Slack token",
            "expires": (NOW + timedelta(days=1)).isoformat(),
        }
        decision = run(
            tmp_path, "token: xoxb-1234567890-abcdef", entries=[entry]
        )
        assert not decision.allowed

    def test_client_identifier_entry_never_clears_even_when_live(self):
        """permits() refuses unallowlistable kinds even against a LIVE
        entry list — the double guard's outer layer, tested with a
        non-empty list so any() is not vacuous (QG D1 r1 M1)."""
        live = [
            AllowlistEntry(
                kind="secret", token="x", reason="r",
                expires=NOW + timedelta(days=1), destinations=(),
            )
        ]
        assert not allowlist.permits(live, "client-identifier", "x", DEST)
        assert not allowlist.permits(
            live, "redaction-config-missing", "", DEST
        )
        assert {"secret", "home-path"} == allowlist.ALLOWLISTABLE_KINDS

    def test_outer_kind_guard_decides_alone(self):
        """A directly-constructed entry of an unallowlistable kind —
        impossible via _parse_entry — still permits nothing: the OUTER
        guard in permits() is load-bearing on its own, not shadowed by
        entry-side kind equality (QG D1 r2 F-M3, mutant M05)."""
        forged = [
            AllowlistEntry(
                kind="client-identifier", token="x", reason="r",
                expires=NOW + timedelta(days=1), destinations=(),
            )
        ]
        assert not allowlist.permits(forged, "client-identifier", "x", DEST)

    def test_expired_entry_permits_nothing(self, tmp_path):
        entry = self.secret_entry((NOW - timedelta(seconds=1)).isoformat())
        decision = run(
            tmp_path, "token: xoxb-1234567890-abcdef", entries=[entry]
        )
        assert not decision.allowed

    def test_naive_expiry_is_invalid(self, tmp_path):
        entry = self.secret_entry("2099-01-01T00:00:00")  # no timezone
        decision = run(
            tmp_path, "token: xoxb-1234567890-abcdef", entries=[entry]
        )
        assert not decision.allowed

    def test_naive_expiry_dropped_per_entry_not_whole_file(self, tmp_path):
        """One naive entry must not drop its valid sibling — pins that
        _parse_entry rejects the naive expiry ITSELF, instead of the
        broad file-level catch masking a comparison TypeError (QG D1
        r2 F-M4, mutant M10)."""
        naive = self.secret_entry("2099-01-01T00:00:00")
        valid = self.secret_entry((NOW + timedelta(days=1)).isoformat())
        path = write_allowlist(tmp_path, [naive, valid])
        entries = allowlist.active_entries(path, NOW)
        assert len(entries) == 1
        assert entries[0].expires.tzinfo is not None

    @pytest.mark.parametrize(
        "raw",
        [
            "just-a-string",
            {"kind": "secret", "token": "x", "reason": "r"},  # no expires
            {"kind": "client-identifier", "token": "x", "reason": "r",
             "expires": "2099-01-01T00:00:00+00:00"},  # unallowlistable
            {"kind": "secret", "token": "", "reason": "r",
             "expires": "2099-01-01T00:00:00+00:00"},  # empty token
            {"kind": "secret", "token": "x", "reason": "r",
             "expires": 12345},  # non-str expires
            {"kind": "secret", "token": "x", "reason": "r",
             "expires": "not-a-date"},  # unparseable expires
            {"kind": "secret", "token": "x", "reason": "r",
             "expires": "2099-01-01T00:00:00+00:00",
             "destinations": "notebooklm"},  # destinations not a list
        ],
    )
    def test_malformed_entry_shapes_are_dropped(self, tmp_path, raw):
        """Every malformed shape lands in the deny direction (QG D1 r2
        F-M7 — the defensive branches, executed rather than trusted)."""
        path = write_allowlist(tmp_path, [raw])
        assert allowlist.active_entries(path, NOW) == []

    def test_entries_key_not_a_list_permits_nothing(self, tmp_path):
        path = tmp_path / "allowlist.json"
        path.write_text('{"entries": "not-a-list"}', encoding="utf-8")
        assert allowlist.active_entries(path, NOW) == []

    def test_residual_identifiers_with_no_config_is_empty(self, tmp_path):
        from core.egress.redact import residual_identifiers

        assert residual_identifiers("any text", tmp_path / "absent.json") == []

    def test_wrong_destination_permits_nothing(self, tmp_path):
        entry = self.secret_entry(
            (NOW + timedelta(days=1)).isoformat(), destinations=["other"]
        )
        decision = run(
            tmp_path, "token: xoxb-1234567890-abcdef", entries=[entry]
        )
        assert not decision.allowed

    def test_malformed_allowlist_degrades_to_deny(self, tmp_path):
        path = tmp_path / "allowlist.json"
        path.write_text("{broken", encoding="utf-8")
        cfg = write_clients(tmp_path)
        decision = evaluate(
            "token: xoxb-1234567890-abcdef", DEST, config_path=cfg,
            home=tmp_path / "home", allowlist_path=path,
            audit_path=tmp_path / "audit.jsonl", now=NOW,
        )
        assert not decision.allowed

    def test_default_allowlist_path_lands_under_home(self, tmp_path):
        assert (
            allowlist.default_allowlist_path(tmp_path)
            == tmp_path / ".arkaos" / "egress" / "allowlist.json"
        )


class TestAudit:
    def read_lines(self, tmp_path):
        raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in raw.splitlines()]

    def test_allow_and_deny_are_both_recorded(self, tmp_path):
        run(tmp_path, "clean text")
        run(tmp_path, "token: xoxb-1234567890-abcdef")
        lines = self.read_lines(tmp_path)
        assert [entry["allowed"] for entry in lines] == [True, False]

    def test_audit_never_contains_raw_material(self, tmp_path):
        home = tmp_path / "home"
        run(
            tmp_path,
            f"acme-alpha secret xoxb-1234567890-abc at {home}/Work/x",
        )
        raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").lower()
        assert "acme" not in raw
        assert "xoxb" not in raw
        assert str(home).lower() not in raw
        entry = self.read_lines(tmp_path)[0]
        assert all(len(f["token_sha16"]) == 16 for f in entry["findings"]
                   if f["token_sha16"])

    def test_audit_permissions(self, tmp_path):
        run(tmp_path, "clean text")
        assert (tmp_path / "audit.jsonl").stat().st_mode & 0o777 == 0o600

    def test_preexisting_loose_audit_file_is_repaired(self, tmp_path):
        """0o600 at open applies only at creation — the explicit chmod
        must repair a pre-existing 0666 file (QG D1 r1 M2)."""
        target = tmp_path / "audit.jsonl"
        target.write_text("", encoding="utf-8")
        target.chmod(0o666)
        run(tmp_path, "clean text")
        assert target.stat().st_mode & 0o777 == 0o600

    def test_audit_parent_directory_mode_is_0700(self, tmp_path):
        """The parent starts at 0o777 so the assertion discriminates —
        pytest's tmp_path is already 0700, which made the r2 version
        tautological (QG D1 r2 F-M2, mutant M17)."""
        cfg = write_clients(tmp_path)
        loose = tmp_path / "loose-dir"
        loose.mkdir(mode=0o777)
        loose.chmod(0o777)
        evaluate(
            "clean text", DEST, config_path=cfg, home=tmp_path / "home",
            allowlist_path=tmp_path / "a.json",
            audit_path=loose / "audit.jsonl", now=NOW,
        )
        assert loose.stat().st_mode & 0o777 == 0o700

    def test_unauditable_allow_flips_to_denied(self, tmp_path, monkeypatch):
        monkeypatch.setattr(policy.audit, "record", lambda *a, **k: False)
        decision = run(tmp_path, "clean text")
        assert not decision.allowed
        assert decision.redacted_text is None
        assert "audit-unavailable" in kinds(decision)

    def test_denied_decision_with_failed_audit_stays_denied(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(policy.audit, "record", lambda *a, **k: False)
        decision = run(tmp_path, "token: xoxb-1234567890-abcdef")
        assert not decision.allowed
        assert decision.audited is False


class TestAuditModule:
    def test_hash_token_is_stable_and_short(self):
        assert audit.hash_token("acme-alpha") == audit.hash_token("acme-alpha")
        assert len(audit.hash_token("acme-alpha")) == 16
        assert audit.hash_token("acme-alpha") != audit.hash_token("betacorp")

    def test_salt_defeats_dictionary_confirmation(self, tmp_path):
        """The finding tokens are low-entropy and enumerable, so an
        unsalted digest is a confirm-a-guess oracle (QG D1 r2 F-M1 —
        reversed from a 9-candidate dictionary in microseconds). With
        the per-install salt, the same token hashes differently per
        install, and the unsalted guess no longer matches."""
        salt_a = audit.load_or_create_salt(tmp_path / "a" / ".audit-salt")
        salt_b = audit.load_or_create_salt(tmp_path / "b" / ".audit-salt")
        assert salt_a != salt_b
        unsalted_guess = audit.hash_token("acme-alpha")
        assert audit.hash_token("acme-alpha", salt_a) != unsalted_guess
        assert audit.hash_token("acme-alpha", salt_a) != audit.hash_token(
            "acme-alpha", salt_b
        )

    def test_salt_is_stable_per_install_and_0600(self, tmp_path):
        path = tmp_path / ".audit-salt"
        first = audit.load_or_create_salt(path)
        second = audit.load_or_create_salt(path)
        assert first == second
        assert len(first) == 16
        assert path.stat().st_mode & 0o777 == 0o600

    def test_unwritable_salt_degrades_to_empty_never_raises(self, tmp_path):
        blocked = tmp_path / "dir-as-salt"
        blocked.mkdir()
        assert audit.load_or_create_salt(blocked) == b""

    def test_salt_parent_directory_is_narrowed_to_0700(self, tmp_path):
        """The salt dir is narrowed even when the audit trail lives
        elsewhere (QG D1 r3 F-M4)."""
        loose = tmp_path / "salts"
        loose.mkdir(mode=0o777)
        loose.chmod(0o777)
        audit.load_or_create_salt(loose / ".audit-salt")
        assert loose.stat().st_mode & 0o777 == 0o700

    def test_concurrent_creator_in_flight_write_is_retried(
        self, tmp_path, monkeypatch
    ):
        """A concurrent creator's O_EXCL file exists BEFORE its bytes
        land — an empty read means not-yet-created, and the retry gets
        the real salt instead of silently degrading (QG D1 r3 F-M1)."""
        path = tmp_path / ".audit-salt"
        path.write_bytes(b"")  # exists, zero bytes: writer in flight
        reads = iter([b"", b"", b"real-salt-16byte"])
        monkeypatch.setattr(
            audit, "_read_salt", lambda p: next(reads, b"real-salt-16byte")
        )
        monkeypatch.setattr(audit.time, "sleep", lambda s: None)
        assert audit.load_or_create_salt(path) == b"real-salt-16byte"

    def test_permanently_empty_salt_file_degrades_to_empty(
        self, tmp_path, monkeypatch
    ):
        path = tmp_path / ".audit-salt"
        path.write_bytes(b"")  # crashed creator, never written
        monkeypatch.setattr(audit.time, "sleep", lambda s: None)
        assert audit.load_or_create_salt(path) == b""

    def test_audit_lines_use_the_salted_hash(self, tmp_path):
        """End-to-end: the token_sha16 persisted for a finding must be
        the SALTED digest, not the unsalted one a dictionary attacker
        can precompute."""
        cfg = write_clients(tmp_path)
        home = tmp_path / "home"
        evaluate(
            "token: xoxb-1234567890-abcdef", DEST, config_path=cfg,
            home=home, allowlist_path=tmp_path / "a.json",
            audit_path=tmp_path / "audit.jsonl", now=NOW,
        )
        line = json.loads(
            (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
        )
        salt = audit.load_or_create_salt(audit.default_salt_path(home))
        assert line["findings"][0]["token_sha16"] == audit.hash_token(
            "Slack token", salt
        )
        assert line["findings"][0]["token_sha16"] != audit.hash_token(
            "Slack token"
        )

    def test_record_failure_returns_false(self, tmp_path):
        target = tmp_path / "dir-as-file"
        target.mkdir()
        assert audit.record({"a": 1}, target) is False

    def test_unserializable_entry_returns_false(self, tmp_path):
        assert (
            audit.record({"bad": object()}, tmp_path / "audit.jsonl")
            is False
        )

    def test_default_audit_path_lands_under_home(self, tmp_path):
        assert (
            audit.default_audit_path(tmp_path)
            == tmp_path / ".arkaos" / "egress" / "audit.jsonl"
        )


class TestNoRealClientNames:
    def test_this_file_passes_the_release_leak_gate(self):
        """The confidentiality primitive's own tests must never commit
        a real client name (QG D1 r1 B3). Scans THIS file with the
        operator's live redaction list when present; on machines
        without the config the scan is a structural no-op by design."""
        from core.governance.leak_scanner import scan_paths

        report = scan_paths([Path(__file__)])
        assert report.hits == []
