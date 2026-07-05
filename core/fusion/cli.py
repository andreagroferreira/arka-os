"""Fusion CLI — run the panel → judge → synthesis pipeline.

Usage::

    python -m core.fusion.cli "your question"
    python -m core.fusion.cli --save "your question"   # persist the panel
    python -m core.fusion.cli --show                   # show the panel only

When ``models.yaml`` has no ``fusion.panel``, a default is built from the
machine's models (runtime + local Ollama) so fusion works out of the box.
``--save`` writes that panel into ``~/.arkaos/models.yaml`` so every
fusion consumer (and the dashboard) sees it.
"""

from __future__ import annotations

import sys

from core.fusion.engine import FusionUnavailable, fuse
from core.fusion.panel_builder import default_panel, describe_panel
from core.runtime.model_router import load_config


def _save_panel(panel, judge) -> str:
    import yaml
    from core.runtime.model_router import USER_CONFIG_PATH, ensure_user_config
    path = ensure_user_config()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("fusion", {})
    data["fusion"]["judge"] = judge.model_dump()
    data["fusion"]["panel"] = [c.model_dump() for c in panel]
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return str(USER_CONFIG_PATH)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    save = "--save" in args
    show = "--show" in args
    args = [a for a in args if a not in ("--save", "--show")]

    config, _ = load_config()
    panel, judge = default_panel(config)

    if show:
        print(f"\n  Fusion panel — {describe_panel(panel, judge)}")
        if not config.fusion.panel:
            print("  (default built from the machine; run --save to persist)")
        print()
        return 0

    if len(panel) < 2:
        print("  ✗ No panel available — configure fusion.panel in "
              "models.yaml (try /arka-fusion) or start Ollama with 2+ "
              "models for a local panel.", file=sys.stderr)
        return 1

    if save:
        where = _save_panel(panel, judge)
        print(f"  ✓ Fusion panel saved to {where}")
        config, _ = load_config()  # reload so fuse() uses the saved panel

    prompt = " ".join(args).strip()
    if not prompt:
        print("usage: python -m core.fusion.cli [--save] \"question\"",
              file=sys.stderr)
        return 1

    # Build an effective config carrying the (possibly default) panel.
    config.fusion.panel = panel
    config.fusion.judge = judge
    try:
        result = fuse(prompt, config=config)
    except FusionUnavailable as exc:
        print(f"  ✗ {exc}", file=sys.stderr)
        return 1
    seats = ", ".join(
        f"{a.provider}/{a.model}" + (" (failed)" if a.failed else "")
        for a in result.answers
    )
    print(f"\n  Fusion — judge {result.judge_provider}/{result.judge_model} "
          f"| panel: {seats}\n")
    print(result.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
