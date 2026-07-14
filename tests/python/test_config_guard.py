"""Config-protection gate — the agent fixes the code, not the linter."""

import json

import pytest

import core.workflow.config_guard as cg
from core.workflow.config_guard import (
    ConfigGuardDecision,
    evaluate,
    is_protected_config,
    mode,
)


class TestIsProtectedConfig:
    @pytest.mark.parametrize("path", [
        ".eslintrc.json", "eslint.config.mjs", ".prettierrc",
        "biome.json", "ruff.toml", ".flake8", "mypy.ini",
        ".pre-commit-config.yaml", ".php-cs-fixer.dist.php", "phpstan.neon",
        ".rubocop.yml", ".golangci.yml", "rustfmt.toml", ".editorconfig",
        "/abs/path/to/project/.eslintrc.json",
        "nested/deep/.prettierrc",
    ])
    def test_protected_configs(self, path):
        assert is_protected_config(path)

    @pytest.mark.parametrize("path", [
        "src/index.ts", "app/main.py", "README.md",
        # Multi-purpose files are deliberately NOT hard-protected — they
        # hold real project config alongside any tool sections.
        "pyproject.toml", "package.json", "setup.cfg", "tox.ini",
        "", "Makefile",
    ])
    def test_unprotected_files(self, path):
        assert not is_protected_config(path)

    def test_case_insensitive(self):
        assert is_protected_config("RUFF.TOML")


class TestEvaluate:
    def test_ordinary_file_is_allowed(self):
        assert evaluate("src/app.ts").allow

    def test_protected_config_is_denied(self):
        d = evaluate(".eslintrc.json")
        assert not d.allow
        assert d.reason == "protected-config"
        assert ".eslintrc.json" in d.to_stderr_message()
        assert "fix the underlying code" in d.to_stderr_message().lower()

    def test_env_bypass_allows(self, monkeypatch):
        monkeypatch.setenv("ARKA_BYPASS_CONFIG_GUARD", "1")
        d = evaluate("ruff.toml")
        assert d.allow
        assert d.reason == "env-bypass"

    def test_env_bypass_must_be_exactly_one(self, monkeypatch):
        monkeypatch.setenv("ARKA_BYPASS_CONFIG_GUARD", "yes")
        assert not evaluate("ruff.toml").allow

    def test_operator_naming_the_file_allows(self):
        messages = ["please bump the rules in ruff.toml to add S101"]
        d = evaluate("ruff.toml", messages)
        assert d.allow
        assert d.reason == "operator-named-file"

    def test_operator_naming_a_different_file_does_not_allow(self):
        messages = ["fix the lint error in src/app.ts"]
        assert not evaluate("ruff.toml", messages).allow

    def test_partial_name_match_does_not_count(self):
        assert not evaluate("ruff.toml", ["look at ruff.tomlx"]).allow

    def test_dotted_suffix_does_not_authorise_the_base(self):
        # The P0-adjacent regex bug: 'ruff.toml.bak' must not authorise
        # an edit to 'ruff.toml'.
        assert not evaluate("ruff.toml", ["diff ruff.toml.bak against it"]).allow

    @pytest.mark.parametrize("mention", [
        "ruff.toml.bak", "ruff.toml~", "ruff.toml-old",
    ])
    def test_sibling_files_do_not_authorise_the_base(self, mention):
        assert not evaluate("ruff.toml", [f"look at {mention}"]).allow

    def test_sentence_ending_period_still_matches(self):
        # ...but a trailing period (end of sentence) must still count.
        assert evaluate("ruff.toml", ["please edit ruff.toml."]).allow

    def test_hyphen_with_surrounding_space_still_matches(self):
        # "ruff.toml - the linter config" is a normal mention, not a sibling.
        assert evaluate("ruff.toml", ["edit ruff.toml - the config"]).allow

    def test_operator_naming_is_case_insensitive(self):
        # is_protected_config lowercases; the override must agree.
        assert evaluate("ruff.toml", ["please edit RUFF.TOML"]).allow

    def test_no_messages_denies_protected(self):
        assert not evaluate(".prettierrc", None).allow

    def test_empty_file_path_is_allowed(self):
        assert evaluate("").allow


