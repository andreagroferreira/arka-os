"""Integration fix-ups over the knowledge cluster.

Three properties, each of which was a real hole after the six PRs landed
together:

1. ``--force`` genuinely rebuilds. Incremental indexing skips by content
   hash, so after a chunker, embedder or doctrine-rule change the index
   keeps serving chunks built under the OLD rules and every run reports a
   contented "0 indexed". The test asserts the incremental skip first —
   without that contrast, "forced run indexed a file" proves nothing.

2. The vault is configured, never guessed. The old fallback list was
   headed by one developer's ``~/Documents/Personal``; on another machine
   it either matched nothing or matched something unrelated, silently.

3. Fusion has one implementation. ``recall_cli`` shipped a copy of
   ``lexical.rrf`` with a comment asking for exactly this consolidation.
"""

from __future__ import annotations

import builtins
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

SCRIPT = REPO_ROOT / "scripts" / "knowledge-index.py"


def _load_cli():
    """Load the hyphenated script as a module — it is not importable by name."""
    spec = importlib.util.spec_from_file_location("knowledge_index_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text(
        "# note\n\n" + "alpha beta gamma delta " * 30, encoding="utf-8"
    )
    return vault


def _indexed_sources(db: Path) -> set[str]:
    """Read the chunk table directly — no store API between the assertion
    and what is actually on disk."""
    import sqlite3

    con = sqlite3.connect(db)
    try:
        return {row[0] for row in con.execute("select distinct source from chunks")}
    finally:
        con.close()


def _runner(cli, vault: Path, db: Path, monkeypatch, capsys):
    def run(*extra: str) -> dict:
        monkeypatch.setattr(
            sys,
            "argv",
            ["knowledge-index.py", "--dir", str(vault), "--db", str(db),
             "--json", *extra],
        )
        assert cli.main() == 0
        return json.loads(capsys.readouterr().out)

    return run


# ── 1. --force actually rebuilds ─────────────────────────────────────────

def test_force_reindexes_what_an_incremental_run_skips(
    tmp_path, monkeypatch, capsys
):
    vault = _make_vault(tmp_path)
    db = tmp_path / "knowledge.db"
    run = _runner(_load_cli(), vault, db, monkeypatch, capsys)

    first = run()
    assert first["files_indexed"] == 1

    # The behaviour --force exists to override. Asserted explicitly so the
    # forced run below is a contrast and not a coincidence.
    incremental = run()
    assert incremental["files_indexed"] == 0
    assert incremental["files_skipped"] == 1

    forced = run("--force")
    assert forced["files_indexed"] == 1
    assert forced["chunks_created"] > 0


def test_reindex_is_the_same_flag_as_force(tmp_path, monkeypatch, capsys):
    vault = _make_vault(tmp_path)
    db = tmp_path / "knowledge.db"
    run = _runner(_load_cli(), vault, db, monkeypatch, capsys)

    run()
    assert run()["files_indexed"] == 0
    assert run("--reindex")["files_indexed"] == 1


def test_force_disables_the_hash_skip_as_well_as_wiping(
    tmp_path, monkeypatch, capsys
):
    """--force must not lean solely on the wipe.

    Emptying the store already makes every file look unindexed, so a test
    that only checks "files were reindexed" passes even if the hash skip
    is left on. This pins the second guarantee directly at the call, so
    the two cannot silently collapse into one.
    """
    import core.knowledge.indexer as indexer_module

    vault = _make_vault(tmp_path)
    db = tmp_path / "knowledge.db"
    cli = _load_cli()
    run = _runner(cli, vault, db, monkeypatch, capsys)

    seen: list[bool] = []
    real_index_directory = indexer_module.index_directory

    def spy(directory, store, **kwargs):
        seen.append(kwargs.get("skip_indexed", True))
        return real_index_directory(directory, store, **kwargs)

    monkeypatch.setattr(indexer_module, "index_directory", spy)

    run()
    assert seen == [True], "a plain run must stay incremental"
    run("--force")
    assert seen == [True, False], "--force must turn the hash skip off"


