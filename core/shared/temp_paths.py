"""Cross-platform base directory for ArkaOS inter-process coordination files.

Several core modules and the bash hooks coordinate through small marker
and cache files: workflow-required markers (``stop.sh`` ->
``flow_enforcer``), the turn-scoped KB query cache
(``user-prompt-submit.sh`` -> ``kb_cache``), hook metrics
(``user-prompt-submit.sh`` -> ``dashboard-api``). The hooks write them
under ``/tmp/arkaos-*``; the Python side MUST resolve to the *same*
directory or the coordination silently breaks.

Why this lives in ``core.shared``: every module that coordinates through
these files (flow_enforcer, marker_cache, research_gate, kb_cache,
forge.orchestrator, the consolidated hooks, native_usage, the synapse
bridge, the dashboard API, …) used to hardcode the literal string
``/tmp``. ``/tmp`` does not exist on Windows, so every one of those
features failed there. A single helper keeps the resolution in one place.

POSIX keeps the literal ``/tmp`` the bash hooks use (avoiding a
``$TMPDIR`` divergence on macOS where ``tempfile.gettempdir()`` returns
``/var/folders/...`` but the hooks still write ``/tmp``). On Windows
there is no ``/tmp``: Git-for-Windows maps a hook's ``/tmp`` to
``%TEMP%``, which is exactly what ``tempfile.gettempdir()`` returns, so
both sides still meet.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def arkaos_temp_dir(*parts: str) -> Path:
    """Return ``<coordination base>/<parts...>`` (the path is not created).

    POSIX -> ``/tmp/<parts>`` (matches the bash hooks verbatim).
    Windows -> ``<%TEMP%>/<parts>`` (matches Git-for-Windows ``/tmp``).
    """
    base = Path(tempfile.gettempdir()) if os.name == "nt" else Path("/tmp")
    return base.joinpath(*parts)


def wf_required_dir() -> Path:
    """Directory holding the workflow-required markers.

    Honors ``ARKA_WF_REQUIRED_DIR`` — the same override the bash
    classifier (``_lib/workflow-classifier.sh``) reads. It lives here and
    not at each call site because the override used to be honored by the
    writer only: ``flow_enforcer`` and ``stop`` resolved the default
    directly, so setting it split writer from reader and the gate found
    no marker and allowed everything, silently. One resolver, no drift.
    """
    override = os.environ.get("ARKA_WF_REQUIRED_DIR")
    return Path(override) if override else arkaos_temp_dir("arkaos-wf-required")