class TestDecisionMessage:
    def test_allow_has_no_message(self):
        assert ConfigGuardDecision(allow=True).to_stderr_message() == ""

    def test_deny_names_the_file_and_the_operator_as_the_actor(self):
        msg = ConfigGuardDecision(
            allow=False, file_path="biome.json").to_stderr_message()
        assert "biome.json" in msg
        assert "ARKA_BYPASS_CONFIG_GUARD" in msg
        # The actor who can lift the block is the OPERATOR, not the agent
        # reading this on stderr.
        assert "OPERATOR" in msg


class TestMode:
    def test_default_is_warn_when_no_config(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cg, "CONFIG_PATH", tmp_path / "nope.json")
        assert mode() == "warn"

    @pytest.mark.parametrize("raw,expected", [
        ("off", "off"), (False, "off"), ("false", "off"),
        ("hard", "hard"), (True, "hard"), ("true", "hard"),
        ("warn", "warn"), ("anything-else", "warn"),
    ])
    def test_mode_resolution(self, raw, expected, monkeypatch, tmp_path):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"hooks": {"configGuard": raw}}))
        monkeypatch.setattr(cg, "CONFIG_PATH", config)
        assert mode() == expected

    def test_unreadable_config_degrades_to_warn_not_hard(
        self, monkeypatch, tmp_path
    ):
        config = tmp_path / "config.json"
        config.write_text("{ broken json")
        monkeypatch.setattr(cg, "CONFIG_PATH", config)
        assert mode() == "warn"


def _transcript(tmp_path, *records) -> str:
    """Write a JSONL transcript; each record is (role, text, sidechain?)."""
    lines = []
    for role, text, *rest in records:
        side = rest[0] if rest else False
        lines.append(json.dumps({
            "isSidechain": side,
            "message": {"role": role, "content": text},
        }))
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


class TestThroughMain:
    """Drive the real pre_tool_use.main() entrypoint with a real
    transcript. This is the gate that catches the P0 the unit tests
    could not see: production feeds the gate a TRANSCRIPT, and the
    override must read the OPERATOR's messages, not the agent's.
    """

    @pytest.fixture
    def hard_mode(self, monkeypatch, tmp_path):
        import core.hooks.pre_tool_use  # noqa: F401 — ensure importable
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"hooks": {"configGuard": "hard"}}))
        monkeypatch.setattr(cg, "CONFIG_PATH", config)
        return tmp_path

    @staticmethod
    def _run(transcript_path, file_path="ruff.toml", tool="Edit"):
        from core.hooks.pre_tool_use import main
        return main({
            "tool_name": tool,
            "session_id": "s1",
            "transcript_path": transcript_path,
            "cwd": ".",
            "tool_input": {"file_path": file_path},
        })

    def test_operator_named_the_file_is_allowed(self, hard_mode, capsys):
        # The operator asked; the agent obeys. Must ALLOW.
        tp = _transcript(hard_mode, ("user", "please edit ruff.toml to add S101"))
        assert self._run(tp) == 0

    def test_agent_naming_the_file_cannot_self_authorise(
        self, hard_mode, capsys
    ):
        # The P0: the file is named only in the ASSISTANT's own message.
        # The guarded actor must NOT be able to lift its own block.
        tp = _transcript(
            hard_mode,
            ("user", "make the lint pass"),
            ("assistant", "I'll just edit ruff.toml to disable S101"),
        )
        assert self._run(tp) == 2

    def test_unnamed_protected_edit_is_denied(self, hard_mode, capsys):
        tp = _transcript(hard_mode, ("user", "make the lint pass"))
        assert self._run(tp) == 2

    def test_sidechain_user_turn_is_not_the_operator(self, hard_mode, capsys):
        # A dispatched subagent's prompt is not the operator speaking.
        tp = _transcript(
            hard_mode, ("user", "edit ruff.toml please", True))
        assert self._run(tp) == 2

    def test_ordinary_file_is_never_gated(self, hard_mode, capsys):
        tp = _transcript(hard_mode, ("user", "anything"))
        assert self._run(tp, file_path="src/app.py") == 0

    def test_unreadable_transcript_fails_closed_in_hard_mode(
        self, hard_mode, capsys
    ):
        # No override can be read → treat as un-authorised → deny.
        assert self._run("/nonexistent/transcript.jsonl") == 2

    def test_env_bypass_works_without_a_transcript(
        self, hard_mode, capsys, monkeypatch
    ):
        # The escape hatch that never depends on the transcript.
        monkeypatch.setenv("ARKA_BYPASS_CONFIG_GUARD", "1")
        assert self._run("/nonexistent/transcript.jsonl") == 0

    def test_warn_mode_never_blocks(self, monkeypatch, tmp_path, capsys):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"hooks": {"configGuard": "warn"}}))
        monkeypatch.setattr(cg, "CONFIG_PATH", config)
        tp = _transcript(tmp_path, ("user", "make lint pass"))
        assert self._run(tp) == 0
        assert "[arka:config-guard]" in capsys.readouterr().err

    def test_off_mode_is_silent(self, monkeypatch, tmp_path, capsys):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"hooks": {"configGuard": "off"}}))
        monkeypatch.setattr(cg, "CONFIG_PATH", config)
        tp = _transcript(tmp_path, ("user", "make lint pass"))
        assert self._run(tp) == 0
        assert "[arka:config-guard]" not in capsys.readouterr().err

    def test_notebookedit_is_never_config_gated(self, hard_mode, capsys):
        # NotebookEdit addresses notebook_path, never a linter config.
        tp = _transcript(hard_mode, ("user", "x"))
        assert self._run(tp, tool="NotebookEdit") == 0