def test_force_rebuilds_both_sidecars(tmp_path, monkeypatch, capsys):
    """A forced rebuild must refresh the doctrine and lexical sidecars.

    Rebuilding chunks while leaving the sidecars stale is the failure this
    flag is supposed to prevent, so the run reports on both.
    """
    from core.knowledge import lexical

    vault = _make_vault(tmp_path)
    doctrine_dir = vault / "Resources" / "Books" / "T"
    doctrine_dir.mkdir(parents=True)
    (doctrine_dir / "ch1.md").write_text(
        "---\ntype: book-chapter\ndomain: [testing]\n---\n\n" + "word " * 60,
        encoding="utf-8",
    )
    db = tmp_path / "knowledge.db"
    run = _runner(_load_cli(), vault, db, monkeypatch, capsys)

    run()
    forced = run("--force")

    assert forced["doctrine_notes"] == 1
    # Asserted in both worlds rather than skipped: FTS5 is compiled into
    # most SQLite builds but not guaranteed, and the fail-open path is
    # itself a property worth pinning.
    if lexical.fts5_available():
        assert forced["lexical_rebuilt"] is True
        assert lexical.index_path(db).is_file()
    else:
        assert forced["lexical_rebuilt"] is False


def test_force_evicts_notes_deleted_from_the_vault(
    tmp_path, monkeypatch, capsys
):
    """This is what the wipe buys, and nothing else in --force does it.

    An incremental walk only ever visits files that still exist, so a note
    deleted from the vault keeps its chunks in the index indefinitely.
    Orphaned chunks have already bitten this system once.
    """
    vault = _make_vault(tmp_path)
    doomed = vault / "doomed.md"
    doomed.write_text("# doomed\n\n" + "epsilon zeta eta " * 30, encoding="utf-8")
    db = tmp_path / "knowledge.db"
    run = _runner(_load_cli(), vault, db, monkeypatch, capsys)

    run()
    assert str(doomed) in _indexed_sources(db)

    doomed.unlink()
    run("--force")

    sources = _indexed_sources(db)
    assert str(doomed) not in sources, "deleted note survived a forced rebuild"
    assert str(vault / "note.md") in sources, "surviving note was lost"


def test_clear_empties_the_chunk_table(tmp_path, monkeypatch, capsys):
    vault = _make_vault(tmp_path)
    db = tmp_path / "knowledge.db"
    run = _runner(_load_cli(), vault, db, monkeypatch, capsys)
    run()
    assert _indexed_sources(db)

    monkeypatch.setattr(
        sys, "argv",
        ["knowledge-index.py", "--db", str(db), "--clear", "--json"],
    )
    assert _load_cli().main() == 0
    assert _indexed_sources(db) == set()


def test_clear_removes_the_lexical_sidecar(tmp_path, monkeypatch, capsys):
    """"Cleared" must mean cleared — the sidecar is a separate file, and
    leaving it behind keeps the wiped corpus readable on disk."""
    from core.knowledge import lexical

    if not lexical.fts5_available():
        return  # nothing to leave behind on a build without FTS5

    vault = _make_vault(tmp_path)
    db = tmp_path / "knowledge.db"
    run = _runner(_load_cli(), vault, db, monkeypatch, capsys)
    run()
    assert lexical.index_path(db).is_file()

    monkeypatch.setattr(
        sys, "argv",
        ["knowledge-index.py", "--db", str(db), "--clear", "--json"],
    )
    assert _load_cli().main() == 0
    assert not lexical.index_path(db).exists()


# ── 2. the vault is configured, never guessed ────────────────────────────

def test_no_personal_path_is_guessed_in_the_script():
    source = SCRIPT.read_text(encoding="utf-8")
    # The quoted literal, not the word: prose about the removed fallback is
    # welcome, a path segment a guess would have to build is not.
    assert '"Documents"' not in source, (
        "the ~/Documents/... guess list is back in the indexer"
    )
    assert "common_vaults" not in source
    # Delegates to the shared resolver rather than resolving locally.
    assert "from core.knowledge.vault import resolve_vault_with_source" in source


def test_unconfigured_vault_resolves_to_nothing(tmp_path, monkeypatch):
    from core.knowledge.vault import resolve_vault_path

    monkeypatch.delenv("ARKAOS_VAULT", raising=False)
    assert resolve_vault_path(tmp_path / "absent.json") is None


