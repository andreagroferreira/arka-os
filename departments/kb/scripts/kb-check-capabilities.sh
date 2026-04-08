#!/bin/bash
# ============================================================================
# ARKA OS — KB Capability Detection
# Probes local binaries and API keys, writes ~/.arka-os/capabilities.json
# ============================================================================
set -euo pipefail

ARKA_DIR="$HOME/.arka-os"
CAPS_FILE="$ARKA_DIR/capabilities.json"
ENV_FILE="$ARKA_DIR/.env"

mkdir -p "$ARKA_DIR"

# Load env if present
[ -f "$ENV_FILE" ] && source "$ENV_FILE"

# ─── Binary checks ──────────────────────────────────────────────────────────

check_binary() {
    local name="$1"
    local path=""
    local version=""

    if path=$(command -v "$name" 2>/dev/null); then
        case "$name" in
            whisper)  version=$(pip3 show openai-whisper 2>/dev/null | grep "^Version:" | cut -d' ' -f2 || echo "installed") ;;
            yt-dlp)   version=$($path --version 2>&1 | head -1 || echo "unknown") ;;
            ffmpeg)   version=$(ffmpeg -version 2>&1 | head -1 | sed 's/ffmpeg version //' | cut -d' ' -f1 || echo "unknown") ;;
            jq)       version=$($path --version 2>&1 || echo "unknown") ;;
            python3)  version=$($path --version 2>&1 | cut -d' ' -f2 || echo "unknown") ;;
        esac
        version=$(printf '%s' "$version" | tr -d '\n\r' | tr -cd '[:print:]')
        printf '{"available":true,"path":"%s","version":"%s"}' "$path" "$version"
    else
        printf '{"available":false,"path":null,"version":null}'
    fi
}

# ─── API key checks ─────────────────────────────────────────────────────────

check_key() {
    local var_name="$1"
    local value="${!var_name:-}"
    if [ -n "$value" ] && [ ${#value} -ge 8 ]; then
        printf '{"configured":true,"key_prefix":"%s***"}' "${value:0:6}"
    else
        printf '{"configured":false,"key_prefix":null}'
    fi
}

# ─── Determine transcription method ─────────────────────────────────────────

whisper_available=false
openai_available=false

if command -v whisper &>/dev/null; then
    whisper_available=true
fi
if [ -n "${OPENAI_API_KEY:-}" ] && [ ${#OPENAI_API_KEY} -ge 8 ]; then
    openai_available=true
fi

if $whisper_available; then
    transcription_method="local_whisper"
    transcription_note="Using local Whisper (free, private)"
elif $openai_available; then
    transcription_method="openai_api"
    transcription_note="Using OpenAI Whisper API (requires credits)"
else
    transcription_method="none"
    transcription_note="No transcription available. Install whisper (pip install openai-whisper) or set OPENAI_API_KEY."
fi

# ─── Build JSON ──────────────────────────────────────────────────────────────

cat > "$CAPS_FILE" << JSONEOF
{
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "binaries": {
    "whisper": $(check_binary whisper),
    "yt-dlp": $(check_binary yt-dlp),
    "ffmpeg": $(check_binary ffmpeg),
    "jq": $(check_binary jq),
    "python3": $(check_binary python3)
  },
  "api_keys": {
    "OPENAI_API_KEY": $(check_key OPENAI_API_KEY),
    "GEMINI_API_KEY": $(check_key GEMINI_API_KEY),
    "OPENROUTER_API_KEY": $(check_key OPENROUTER_API_KEY),
    "REPLICATE_API_TOKEN": $(check_key REPLICATE_API_TOKEN),
    "FAL_KEY": $(check_key FAL_KEY)
  },
  "transcription": {
    "method": "$transcription_method",
    "note": "$transcription_note"
  }
}
JSONEOF

# ─── Pretty output if running interactively ──────────────────────────────────

if [ -t 1 ]; then
    CYAN='\033[0;36m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    NC='\033[0m'

    echo ""
    echo -e "${CYAN}═══ ARKA OS — Capabilities ═══${NC}"
    echo ""
    echo -e "${CYAN}Binaries:${NC}"
    for bin in whisper yt-dlp ffmpeg jq python3; do
        if command -v "$bin" &>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $bin ($(command -v "$bin"))"
        else
            echo -e "  ${RED}✗${NC} $bin — not found"
        fi
    done

    echo ""
    echo -e "${CYAN}API Keys:${NC}"
    for key in OPENAI_API_KEY GEMINI_API_KEY OPENROUTER_API_KEY REPLICATE_API_TOKEN FAL_KEY; do
        value="${!key:-}"
        if [ -n "$value" ] && [ ${#value} -ge 8 ]; then
            echo -e "  ${GREEN}✓${NC} $key (${value:0:6}***)"
        else
            echo -e "  ${YELLOW}⚠${NC} $key — not set"
        fi
    done

    echo ""
    echo -e "${CYAN}Transcription:${NC}"
    case "$transcription_method" in
        local_whisper) echo -e "  ${GREEN}✓${NC} $transcription_note" ;;
        openai_api)    echo -e "  ${GREEN}✓${NC} $transcription_note" ;;
        none)          echo -e "  ${RED}✗${NC} $transcription_note" ;;
    esac

    echo ""
    echo -e "Written to: ${CYAN}$CAPS_FILE${NC}"
    echo -e "${CYAN}═══════════════════════════════${NC}"
fi
