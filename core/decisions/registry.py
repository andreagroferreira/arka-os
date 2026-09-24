"""Every registered decision site, by name (``SITES``).

The shadow worker rebuilds calls from here, and ``engine.active`` asks
whether any of them is live. New site modules append their tuple.
"""

from __future__ import annotations

from core.decisions.site import Site
from core.decisions.sites.command import COMMAND_SITES
from core.decisions.sites.dispatch import DISPATCH_SITES
from core.decisions.sites.forge import FORGE_SITES
from core.decisions.sites.governance import GOVERNANCE_SITES
from core.decisions.sites.prompt import PROMPT_SITES
from core.decisions.sites.quality import QUALITY_SITES

SITES: dict[str, Site] = {
    site.name: site
    for site in (
        *PROMPT_SITES, *COMMAND_SITES, *FORGE_SITES, *DISPATCH_SITES,
        *GOVERNANCE_SITES, *QUALITY_SITES,
    )
}
