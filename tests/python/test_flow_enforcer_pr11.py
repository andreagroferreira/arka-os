"""PR11 v2.33.0 — Discovery vs Effect tool taxonomy tests.

Covers the bash_is_effect classifier and the expanded EFFECT_TOOLS_ALWAYS
set. Earlier tests live in test_flow_enforcer.py and continue to cover
the original Write/Edit/MultiEdit gating path.
"""

from __future__ import annotations

import pytest

from core.workflow.flow_enforcer import (
    EFFECT_TOOLS_ALWAYS,
    GATED_TOOLS,
    bash_is_effect,
    evaluate,
)


class TestEffectToolsAlwaysSet:
    def test_includes_legacy_write_edit_multiedit(self):
        assert "Write" in EFFECT_TOOLS_ALWAYS
        assert "Edit" in EFFECT_TOOLS_ALWAYS
        assert "MultiEdit" in EFFECT_TOOLS_ALWAYS

    def test_includes_notebook_edit(self):
        assert "NotebookEdit" in EFFECT_TOOLS_ALWAYS

    def test_includes_agent_dispatch_and_skill(self):
        assert "Task" in EFFECT_TOOLS_ALWAYS
        assert "Skill" in EFFECT_TOOLS_ALWAYS

    def test_excludes_discovery_tools(self):
        for discovery in ("Read", "Grep", "Glob", "ToolSearch", "AskUserQuestion"):
            assert discovery not in EFFECT_TOOLS_ALWAYS

    def test_excludes_bash_intentionally(self):
        """Bash is classified per-command, not as a blanket gated tool."""
        assert "Bash" not in EFFECT_TOOLS_ALWAYS

    def test_gated_tools_alias_matches_effect_tools(self):
        """Backwards-compat alias preserved."""
        assert GATED_TOOLS == EFFECT_TOOLS_ALWAYS


class TestBashIsEffectDiscovery:
    """Commands that must be classified DISCOVERY (no routing required)."""

    @pytest.mark.parametrize("command", [
        "ls",
        "ls -la",
        "cat /etc/hosts",
        "head -n 20 file.txt",
        "tail -f log.txt",
        "grep -rn pattern src/",
        "rg --json TODO",
        "find . -name '*.py'",
        "pwd",
        "whoami",
        "date",
        "echo hello",
        "git status",
        "git log --oneline -10",
        "git diff HEAD~1",
        "git show abc123",
        "git branch",
        "git rev-parse --abbrev-ref HEAD",
        "npm view arkaos version",
        "npm list",
        "pip list",
        "pip show pydantic",
        "python --version",
        "python3 -c 'import json; print(1+1)'",
        "node --version",
        "wc -l file.txt",
        "sort file.txt | uniq -c",
        "awk '{print $1}' file.txt",
        "ps aux | grep python",
        "df -h",
        "which python3",
        "type cd",
    ])
    def test_known_read_only_commands_are_discovery(self, command: str):
        assert bash_is_effect(command) is False, f"{command!r} should be discovery"

    def test_empty_command_is_not_effect(self):
        assert bash_is_effect("") is False
        assert bash_is_effect("   ") is False

    def test_env_var_assignment_only_is_not_effect(self):
        # `FOO=bar` alone is a variable assignment, no command
        assert bash_is_effect("FOO=bar cat file.txt") is False


class TestBashIsEffectMutation:
    """Commands that must be classified EFFECT (routing required)."""

    @pytest.mark.parametrize("command", [
        "rm file.txt",
        "rm -rf node_modules",
        "mv old.txt new.txt",
        "cp -rf src/ dst/",
        "dd if=/dev/zero of=/tmp/x bs=1M",
        "chmod +x script.sh",
        "chown user:group file",
        "sudo apt update",
        "sudo rm -rf /tmp/x",
        "kill 1234",
        "killall python",
        "pkill -f some-pattern",
        "git commit -m 'feat: x'",
        "git push origin master",
        "git reset --hard HEAD~1",
        "git merge feature/x",
        "git rebase main",
        "git tag v1.0.0",
        "git stash",
        "git stash pop",
        "git checkout -b new-branch",
        "git branch -D old-branch",
        "git cherry-pick abc123",
        "git revert HEAD",
        "npm install lodash",
        "npm i react",
        "npm publish --access public",
        "npm uninstall lodash",
        "yarn add lodash",
        "pnpm add lodash",
        "pip install requests",
        "pip3 install pydantic",
        "uv pip install requests",
        "poetry add fastapi",
        "brew install obsidian",
        "apt install nodejs",
        "snap install obsidian --classic",
        "winget install OpenJS.NodeJS",
        "gh pr create --title x",
        "gh release create v1.0.0",
        "gh issue create --title bug",
        "gh pr merge 42",
        "gh repo delete andreagroferreira/old-project",
        "sed -i 's/foo/bar/' file.txt",
        "perl -i -pe 's/a/b/' file.txt",
        "docker build -t myimage .",
        "docker push myimage",
        "docker run -it ubuntu",
        "scp file.txt user@host:/tmp/",
        "rsync src/ dst/",
    ])
    def test_known_mutating_commands_are_effect(self, command: str):
        assert bash_is_effect(command) is True, f"{command!r} should be effect"

    def test_redirect_to_file_is_effect(self):
        assert bash_is_effect("echo hi > /tmp/file.txt") is True
        assert bash_is_effect("date >> log.txt") is True

    def test_rsync_defaults_to_effect_per_default_deny(self):
        """rsync is in neither blacklist nor whitelist → default-deny.
        Even --dry-run requires routing. Safer than guessing intent
        from flags. Users explicitly emit routing if they want rsync.
        """
        assert bash_is_effect("rsync --dry-run src/ dst/") is True
        assert bash_is_effect("rsync src/ dst/") is True


