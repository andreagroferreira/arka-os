#!/usr/bin/env bash
# ============================================================================
# ARKA OS — DISC Team Balance Validator
# Reads agents-registry-v2.json and validates team DISC distribution
# ============================================================================
set -e

ARKA_OS="${ARKA_OS:-$HOME/.claude/skills/arka}"
REPO_DIR="${REPO_DIR:-$(cat "$ARKA_OS/.repo-path" 2>/dev/null || echo "")}"
REGISTRY="${REGISTRY:-$REPO_DIR/knowledge/agents-registry-v2.json}"

if [ ! -f "$REGISTRY" ]; then
  echo "Error: agents-registry-v2.json not found at $REGISTRY"
  exit 1
fi

command -v jq &>/dev/null || { echo "Error: jq is required."; exit 1; }

# Read counts from registry
D_COUNT=$(jq '._meta.disc_distribution.D' "$REGISTRY")
I_COUNT=$(jq '._meta.disc_distribution.I' "$REGISTRY")
S_COUNT=$(jq '._meta.disc_distribution.S' "$REGISTRY")
C_COUNT=$(jq '._meta.disc_distribution.C' "$REGISTRY")
TOTAL=$(( D_COUNT + I_COUNT + S_COUNT + C_COUNT ))

# Calculate percentages
D_PCT=$(( D_COUNT * 100 / TOTAL ))
I_PCT=$(( I_COUNT * 100 / TOTAL ))
S_PCT=$(( S_COUNT * 100 / TOTAL ))
C_PCT=$(( C_COUNT * 100 / TOTAL ))

# Bar generator (10 chars wide)
bar() {
  local pct=$1
  # Scale: 10 bars = 40% (max reasonable for one profile)
  local filled=$(( pct * 10 / 40 ))
  [ "$filled" -gt 10 ] && filled=10
  local empty=$(( 10 - filled ))
  local bar=""
  for ((i=0; i<filled; i++)); do bar+="█"; done
  for ((i=0; i<empty; i++)); do bar+="░"; done
  echo "$bar"
}

# Status check against ideal ranges
check_status() {
  local profile=$1 pct=$2 min=$3 max=$4
  if [ "$pct" -lt "$min" ]; then
    echo "⚠ Low"
  elif [ "$pct" -gt "$max" ]; then
    echo "⚠ High"
  else
    echo "✓ OK"
  fi
}

# Colors
C='\033[0;36m'
G='\033[0;32m'
Y='\033[1;33m'
R='\033[0;31m'
N='\033[0m'

D_STATUS=$(check_status "D" "$D_PCT" 15 25)
I_STATUS=$(check_status "I" "$I_PCT" 20 30)
S_STATUS=$(check_status "S" "$S_PCT" 20 30)
C_STATUS=$(check_status "C" "$C_PCT" 25 35)

echo ""
echo -e "${C}═══ ARKA OS — Team DISC Balance ═══${N}"
printf "  D (Dominant):      %d agents (%d%%)  %s  %s\n" "$D_COUNT" "$D_PCT" "$(bar $D_PCT)" "$D_STATUS"
printf "  I (Influential):   %d agents (%d%%)  %s  %s\n" "$I_COUNT" "$I_PCT" "$(bar $I_PCT)" "$I_STATUS"
printf "  S (Steady):        %d agents (%d%%)  %s  %s\n" "$S_COUNT" "$S_PCT" "$(bar $S_PCT)" "$S_STATUS"
printf "  C (Conscientious): %d agents (%d%%)  %s  %s\n" "$C_COUNT" "$C_PCT" "$(bar $C_PCT)" "$C_STATUS"
echo ""

# Show gaps
GAPS=""
if [ "$S_PCT" -lt 20 ]; then
  GAPS+="  Gap: S profile underrepresented. Consider adding PM or HR agent.\n"
fi
if [ "$D_PCT" -gt 25 ]; then
  GAPS+="  Gap: D profile overrepresented. Watch for authority conflicts.\n"
fi
if [ "$C_PCT" -gt 35 ]; then
  GAPS+="  Gap: C profile overrepresented. Risk of analysis paralysis.\n"
fi

if [ -n "$GAPS" ]; then
  echo -e "$GAPS"
fi

echo -e "${C}═══════════════════════════════════${N}"
echo ""
