"""CLI: render the LiteLLM gateway config from models.yaml.

    arka-py -m core.runtime.gateway            # print config.yaml
    arka-py -m core.runtime.gateway --env KEY  # print launch env (KEY = master key)
"""

from __future__ import annotations

import sys

from core.runtime.gateway.litellm_config import build_launch_env, render_config_yaml


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "--env":
        env = build_launch_env(master_key=argv[1])
        for key, value in env.items():
            print(f"{key}={value}")
        return 0
    sys.stdout.write(render_config_yaml())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
