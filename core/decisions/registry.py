"""Every registered decision site, by name (``SITES``).

The shadow worker rebuilds calls from here, and ``engine.active`` asks
whether any of them is live. New site modules append their tuple.
"""

from __future__ import annotations

from core.decisions.site import Site
from core.decisions.sites.prompt import PROMPT_SITES

SITES: dict[str, Site] = {site.name: site for site in PROMPT_SITES}