def test_a_personal_looking_folder_is_never_adopted(tmp_path, monkeypatch):
    """Recreates exactly what the old fallback matched — an existing
    ``~/Documents/Personal`` holding a ``.obsidian`` directory — and
    asserts nothing adopts it."""
    from core.knowledge import vault as vault_module

    home = tmp_path / "home"
    (home / "Documents" / "Personal" / ".obsidian").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("ARKAOS_VAULT", raising=False)

    assert vault_module.resolve_vault_path(tmp_path / "absent.json") is None


def test_canonical_resolver_outranks_both_legacy_files(tmp_path, monkeypatch):
    """The documented key must win.

    It used to be consulted third, so an operator who set
    knowledge.vaultPath could still be indexed from a stale legacy file
    and never be told which one won.
    """
    from core.knowledge import vault as vault_module

    cli = _load_cli()
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    legacy = tmp_path / "legacy"
    legacy.mkdir()

    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"knowledge": {"vaultPath": str(canonical)}}), encoding="utf-8"
    )
    monkeypatch.setattr(vault_module, "CONFIG_PATH", cfg)
    monkeypatch.delenv("ARKAOS_VAULT", raising=False)
    monkeypatch.setattr(cli, "_legacy_obsidian_config", lambda: str(legacy))
    monkeypatch.setattr(cli, "_legacy_profile_vault", lambda: str(legacy))

    assert cli.resolve_index_directory() == str(canonical)


def test_legacy_source_is_used_but_announced_as_deprecated(
    tmp_path, monkeypatch, capsys
):
    from core.knowledge import vault as vault_module

    cli = _load_cli()
    legacy = tmp_path / "legacy"
    legacy.mkdir()

    monkeypatch.setattr(vault_module, "CONFIG_PATH", tmp_path / "absent.json")
    monkeypatch.delenv("ARKAOS_VAULT", raising=False)
    monkeypatch.setattr(cli, "_legacy_obsidian_config", lambda: str(legacy))

    assert cli.resolve_index_directory() == str(legacy)
    err = capsys.readouterr().err
    assert "obsidian-config.json" in err
    assert "DEPRECATED" in err


def test_resolution_notes_reach_stderr_even_in_json_mode(tmp_path, monkeypatch, capsys):
    """stdout is the JSON channel; stderr is not. Gating diagnostics on
    --json only hid the chosen corpus from whoever was automating."""
    cli = _load_cli()
    cli._note("chosen: /some/vault")
    captured = capsys.readouterr()
    assert "chosen: /some/vault" in captured.err
    assert captured.out == ""


def test_no_configured_vault_fails_instead_of_indexing_arkaos_itself(
    tmp_path, monkeypatch, capsys
):
    """The departments/ fallback indexed ArkaOS's own docs as the user's
    knowledge base and exited 0 — a successful-looking run answering from
    the wrong corpus."""
    cli = _load_cli()
    monkeypatch.setattr(cli, "resolve_index_directory", lambda: "")

    import core.knowledge.indexer as indexer_module

    called: list[str] = []
    monkeypatch.setattr(
        indexer_module, "index_directory",
        lambda directory, store, **kw: called.append(str(directory)),
    )
    monkeypatch.setattr(
        sys, "argv",
        ["knowledge-index.py", "--db", str(tmp_path / "k.db")],
    )

    assert cli.main() == 2, "must not exit 0 with no vault configured"
    assert called == [], "nothing may be indexed when no vault resolved"
    err = capsys.readouterr().err
    assert "knowledge.vaultPath" in err
    assert "departments" not in err


def test_departments_fallback_is_gone_from_the_source():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "Indexing ArkaOS skills" not in source
    assert 'ARKAOS_ROOT / "departments"' not in source


def test_config_wins_over_env(tmp_path, monkeypatch):
    from core.knowledge.vault import resolve_vault_path

    configured = tmp_path / "configured"
    configured.mkdir()
    env_vault = tmp_path / "from-env"
    env_vault.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"knowledge": {"vaultPath": str(configured)}}), encoding="utf-8"
    )
    monkeypatch.setenv("ARKAOS_VAULT", str(env_vault))

    assert resolve_vault_path(cfg) == configured


