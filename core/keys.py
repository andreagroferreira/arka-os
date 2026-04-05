"""API key management — store, retrieve, and list API keys securely.

Keys stored in ~/.arkaos/keys.json with 600 permissions (owner only).
"""

import json
import os
import stat
from pathlib import Path
from typing import Optional

KEYS_PATH = Path.home() / ".arkaos" / "keys.json"

# Known providers with descriptions
PROVIDERS = {
    "OPENAI_API_KEY": {"name": "OpenAI", "used_for": "Whisper transcription, embeddings, GPT"},
    "ANTHROPIC_API_KEY": {"name": "Anthropic", "used_for": "Claude API (outside Claude Code)"},
    "FAL_API_KEY": {"name": "fal.ai", "used_for": "Image generation, video generation"},
}


def _load() -> dict[str, str]:
    if not KEYS_PATH.exists():
        return {}
    return json.loads(KEYS_PATH.read_text())


def _save(keys: dict[str, str]) -> None:
    KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    KEYS_PATH.write_text(json.dumps(keys, indent=2))
    os.chmod(KEYS_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 600


def get_key(name: str) -> Optional[str]:
    """Get an API key by name. Also checks environment variables."""
    env_val = os.environ.get(name)
    if env_val:
        return env_val
    keys = _load()
    return keys.get(name)


def set_key(name: str, value: str) -> None:
    """Set an API key."""
    keys = _load()
    keys[name] = value
    _save(keys)


def remove_key(name: str) -> bool:
    """Remove an API key. Returns True if it existed."""
    keys = _load()
    if name in keys:
        del keys[name]
        _save(keys)
        return True
    return False


def list_keys() -> list[dict]:
    """List configured keys (masked values)."""
    keys = _load()
    result = []
    for name, info in PROVIDERS.items():
        value = keys.get(name, "")
        env_val = os.environ.get(name, "")
        configured = bool(value or env_val)
        masked = ""
        if value:
            masked = value[:4] + "..." + value[-4:] if len(value) > 10 else "****"
        elif env_val:
            masked = "(from environment)"
        result.append({
            "key": name,
            "provider": info["name"],
            "used_for": info["used_for"],
            "configured": configured,
            "masked_value": masked,
        })
    # Include any custom keys not in PROVIDERS
    for name, value in keys.items():
        if name not in PROVIDERS:
            masked = value[:4] + "..." + value[-4:] if len(value) > 10 else "****"
            result.append({
                "key": name,
                "provider": "Custom",
                "used_for": "",
                "configured": True,
                "masked_value": masked,
            })
    return result
