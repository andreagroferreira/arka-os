#!/usr/bin/env bats
# ============================================================================
# ARKA OS — Model-routing gateway ensure (scripts/gateway-ensure.sh)
# ============================================================================

load helpers/setup

setup_gateway() {
  export ARKAOS_ROOT="$REPO_DIR"
  # Use the real ArkaOS venv python (has pydantic + yaml) to render config,
  # captured before we override HOME so its absolute path stays valid.
  # shellcheck source=/dev/null
  . "$REPO_DIR/config/hooks/_lib/arka_python.sh"
  export ARKA_PY
  # Scratch home; the router reads $HOME/.arkaos/models.yaml.
  export HOME="$TEST_TEMP_DIR/home"
  export ARKAOS_HOME="$HOME/.arkaos"
  mkdir -p "$ARKAOS_HOME/venv/bin"
  cp "$REPO_DIR/config/models.yaml" "$ARKAOS_HOME/models.yaml" 2>/dev/null || \
    printf 'version: 1\nroles:\n  execution: {provider: ollama, model: "kimi:cloud", effort: high}\n' > "$ARKAOS_HOME/models.yaml"
}

@test "gateway-ensure degrades (non-zero) when litellm is absent" {
  setup_gateway
  export ANTHROPIC_API_KEY="sk-test"
  # no litellm binary in venv/bin
  run bash "$REPO_DIR/scripts/gateway-ensure.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"LiteLLM not installed"* ]]
}

@test "gateway-ensure degrades when ANTHROPIC_API_KEY is unset" {
  setup_gateway
  printf '#!/usr/bin/env bash\nexit 0\n' > "$ARKAOS_HOME/venv/bin/litellm"
  chmod +x "$ARKAOS_HOME/venv/bin/litellm"
  unset ANTHROPIC_API_KEY
  run bash "$REPO_DIR/scripts/gateway-ensure.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"ANTHROPIC_API_KEY unset"* ]]
}

@test "gateway-ensure renders config + launch.env with a stubbed healthy proxy" {
  setup_gateway
  export ANTHROPIC_API_KEY="sk-test"
  # Stub litellm as a no-op; stub curl health to succeed immediately so the
  # ensure treats the proxy as already up and returns fast.
  printf '#!/usr/bin/env bash\nexit 0\n' > "$ARKAOS_HOME/venv/bin/litellm"
  chmod +x "$ARKAOS_HOME/venv/bin/litellm"
  local stubdir="$TEST_TEMP_DIR/stub"
  mkdir -p "$stubdir"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$stubdir/curl"   # health always OK
  chmod +x "$stubdir/curl"
  PATH="$stubdir:$PATH" run bash "$REPO_DIR/scripts/gateway-ensure.sh"
  [ "$status" -eq 0 ]
  [ -f "$ARKAOS_HOME/gateway/config.yaml" ]
  [ -f "$ARKAOS_HOME/gateway/launch.env" ]
  grep -q "ANTHROPIC_BASE_URL=http://127.0.0.1:4000" "$ARKAOS_HOME/gateway/launch.env"
  grep -q "ANTHROPIC_DEFAULT_HAIKU_MODEL=arka-haiku" "$ARKAOS_HOME/gateway/launch.env"
  grep -q "ARKA_GATEWAY_KEY=sk-arka-" "$ARKAOS_HOME/gateway/launch.env"
  # The rendered config must carry the ollama execution route.
  grep -q "arka-haiku" "$ARKAOS_HOME/gateway/config.yaml"
}

@test "gateway-ensure reuse keeps the same key (no 401 on relaunch)" {
  setup_gateway
  export ANTHROPIC_API_KEY="sk-test"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$ARKAOS_HOME/venv/bin/litellm"
  chmod +x "$ARKAOS_HOME/venv/bin/litellm"
  local stubdir="$TEST_TEMP_DIR/stub"
  mkdir -p "$stubdir"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$stubdir/curl"   # always healthy
  chmod +x "$stubdir/curl"
  # First launch mints the key + writes launch.env.
  PATH="$stubdir:$PATH" run bash "$REPO_DIR/scripts/gateway-ensure.sh"
  [ "$status" -eq 0 ]
  key1=$(grep '^ARKA_GATEWAY_KEY=' "$ARKAOS_HOME/gateway/launch.env")
  # Second launch sees a healthy proxy + existing env -> reuse, key unchanged.
  PATH="$stubdir:$PATH" run bash "$REPO_DIR/scripts/gateway-ensure.sh"
  [ "$status" -eq 0 ]
  key2=$(grep '^ARKA_GATEWAY_KEY=' "$ARKAOS_HOME/gateway/launch.env")
  [ "$key1" = "$key2" ]
}

@test "gateway-ensure restart rotates the key (ARKA_GATEWAY_RESTART=1)" {
  setup_gateway
  export ANTHROPIC_API_KEY="sk-test"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$ARKAOS_HOME/venv/bin/litellm"
  chmod +x "$ARKAOS_HOME/venv/bin/litellm"
  local stubdir="$TEST_TEMP_DIR/stub"
  mkdir -p "$stubdir"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$stubdir/curl"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$stubdir/pkill"
  chmod +x "$stubdir/curl" "$stubdir/pkill"
  PATH="$stubdir:$PATH" run bash "$REPO_DIR/scripts/gateway-ensure.sh"
  key1=$(grep '^ARKA_GATEWAY_KEY=' "$ARKAOS_HOME/gateway/launch.env")
  PATH="$stubdir:$PATH" ARKA_GATEWAY_RESTART=1 run bash "$REPO_DIR/scripts/gateway-ensure.sh"
  [ "$status" -eq 0 ]
  key2=$(grep '^ARKA_GATEWAY_KEY=' "$ARKAOS_HOME/gateway/launch.env")
  [ "$key1" != "$key2" ]
}

@test "launch.env never contains the real Anthropic key" {
  setup_gateway
  export ANTHROPIC_API_KEY="sk-ant-REALSECRET"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$ARKAOS_HOME/venv/bin/litellm"
  chmod +x "$ARKAOS_HOME/venv/bin/litellm"
  local stubdir="$TEST_TEMP_DIR/stub"
  mkdir -p "$stubdir"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$stubdir/curl"
  chmod +x "$stubdir/curl"
  PATH="$stubdir:$PATH" run bash "$REPO_DIR/scripts/gateway-ensure.sh"
  [ "$status" -eq 0 ]
  ! grep -q "sk-ant-REALSECRET" "$ARKAOS_HOME/gateway/launch.env"
  ! grep -q "sk-ant-REALSECRET" "$ARKAOS_HOME/gateway/config.yaml"
}