def test_env_serves_when_config_is_absent(tmp_path, monkeypatch):
    from core.knowledge.vault import resolve_vault_path

    env_vault = tmp_path / "from-env"
    env_vault.mkdir()
    monkeypatch.setenv("ARKAOS_VAULT", str(env_vault))

    assert resolve_vault_path(tmp_path / "absent.json") == env_vault


def test_a_configured_path_that_does_not_exist_is_not_returned(
    tmp_path, monkeypatch
):
    from core.knowledge.vault import resolve_vault_path

    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"knowledge": {"vaultPath": str(tmp_path / "gone")}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("ARKAOS_VAULT", raising=False)

    assert resolve_vault_path(cfg) is None


def test_the_research_gate_shares_the_one_resolver(tmp_path, monkeypatch):
    """The gate and the indexer must not be able to disagree about which
    directory is the vault."""
    from core.workflow import research_gate

    vault = tmp_path / "vault"
    vault.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"knowledge": {"vaultPath": str(vault)}}), encoding="utf-8"
    )
    monkeypatch.setattr(research_gate, "CONFIG_PATH", cfg)
    monkeypatch.delenv("ARKAOS_VAULT", raising=False)

    from core.knowledge.vault import resolve_vault_path

    assert research_gate._resolve_vault_path() == resolve_vault_path(cfg) == vault


# ── 3. one fusion implementation ─────────────────────────────────────────

def test_recall_delegates_fusion_to_lexical_rrf(monkeypatch):
    from core.knowledge import lexical, recall_cli

    calls: list[tuple] = []
    real_rrf = lexical.rrf  # bound before patching, or the spy calls itself

    def spy(rankings, top_k=5, k=60):
        calls.append((rankings, top_k))
        return real_rrf(rankings, top_k=top_k, k=k)

    monkeypatch.setattr(lexical, "rrf", spy)
    fused = recall_cli._fuse([["x", "shared"], ["y", "shared"]], top_k=2)

    assert calls, "recall_cli must call lexical.rrf, not reimplement RRF"
    assert calls[0][1] == 2
    assert fused[0] == "shared"


def test_fusion_survives_a_missing_lexical_module(monkeypatch):
    """Without the lexical layer there is only ever one ranking to fuse,
    and RRF over one ranking preserves its order — so the fallback is the
    cut, not a second copy of the algorithm."""
    from core.knowledge import recall_cli

    real_import = builtins.__import__

    def no_lexical(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "core.knowledge" and "lexical" in (fromlist or ()):
            raise ImportError("lexical unavailable on this install")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", no_lexical)

    assert recall_cli._fuse([["a", "b", "c"]], top_k=2) == ["a", "b"]
    assert recall_cli._fuse([], top_k=2) == []


def test_no_second_rrf_implementation_survives_in_recall_cli():
    source = (REPO_ROOT / "core" / "knowledge" / "recall_cli.py").read_text(
        encoding="utf-8"
    )
    assert "1.0 / (" not in source, "RRF arithmetic is back in recall_cli"
    assert "lexical.rrf" in source


# ─── the announced source must be the source that answered (QG C3) ──────


def test_env_vault_is_announced_as_env_not_as_the_config_file(
    tmp_path, monkeypatch, capsys
):
    """resolve_vault_path answers from TWO places. Announcing the config
    file for an ARKAOS_VAULT win is the same 'which source won' ambiguity
    these lines exist to end."""
    from core.knowledge import vault as vault_module

    cli = _load_cli()
    env_vault = tmp_path / "from-env"
    env_vault.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")

    monkeypatch.setattr(vault_module, "CONFIG_PATH", cfg)
    monkeypatch.setenv("ARKAOS_VAULT", str(env_vault))

    assert cli.resolve_index_directory() == str(env_vault)
    err = capsys.readouterr().err
    assert "ARKAOS_VAULT" in err
    assert "config.json" not in err


def test_config_vault_is_announced_as_the_config_file(
    tmp_path, monkeypatch, capsys
):
    from core.knowledge import vault as vault_module

    cli = _load_cli()
    configured = tmp_path / "configured"
    configured.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"knowledge": {"vaultPath": str(configured)}}), encoding="utf-8"
    )
    monkeypatch.setattr(vault_module, "CONFIG_PATH", cfg)
    monkeypatch.delenv("ARKAOS_VAULT", raising=False)

    assert cli.resolve_index_directory() == str(configured)
    err = capsys.readouterr().err
    assert "~/.arkaos/config.json" in err
    assert "ARKAOS_VAULT" not in err


