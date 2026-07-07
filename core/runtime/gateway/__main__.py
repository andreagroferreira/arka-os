"""CLI: render the LiteLLM gateway config from models.yaml.

    arka-py -m core.runtime.gateway [--local]            # print config.yaml
    arka-py -m core.runtime.gateway [--local] --env KEY  # print launch env

``--local`` renders the keyless local-only variant (every route → local
Ollama) for subscription users with no ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import sys

from core.runtime.gateway.litellm_config import build_launch_env, render_config_yaml


def main(argv: list[str]) -> int:
    local_only = "--local" in argv
    argv = [a for a in argv if a != "--local"]
    if len(argv) >= 2 and argv[0] == "--env":
        env = build_launch_env(master_key=argv[1])
        for key, value in env.items():
            print(f"{key}={value}")
        return 0
    sys.stdout.write(render_config_yaml(local_only=local_only))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
