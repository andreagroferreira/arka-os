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
    assert "from core.knowledge.vault import resolve_vault_path" in source


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