def test_resolver_reports_its_source(tmp_path, monkeypatch):
    from core.knowledge.vault import resolve_vault_with_source

    env_vault = tmp_path / "e"
    env_vault.mkdir()
    monkeypatch.setenv("ARKAOS_VAULT", str(env_vault))
    path, source = resolve_vault_with_source(tmp_path / "absent.json")
    assert (path, source) == (env_vault, "ARKAOS_VAULT")

    monkeypatch.delenv("ARKAOS_VAULT", raising=False)
    assert resolve_vault_with_source(tmp_path / "absent.json") == (None, "")


# ─── one shared db-path lookup (QG C4) ──────────────────────────────────


def test_all_three_consumers_resolve_db_path_through_one_helper():
    """Named for all three, so it checks all three.

    recall_cli kept the private attribute after the other two were
    converted; the indexer then kept its own get_stats() call after
    recall_cli was fixed. The helper's own getattr fallback is the only
    private access that may remain.
    """
    knowledge = REPO_ROOT / "core" / "knowledge"
    for name in ("recall_cli.py", "indexer.py"):
        src = (knowledge / name).read_text(encoding="utf-8")
        assert 'getattr(store, "_db_path"' not in src, f"{name} reaches privately"
        assert 'get_stats()["db_path"]' not in src, f"{name} bypasses the helper"
        assert "store_db_path" in src, f"{name} does not use the shared helper"

    fusion = (knowledge / "lexical_fusion.py").read_text(encoding="utf-8")
    assert fusion.count('getattr(store, "_db_path"') == 1, (
        "the documented test-double fallback inside the helper, and nowhere else"
    )


def test_shared_helper_prefers_the_public_surface():
    from core.knowledge.lexical_fusion import store_db_path

    class _Public:
        def get_stats(self):
            return {"db_path": "/from/get_stats.db"}

        _db_path = "/from/private.db"

    class _DoubleWithoutStats:
        _db_path = "/from/private.db"

    assert store_db_path(_Public()) == "/from/get_stats.db"
    assert store_db_path(_DoubleWithoutStats()) == "/from/private.db"


# ─── CLI surface measured in-process (QG B2) ────────────────────────────
#
# These run main() in this process rather than through subprocess.run, so
# coverage can see them. The two subprocess smokes that remain live in
# test_knowledge_lexical.py, where a fresh process IS the property under
# test (the WAL checkpoint) and where the exit-code contract is asserted.


def _cli_run(cli, monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["knowledge-index.py", *argv])
    code = cli.main()
    return code, capsys.readouterr()


def test_stats_reports_the_index(tmp_path, monkeypatch, capsys):
    vault = _make_vault(tmp_path)
    db = tmp_path / "k.db"
    cli = _load_cli()
    _runner(cli, vault, db, monkeypatch, capsys)()

    code, out = _cli_run(cli, monkeypatch, capsys, "--db", str(db), "--stats")
    assert code == 0
    assert "Chunks:" in out.out
    assert "Vec:" in out.out

    code, out = _cli_run(
        cli, monkeypatch, capsys, "--db", str(db), "--stats", "--json"
    )
    assert code == 0
    assert json.loads(out.out)["total_chunks"] > 0


def test_search_prints_results_and_json(tmp_path, monkeypatch, capsys):
    vault = _make_vault(tmp_path)
    db = tmp_path / "k.db"
    cli = _load_cli()
    _runner(cli, vault, db, monkeypatch, capsys)()

    code, out = _cli_run(
        cli, monkeypatch, capsys, "--db", str(db), "--search", "alpha beta"
    )
    assert code == 0
    assert "Score:" in out.out or "keyword-degraded" in out.out

    code, out = _cli_run(
        cli, monkeypatch, capsys, "--db", str(db), "--search", "alpha", "--json"
    )
    assert code == 0
    assert isinstance(json.loads(out.out), list)