class TestUserMessageSource:
    """The transcript reader that makes the override read the operator,
    not the agent — the fix for the P0."""

    @staticmethod
    def _src():
        from core.workflow.transcript_scope import (
            recent_user_messages,
            user_messages_from_path,
        )
        return recent_user_messages, user_messages_from_path

    def test_collects_only_user_role(self):
        recent, _ = self._src()
        raw = "\n".join([
            json.dumps({"message": {"role": "user", "content": "hello"}}),
            json.dumps({"message": {"role": "assistant", "content": "hi"}}),
            json.dumps({"message": {"role": "user", "content": "world"}}),
        ])
        assert recent(raw) == ["hello", "world"]

    def test_excludes_sidechain_user_turns(self):
        recent, _ = self._src()
        raw = "\n".join([
            json.dumps({"message": {"role": "user", "content": "main ask"}}),
            json.dumps({"isSidechain": True,
                        "message": {"role": "user", "content": "subagent"}}),
        ])
        assert recent(raw) == ["main ask"]

    def test_limit_keeps_the_most_recent(self):
        recent, _ = self._src()
        raw = "\n".join(
            json.dumps({"message": {"role": "user", "content": str(i)}})
            for i in range(10)
        )
        assert recent(raw, limit=3) == ["7", "8", "9"]

    def test_broken_lines_are_skipped(self):
        recent, _ = self._src()
        raw = "not json\n" + json.dumps(
            {"message": {"role": "user", "content": "ok"}})
        assert recent(raw) == ["ok"]

    @pytest.mark.parametrize("record", [
        {"message": "a bare string, not a dict"},
        ["a list, not a dict"],
        {"message": {"role": "user"}},   # no content
        "plain string record",
    ])
    def test_malformed_records_never_raise(self, record):
        recent, _ = self._src()
        raw = json.dumps(record) + "\n" + json.dumps(
            {"message": {"role": "user", "content": "real"}})
        assert recent(raw) == ["real"]  # bad record skipped, good one kept

    def test_from_path_missing_file_is_empty(self, tmp_path):
        _, from_path = self._src()
        assert from_path(str(tmp_path / "nope.jsonl")) == []
        assert from_path("") == []

    def test_from_path_reads_a_real_file(self, tmp_path):
        _, from_path = self._src()
        p = tmp_path / "t.jsonl"
        p.write_text(json.dumps(
            {"message": {"role": "user", "content": "hey"}}))
        assert from_path(str(p)) == ["hey"]

    def test_blank_lines_are_skipped(self):
        recent, _ = self._src()
        raw = "\n\n" + json.dumps(
            {"message": {"role": "user", "content": "x"}}) + "\n\n"
        assert recent(raw) == ["x"]

    def test_from_path_on_a_directory_is_empty_not_a_crash(self, tmp_path):
        # read_text on a directory raises IsADirectoryError (an OSError).
        _, from_path = self._src()
        d = tmp_path / "adir"
        d.mkdir()
        assert from_path(str(d)) == []