class TestBashIsEffectDefaultDeny:
    """Unknown commands default to EFFECT (safer)."""

    @pytest.mark.parametrize("command", [
        "totally-made-up-binary --do-stuff",
        "obscure-tool subcommand",
        "/usr/local/bin/custom-script",
    ])
    def test_unknown_commands_are_effect(self, command: str):
        assert bash_is_effect(command) is True


class TestEvaluatePassesToolInput:
    """evaluate() should call bash_is_effect when tool_name == 'Bash'."""

    def test_bash_with_read_only_command_is_not_gated(self, tmp_path):
        decision = evaluate(
            tool_name="Bash",
            transcript_path=str(tmp_path / "no-transcript.jsonl"),
            session_id="",
            cwd="",
            tool_input={"command": "ls -la"},
        )
        assert decision.allow is True
        assert decision.reason == "tool-not-gated"

    def test_bash_with_mutating_command_is_gated(self, tmp_path, monkeypatch):
        # Force the feature flag on and the session flag on so we hit the
        # marker-check path; with no transcript, the result is "no marker".
        from core.workflow import flow_enforcer
        monkeypatch.setattr(flow_enforcer, "_feature_flag_on", lambda: True)
        monkeypatch.setattr(
            flow_enforcer, "_flow_required_for_session", lambda sid: True
        )
        # Clear marker cache for this session
        monkeypatch.setattr(
            flow_enforcer.marker_cache, "read_marker", lambda sid: None
        )
        decision = evaluate(
            tool_name="Bash",
            transcript_path=str(tmp_path / "no-transcript.jsonl"),
            session_id="test-bash-mutating",
            cwd="",
            tool_input={"command": "rm -rf /tmp/x"},
        )
        # Without a marker, mutating Bash should be denied
        assert decision.allow is False
        assert "no-flow-marker" in decision.reason

    def test_bash_without_tool_input_treats_command_as_empty(self, tmp_path):
        """No tool_input means empty Bash command — not effect, allowed."""
        decision = evaluate(
            tool_name="Bash",
            transcript_path=str(tmp_path / "no-transcript.jsonl"),
            session_id="",
            cwd="",
            tool_input=None,
        )
        assert decision.allow is True

    def test_notebook_edit_is_gated_like_write(self, tmp_path, monkeypatch):
        from core.workflow import flow_enforcer
        monkeypatch.setattr(flow_enforcer, "_feature_flag_on", lambda: True)
        monkeypatch.setattr(
            flow_enforcer, "_flow_required_for_session", lambda sid: True
        )
        monkeypatch.setattr(
            flow_enforcer.marker_cache, "read_marker", lambda sid: None
        )
        decision = evaluate(
            tool_name="NotebookEdit",
            transcript_path=str(tmp_path / "no-transcript.jsonl"),
            session_id="test-notebook",
            cwd="",
            tool_input={},
        )
        assert decision.allow is False

    def test_task_agent_dispatch_is_gated(self, tmp_path, monkeypatch):
        from core.workflow import flow_enforcer
        monkeypatch.setattr(flow_enforcer, "_feature_flag_on", lambda: True)
        monkeypatch.setattr(
            flow_enforcer, "_flow_required_for_session", lambda sid: True
        )
        monkeypatch.setattr(
            flow_enforcer.marker_cache, "read_marker", lambda sid: None
        )
        decision = evaluate(
            tool_name="Task",
            transcript_path=str(tmp_path / "no-transcript.jsonl"),
            session_id="test-task",
            cwd="",
            tool_input={"subagent_type": "Explore"},
        )
        assert decision.allow is False


class TestStderrMessageUpdated:
    def test_stderr_message_mentions_new_tools(self, tmp_path, monkeypatch):
        from core.workflow import flow_enforcer
        monkeypatch.setattr(flow_enforcer, "_feature_flag_on", lambda: True)
        monkeypatch.setattr(
            flow_enforcer, "_flow_required_for_session", lambda sid: True
        )
        monkeypatch.setattr(
            flow_enforcer.marker_cache, "read_marker", lambda sid: None
        )
        decision = evaluate(
            tool_name="Write",
            transcript_path=str(tmp_path / "no-transcript.jsonl"),
            session_id="test-msg",
            cwd="",
            tool_input={},
        )
        msg = decision.to_stderr_message()
        assert "NotebookEdit" in msg
        assert "Task" in msg
        assert "Skill" in msg
        assert "Bash" in msg