def test_search_with_no_results_says_so(tmp_path, monkeypatch, capsys):
    db = tmp_path / "empty.db"
    cli = _load_cli()
    code, out = _cli_run(
        cli, monkeypatch, capsys, "--db", str(db), "--search", "zzz nothing"
    )
    assert code == 0
    assert "No results found." in out.out


def test_missing_directory_exits_2(tmp_path, monkeypatch, capsys):
    cli = _load_cli()
    code, out = _cli_run(
        cli, monkeypatch, capsys,
        "--dir", str(tmp_path / "absent"), "--db", str(tmp_path / "k.db"),
    )
    assert code == 2
    assert "Directory not found" in out.err


def test_human_output_reports_both_sidecars(tmp_path, monkeypatch, capsys):
    """Non-JSON mode is the operator's view and must name what the run did
    to the doctrine vocabulary and the lexical index."""
    vault = _make_vault(tmp_path)
    cli = _load_cli()
    code, out = _cli_run(
        cli, monkeypatch, capsys,
        "--dir", str(vault), "--db", str(tmp_path / "k.db"),
    )
    assert code == 0
    assert "Files indexed:" in out.out
    assert "Doctrine notes:" in out.out
    assert "Lexical index:" in out.out


def test_legacy_obsidian_config_reads_and_resolves(tmp_path, monkeypatch):
    cli = _load_cli()
    vault = tmp_path / "legacy-vault"
    vault.mkdir()
    root = tmp_path / "root"
    (root / "knowledge").mkdir(parents=True)
    (root / "knowledge" / "obsidian-config.json").write_text(
        json.dumps({"vault_path": str(vault)}), encoding="utf-8"
    )
    monkeypatch.setattr(cli, "ARKAOS_ROOT", root)
    assert cli._legacy_obsidian_config() == str(vault)

    (root / "knowledge" / "obsidian-config.json").write_text(
        "{ not json", encoding="utf-8"
    )
    assert cli._legacy_obsidian_config() == ""


def test_legacy_obsidian_config_absent_or_missing_path(tmp_path, monkeypatch):
    cli = _load_cli()
    monkeypatch.setattr(cli, "ARKAOS_ROOT", tmp_path / "nowhere")
    assert cli._legacy_obsidian_config() == ""

    root = tmp_path / "root2"
    (root / "knowledge").mkdir(parents=True)
    (root / "knowledge" / "obsidian-config.json").write_text(
        json.dumps({"vault_path": str(tmp_path / "gone")}), encoding="utf-8"
    )
    monkeypatch.setattr(cli, "ARKAOS_ROOT", root)
    assert cli._legacy_obsidian_config() == ""


def test_legacy_profile_vault_reads_and_falls_back(tmp_path, monkeypatch):
    cli = _load_cli()
    home = tmp_path / "home"
    (home / ".arkaos").mkdir(parents=True)
    vault = tmp_path / "profile-vault"
    vault.mkdir()
    (home / ".arkaos" / "profile.json").write_text(
        json.dumps({"vaultPath": str(vault)}), encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    assert cli._legacy_profile_vault() == str(vault)

    (home / ".arkaos" / "profile.json").write_text("{ not json", encoding="utf-8")
    assert cli._legacy_profile_vault() == ""


def test_profile_is_the_last_source_and_is_deprecated(
    tmp_path, monkeypatch, capsys
):
    from core.knowledge import vault as vault_module

    cli = _load_cli()
    home = tmp_path / "home"
    (home / ".arkaos").mkdir(parents=True)
    vault = tmp_path / "profile-vault"
    vault.mkdir()
    (home / ".arkaos" / "profile.json").write_text(
        json.dumps({"vaultPath": str(vault)}), encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(vault_module, "CONFIG_PATH", tmp_path / "absent.json")
    monkeypatch.delenv("ARKAOS_VAULT", raising=False)
    monkeypatch.setattr(cli, "_legacy_obsidian_config", lambda: "")

    assert cli.resolve_index_directory() == str(vault)
    err = capsys.readouterr().err
    assert "profile.json" in err
    assert "DEPRECATED" in err
