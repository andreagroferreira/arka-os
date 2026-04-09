"""ResearchProfiler — infers adaptive research topics from project ecosystems.

Reads ecosystems.json, extracts stacks and domains, and maps them to curated
research topics for automated content monitoring and trend awareness.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


# --- Topic mapping dictionaries ---

STACK_TOPICS: dict[str, list[str]] = {
    "laravel": [
        "Laravel releases and security patches",
        "Laravel ecosystem packages",
        "PHP security advisories",
    ],
    "nuxt": [
        "Nuxt 3/4 releases and migration guides",
        "Vue 3 ecosystem updates",
    ],
    "vue": [
        "Vue 3 composition API patterns",
        "Vue ecosystem tooling updates",
    ],
    "react": [
        "React releases and concurrent features",
        "Next.js app router updates",
        "React ecosystem library news",
    ],
    "python": [
        "Python release notes and deprecations",
        "FastAPI and async Python patterns",
        "Python security CVEs",
    ],
    "shopify-liquid": [
        "Shopify platform updates and API changes",
        "Shopify theme development best practices",
        "Shopify app ecosystem news",
    ],
    "ai": [
        "Large language model releases and benchmarks",
        "AI agent framework updates",
        "Anthropic and OpenAI product announcements",
    ],
    "energy": [
        "Energy sector digital transformation trends",
        "API governance in regulated industries",
        "Enterprise integration patterns for utilities",
    ],
}

DOMAIN_TOPICS: dict[str, list[str]] = {
    "ecommerce": [
        "E-commerce conversion rate trends",
        "Marketplace integration updates",
        "Payment gateway changes and PSD2 compliance",
    ],
    "media": [
        "Streaming technology updates",
        "Content delivery network trends",
        "Viral content mechanics and audience growth",
    ],
    "enterprise": [
        "Enterprise architecture and API governance",
        "System integration patterns",
        "Cloud migration strategies",
    ],
    "saas": [
        "SaaS pricing model trends",
        "Product-led growth tactics",
        "Micro-SaaS opportunity scouting",
    ],
    "news": [
        "CMS architecture and headless content",
        "SEO for news portals and Google News",
        "Security hardening for content platforms",
    ],
    "events": [
        "Event platform technology stack trends",
        "Ticketing and registration UX patterns",
        "Landing page conversion for events",
    ],
    "consulting": [
        "Web application architecture trends",
        "Client delivery workflow optimisation",
        "TypeScript and Nuxt ecosystem updates",
    ],
}

# Keywords used to infer domain from ecosystem description and type
_DOMAIN_SIGNALS: dict[str, list[str]] = {
    "ecommerce": ["e-commerce", "ecommerce", "marketplace", "shopify", " erp ", "supplier"],
    "media": ["media", "content", "viral", "streaming", "news portal", "quiz", "audience"],
    "enterprise": ["enterprise integration", "api governance", "energy utility", "soap ", "kafka"],
    "saas": ["micro-saas", "saas", "ai tools", "growth engine", "revenue target"],
    "news": ["news", "portal", "cms", "journalism"],
    "events": ["event", "conference", "landing", "registration"],
    "consulting": ["consulting", "services"],
}


@dataclass
class ResearchTopic:
    """A single research topic derived from a stack or domain."""

    name: str
    source: str  # "stack" | "domain" | "tool" | "business"
    search_queries: list[str] = field(default_factory=list)


@dataclass
class ResearchProfile:
    """Aggregated research profile for all active project ecosystems."""

    stacks: list[str]
    domains: list[str]
    tools: list[str]
    business_interests: list[str]
    competitors: list[str]
    topics: list[ResearchTopic]

    def to_yaml(self) -> str:
        """Serialise the profile to a YAML string."""
        data = {
            "stacks": self.stacks,
            "domains": self.domains,
            "tools": self.tools,
            "business_interests": self.business_interests,
            "competitors": self.competitors,
            "topics": [
                {
                    "name": t.name,
                    "source": t.source,
                    "search_queries": t.search_queries,
                }
                for t in self.topics
            ],
        }
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)


def _normalise_stack_name(raw: str) -> str:
    """Return a canonical stack key from a raw tech string."""
    lower = raw.lower().strip()
    if lower.startswith("laravel"):
        return "laravel"
    if lower.startswith("nuxt"):
        return "nuxt"
    if lower.startswith("vue"):
        return "vue"
    if lower.startswith("react") or lower.startswith("next"):
        return "react"
    if lower.startswith("python") or lower.startswith("fastapi") or lower.startswith("pydantic"):
        return "python"
    if "shopify" in lower:
        return "shopify-liquid"
    if "openai" in lower or "anthropic" in lower or "claude" in lower or "gpt" in lower:
        return "ai"
    return ""


def _extract_stacks_from_ecosystem(eco: dict) -> list[str]:
    """Extract canonical stack names from an ecosystem's tech_stack dict."""
    tech_stack = eco.get("tech_stack", {})
    found: set[str] = set()
    for _category, entries in tech_stack.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            key = _normalise_stack_name(str(entry))
            if key:
                found.add(key)
    return list(found)


def _infer_domain(eco: dict) -> str:
    """Infer a domain label from ecosystem description, capabilities, and type."""
    text = " ".join([
        eco.get("description", ""),
        eco.get("name", ""),
        str(eco.get("capabilities", "")),
    ]).lower()

    for domain, signals in _DOMAIN_SIGNALS.items():
        if any(sig in text for sig in signals):
            return domain
    return "consulting"


class ResearchProfiler:
    """Builds a ResearchProfile by inspecting the ArkaOS ecosystems registry."""

    def __init__(self, ecosystems_path: str) -> None:
        """Load the ecosystems registry from disk."""
        self._path = Path(ecosystems_path)

    def build_profile(self) -> ResearchProfile:
        """Parse ecosystems.json and produce a unified ResearchProfile."""
        raw = self._load()
        ecosystems = raw.get("ecosystems", {})

        stacks: set[str] = set()
        domains: set[str] = set()

        for eco in ecosystems.values():
            stacks.update(_extract_stacks_from_ecosystem(eco))
            domains.add(_infer_domain(eco))

        topics = self._generate_topics(stacks, domains)

        return ResearchProfile(
            stacks=sorted(stacks),
            domains=sorted(domains),
            tools=[],
            business_interests=[],
            competitors=[],
            topics=topics,
        )

    def _load(self) -> dict:
        """Read and parse the ecosystems JSON file."""
        if not self._path.exists():
            return {"ecosystems": {}}
        with self._path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def _generate_topics(
        self,
        stacks: set[str],
        domains: set[str],
    ) -> list[ResearchTopic]:
        """Generate ResearchTopic instances from stack and domain mappings."""
        topics: list[ResearchTopic] = []

        for stack in sorted(stacks):
            if stack in STACK_TOPICS:
                topics.append(ResearchTopic(
                    name=f"{stack} ecosystem",
                    source="stack",
                    search_queries=STACK_TOPICS[stack],
                ))

        for domain in sorted(domains):
            if domain in DOMAIN_TOPICS:
                topics.append(ResearchTopic(
                    name=f"{domain} trends",
                    source="domain",
                    search_queries=DOMAIN_TOPICS[domain],
                ))

        return topics
