#!/usr/bin/env bash
# tools/init_child.sh — First-run setup for child projects cloned from belico-stack
# ===================================================================================
# Run this ONCE after cloning belico-stack as a child project.
# Configures Engram MCP, GGA pre-commit hook, and verifies the stack is operational.
#
# Usage:
#   bash tools/init_child.sh
#   bash tools/init_child.sh --check   # only verify, no changes
#
# After running: open Claude Code in this directory and say "engram conectó"

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
CHECK_ONLY=false
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=true

# Total steps
TOTAL=11

ok()   { echo -e "  ${GREEN}[OK]${NC}    $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC}  $1"; }
err()  { echo -e "  ${RED}[FAIL]${NC}  $1"; }
info() { echo -e "  ${CYAN}[INFO]${NC}  $1"; }

ERRORS=0

echo ""
echo -e "${CYAN}=================================================${NC}"
echo -e "${CYAN}  BELICO STACK — Child Project Init${NC}"
echo -e "${CYAN}  $(basename "$ROOT")${NC}"
echo -e "${CYAN}=================================================${NC}"
echo ""

# ── STEP 1: Verify CLAUDE.md exists ──────────────────────────────────
echo -e "${CYAN}[1/11] CLAUDE.md${NC}"
if [[ -f "$ROOT/CLAUDE.md" ]]; then
    ok "CLAUDE.md found — orchestrator protocol loaded"
else
    err "CLAUDE.md missing — this is required for the agent to operate"
    info "Fix: git fetch belico && git merge belico/main"
    ERRORS=$((ERRORS + 1))
fi

# ── STEP 2: Verify Engram is installed ───────────────────────────────
echo -e "${CYAN}[2/11] Engram binary${NC}"
if command -v engram &>/dev/null; then
    VER=$(engram version 2>/dev/null || engram --version 2>/dev/null || echo "installed")
    ok "engram $VER"
else
    err "engram not installed"
    info "Fix: brew install gentleman-programming/tap/engram"
    info "     OR: bash tools/setup_dependencies.sh"
    ERRORS=$((ERRORS + 1))
fi

# ── STEP 3: Configure Engram MCP for Claude Code ─────────────────────
echo -e "${CYAN}[3/11] Engram MCP (Claude Code)${NC}"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
if [[ -f "$CLAUDE_SETTINGS" ]] && grep -q "engram" "$CLAUDE_SETTINGS" 2>/dev/null; then
    ok "Engram MCP already configured in ~/.claude/settings.json"
else
    if $CHECK_ONLY; then
        err "Engram MCP NOT configured in ~/.claude/settings.json"
        info "Fix (run without --check): bash tools/init_child.sh"
        ERRORS=$((ERRORS + 1))
    else
        info "Configuring Engram MCP for Claude Code..."
        if command -v engram &>/dev/null; then
            engram setup claude-code 2>/dev/null && ok "Engram MCP configured" || {
                warn "Auto-setup failed. Run manually: engram setup claude-code"
                ERRORS=$((ERRORS + 1))
            }
        else
            err "Cannot configure MCP — engram not installed (see step 2)"
            ERRORS=$((ERRORS + 1))
        fi
    fi
fi

# ── STEP 4: Verify Engram DB is accessible ───────────────────────────
echo -e "${CYAN}[4/11] Engram DB${NC}"
ENGRAM_DB="$HOME/.engram/engram.db"
if [[ -f "$ENGRAM_DB" ]]; then
    SIZE=$(du -h "$ENGRAM_DB" 2>/dev/null | cut -f1 || echo "?")
    ok "~/.engram/engram.db ($SIZE) — shared across all projects"
else
    if $CHECK_ONLY; then
        warn "~/.engram/engram.db not found — will be created on first use"
    else
        info "Initializing Engram DB..."
        mkdir -p "$HOME/.engram"
        if command -v engram &>/dev/null; then
            engram save "init: $(basename "$ROOT") — child project initialized from belico-stack" 2>/dev/null \
                && ok "Engram DB initialized" \
                || warn "DB init failed — will be created automatically on first use"
        fi
    fi
fi

# ── STEP 5: GGA pre-commit hook ───────────────────────────────────────
echo -e "${CYAN}[5/11] GGA pre-commit hook${NC}"
if [[ -f "$ROOT/.git/hooks/pre-commit" ]]; then
    ok "pre-commit hook installed"
else
    if command -v gga &>/dev/null; then
        if $CHECK_ONLY; then
            warn "GGA hook not installed — run: gga install"
        else
            cd "$ROOT" && gga install 2>/dev/null && ok "GGA hook installed" || warn "GGA install failed — run manually: gga install"
        fi
    else
        warn "GGA not installed (optional) — run: brew install gentleman-programming/tap/gga"
    fi
fi

# ── STEP 6: Copy .env from mother (credentials inheritance) ──────────
echo -e "${CYAN}[6/11] Credentials (.env)${NC}"
ENV_FILE="$ROOT/.env"
if [[ -f "$ENV_FILE" ]]; then
    ok ".env already exists — credentials configured"
else
    # Try to find the mother's .env — only look for a sibling named belico-stack
    # (never copy arbitrary .env files from unrelated parent directories)
    MOTHER_ENV=""
    SEARCH_DIR="$(dirname "$ROOT")"
    for _ in 1 2 3; do
        CANDIDATE="$SEARCH_DIR/belico-stack/.env"
        if [[ -f "$CANDIDATE" ]] && grep -q "OPENALEX_API_KEY" "$CANDIDATE" 2>/dev/null; then
            MOTHER_ENV="$CANDIDATE"
            break
        fi
        SEARCH_DIR="$(dirname "$SEARCH_DIR")"
    done

    if [[ -n "$MOTHER_ENV" ]]; then
        if $CHECK_ONLY; then
            warn ".env missing — mother found at $MOTHER_ENV"
            info "Fix (run without --check): bash tools/init_child.sh"
        else
            cp "$MOTHER_ENV" "$ENV_FILE"
            ok ".env copied from mother ($MOTHER_ENV)"
        fi
    else
        if $CHECK_ONLY; then
            warn ".env missing and mother not found nearby"
        else
            warn ".env not found — creating from .env.example"
            if [[ -f "$ROOT/.env.example" ]]; then
                cp "$ROOT/.env.example" "$ENV_FILE"
                warn "Fill in credentials: $ENV_FILE"
                warn "Or copy from your mother: cp /path/to/belico-stack/.env $ENV_FILE"
            else
                warn "No .env.example either — credentials must be configured manually"
            fi
        fi
        ERRORS=$((ERRORS + 1))
    fi
fi

# ── STEP 7: Create required pipeline directories ─────────────────────
echo -e "${CYAN}[7/11] Pipeline directories${NC}"
DIRS=(
    "data/raw"
    "data/processed"
    "articles/drafts"
    "articles/figures"
    "articles/compiled"
    "articles/references"
    "articles/patents"
    "db/excitation/records"
    "db/benchmarks"
    "db/patent_search"
    "db/calibration"
    "db/validation"
)
DIRS_CREATED=0
DIRS_EXISTED=0
for d in "${DIRS[@]}"; do
    if [[ -d "$ROOT/$d" ]]; then
        DIRS_EXISTED=$((DIRS_EXISTED + 1))
    else
        if ! $CHECK_ONLY; then
            mkdir -p "$ROOT/$d"
            # Add .gitkeep so git tracks the empty dir
            touch "$ROOT/$d/.gitkeep"
        fi
        DIRS_CREATED=$((DIRS_CREATED + 1))
    fi
done
if $CHECK_ONLY; then
    [[ $DIRS_CREATED -gt 0 ]] && warn "$DIRS_CREATED director(ies) missing — run without --check to create" \
                               || ok "All ${#DIRS[@]} pipeline directories exist"
else
    [[ $DIRS_CREATED -gt 0 ]] && ok "$DIRS_CREATED director(ies) created, $DIRS_EXISTED already existed" \
                               || ok "All ${#DIRS[@]} pipeline directories already exist"
fi

# ── STEP 8: Interactive project setup (3 questions → pre-fill SSOT) ──
echo -e "${CYAN}[8/11] Quick project setup${NC}"
PARAMS="$ROOT/config/params.yaml"
PRD="$ROOT/PRD.md"

# Detect if params.yaml already has a project name set (not null/empty)
CURRENT_NAME=$(python3 -c "
import yaml, sys
try:
    d = yaml.safe_load(open('$PARAMS'))
    n = (d or {}).get('project', {}).get('name', '')
    print('' if not n or str(n).strip() in ('', 'null', 'None') else n)
except Exception:
    print('')
" 2>/dev/null || echo "")

CURRENT_DOMAIN=$(python3 -c "
import yaml, sys
try:
    d = yaml.safe_load(open('$PARAMS'))
    v = (d or {}).get('project', {}).get('domain', '')
    print('' if not v or str(v).strip() in ('', 'null', 'None') else v)
except Exception:
    print('')
" 2>/dev/null || echo "")

if [[ -n "$CURRENT_NAME" && -n "$CURRENT_DOMAIN" ]]; then
    ok "params.yaml already configured — project: $CURRENT_NAME, domain: $CURRENT_DOMAIN"
elif $CHECK_ONLY; then
    warn "params.yaml not configured — run without --check to set up"
else
    echo ""
    DEFAULT_NAME="$(basename "$ROOT")"
    read -rp "  Project name [$DEFAULT_NAME]: " INPUT_NAME
    PROJECT_NAME="${INPUT_NAME:-$DEFAULT_NAME}"

    read -rp "  Domain (structural/water/air/other) [structural]: " INPUT_DOMAIN
    PROJECT_DOMAIN="${INPUT_DOMAIN:-structural}"
    PROJECT_DOMAIN=$(echo "$PROJECT_DOMAIN" | tr '[:upper:]' '[:lower:]')

    echo "  Seismic code:"
    echo "    1) E.030  (Peru)       — Z: 0.10 / 0.25 / 0.35 / 0.45"
    echo "    2) ASCE 7 (USA)        — enter Ss/S1 from USGS maps"
    echo "    3) EC8    (Europe)     — ag/g from national annex"
    echo "    4) NCh433 (Chile)      — Z: 0.20 / 0.30 / 0.40"
    echo "    5) Skip   (fill later)"
    read -rp "  Choice [1]: " SEISMIC_CHOICE
    SEISMIC_CHOICE="${SEISMIC_CHOICE:-1}"

    case "$SEISMIC_CHOICE" in
        1)
            SEISMIC_CODE="E.030"
            echo "    Zone factor Z — options: 0.10 (Z1) | 0.25 (Z2) | 0.35 (Z3) | 0.45 (Z4)"
            read -rp "    Z value [leave blank to fill later]: " SEISMIC_Z
            ;;
        2)
            SEISMIC_CODE="ASCE 7"
            read -rp "    Z value (Ss in g, e.g. 1.5) [leave blank to fill later]: " SEISMIC_Z
            ;;
        3)
            SEISMIC_CODE="Eurocode 8"
            read -rp "    Z value (ag/g, e.g. 0.30) [leave blank to fill later]: " SEISMIC_Z
            ;;
        4)
            SEISMIC_CODE="NCh433"
            echo "    Zone factor Z — options: 0.20 (Z1) | 0.30 (Z2) | 0.40 (Z3)"
            read -rp "    Z value [leave blank to fill later]: " SEISMIC_Z
            ;;
        *)
            SEISMIC_CODE=""
            SEISMIC_Z=""
            ;;
    esac

    # Pre-fill params.yaml using python — validates that each substitution actually occurred
    PARAMS_UPDATE_OK=$(python3 - <<PYEOF 2>&1
import re, sys

path = "$PARAMS"
try:
    with open(path) as f:
        content = f.read()
except OSError as e:
    print(f"ERROR: cannot read {path}: {e}", file=sys.stderr)
    sys.exit(1)

errors = []

def sub_field(pattern, replacement, text, field_name):
    result, n = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if n == 0:
        errors.append(f"field '{field_name}' not found in params.yaml — add it manually")
    return result

content = sub_field(r'(^\s*name:\s*).*$',   r'\g<1>"$PROJECT_NAME"',   content, "project.name")
content = sub_field(r'(^\s*domain:\s*).*$',  r'\g<1>"$PROJECT_DOMAIN"', content, "project.domain")

z_val = "$SEISMIC_Z".strip()
if z_val:
    content = sub_field(r'(^\s*Z:\s*).*$', r'\g<1>' + z_val, content, "design.Z")

if errors:
    for e in errors:
        print(f"WARN: {e}", file=sys.stderr)

with open(path, 'w') as f:
    f.write(content)
print("OK")
PYEOF
)
    if echo "$PARAMS_UPDATE_OK" | grep -q "^ERROR"; then
        err "params.yaml update failed — edit manually: $PARAMS"
        ERRORS=$((ERRORS + 1))
    else
        ok "params.yaml updated — project: $PROJECT_NAME, domain: $PROJECT_DOMAIN"
        echo "$PARAMS_UPDATE_OK" | grep "^WARN" | while read -r w; do warn "${w#WARN: }"; done
    fi
    [[ -n "$SEISMIC_CODE" ]] && info "Seismic code: $SEISMIC_CODE${SEISMIC_Z:+ | Z=$SEISMIC_Z}"

    # Create PRD.md skeleton if it doesn't exist or is empty
    if [[ ! -f "$PRD" ]] || [[ ! -s "$PRD" ]]; then
        cat > "$PRD" <<PRDEOF
# PRD — $PROJECT_NAME

## Research Topic
<!-- Describe your research topic here (in English for novelty check) -->
TODO: describe your research topic

## Domain
$PROJECT_DOMAIN

## Problem Statement
<!-- What problem does this paper solve? -->
TODO

## Proposed Approach
<!-- How will you solve it? -->
TODO

## Expected Contribution
<!-- What is new / what does nobody else do? -->
TODO

## Data Sources
<!-- Where will you get your data? -->
TODO
PRDEOF
        ok "PRD.md skeleton created → edit it before EXPLORE"
    else
        ok "PRD.md already exists"
    fi
fi

# ── STEP 9: SSOT domain config ──────────────────────────
echo -e "${CYAN}[9/11] SSOT domain config${NC}"
PARAMS="$ROOT/config/params.yaml"
if [[ -f "$PARAMS" ]]; then
    DOMAIN=$(grep "domain:" "$PARAMS" | head -1 | awk '{print $2}' | tr -d '"' || echo "")

    # Check if domain is registered in config/domains/
    DOMAIN_REGISTRY="$ROOT/config/domains"
    if [[ -f "$DOMAIN_REGISTRY/${DOMAIN}.yaml" ]]; then
        STATUS=$(grep "^status:" "$DOMAIN_REGISTRY/${DOMAIN}.yaml" 2>/dev/null | awk '{print $2}' || echo "registered")
        ok "Domain: $DOMAIN [$STATUS] — registered in config/domains/${DOMAIN}.yaml"
        # Domain-aware COMPUTE guidance
        info ""
        info "Next steps for domain '$DOMAIN':"
        if [[ "$DOMAIN" == "structural" ]]; then
            info "  Verify deps: python3 -c \"import openseespy.opensees as ops; print(ops.version())\""
            info "  Fetch data:  python3 tools/fetch_benchmark.py --auto"
            info "  Emulate:     python3 tools/arduino_emu.py sano"
        else
            # Read c0_check from domain YAML (if present)
            C0_CHECK=$(python3 -c \
                "import yaml; r=yaml.safe_load(open('$DOMAIN_REGISTRY/$DOMAIN.yaml')); print(r.get('compute',{}).get('c0_check',''))" \
                2>/dev/null || echo "")
            if [[ -n "$C0_CHECK" ]]; then
                info "  Verify deps: ${C0_CHECK}"
            fi
            info "  Fetch data:  python3 tools/fetch_domain_data.py --domain ${DOMAIN}"
            info "  Configure:   python3 tools/activate_domain.py --domain ${DOMAIN}"
        fi
        info ""
    elif [[ "$DOMAIN" == "structural" || "$DOMAIN" == "water" || "$DOMAIN" == "air" ]]; then
        ok "Domain: $DOMAIN (core domain)"
        if [[ "$DOMAIN" == "structural" ]]; then
            info ""
            info "Next steps for domain 'structural':"
            info "  Verify deps: python3 -c \"import openseespy.opensees as ops; print(ops.version())\""
            info "  Fetch data:  python3 tools/fetch_benchmark.py --auto"
            info "  Emulate:     python3 tools/arduino_emu.py sano"
            info ""
        fi
    elif [[ -z "$DOMAIN" || "$DOMAIN" == "null" ]]; then
        warn "Domain not set in config/params.yaml"
        info "Fix: python3 tools/activate_domain.py --domain <domain>"
        info "Or open Claude Code and describe your research — the orchestrator will generate the domain."
    else
        # Unknown domain — guide user to orchestrator
        warn "Domain '${DOMAIN}' not registered in config/domains/"
        info "The orchestrator can generate this domain automatically."
        info ""
        info "  Option A — Use an existing domain:"
        if command -v python3 &>/dev/null && [[ -f "$ROOT/tools/activate_domain.py" ]]; then
            python3 "$ROOT/tools/activate_domain.py" --list 2>/dev/null | grep -E "^\s+(structural|environmental|biomedical|economics)" || true
        fi
        info ""
        info "  Option B — Generate a new domain from your research description:"
        info "  → Open Claude Code in this directory"
        info "  → Say: \"engram conectó\""
        info "  → When asked '¿Qué vamos a desarrollar?', describe your research"
        info "  → The orchestrator will generate config/domains/${DOMAIN}.yaml automatically"
        info ""
        info "  Option C — Activate manually:"
        info "  → python3 tools/activate_domain.py --domain ${DOMAIN}"
    fi
else
    warn "config/params.yaml not found — run: python3 tools/init_project.py"
fi

# ── STEP 10: Python version + pip install -r requirements.txt ─────────
echo -e "${CYAN}[10/11] Python dependencies${NC}"
if ! command -v python3 &>/dev/null; then
    err "python3 not found — install Python 3.9+"
    ERRORS=$((ERRORS + 1))
else
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 9) ]]; then
        err "Python $PY_VERSION found — requires 3.9+"
        ERRORS=$((ERRORS + 1))
    else
        ok "Python $PY_VERSION"
        REQ="$ROOT/requirements.txt"
        if [[ -f "$REQ" ]]; then
            if $CHECK_ONLY; then
                MISSING=$(python3 -c "
import importlib, re, sys
missing = []
for line in open('$REQ'):
    pkg = re.split('[>=<!]', line.strip())[0].strip()
    if pkg and not pkg.startswith('#'):
        mod = pkg.replace('-','_').lower()
        try: importlib.import_module(mod)
        except ImportError: missing.append(pkg)
print(' '.join(missing))
" 2>/dev/null || echo "")
                if [[ -z "$MISSING" ]]; then
                    ok "All Python dependencies installed"
                else
                    warn "Missing packages: $MISSING"
                    info "Fix: pip install -r requirements.txt"
                fi
            else
                info "Installing Python dependencies..."
                pip install -r "$REQ" --quiet && ok "pip install done" || {
                    warn "pip install failed — run manually: pip install -r requirements.txt"
                    ERRORS=$((ERRORS + 1))
                }
            fi
        else
            warn "requirements.txt not found"
        fi
    fi
fi

# ── STEP 11: Generate derived params (params.py + params.h) ──────────
echo -e "${CYAN}[11/11] Derived params (generate_params.py)${NC}"
GEN="$ROOT/tools/generate_params.py"
PARAMS_PY="$ROOT/src/physics/models/params.py"
PARAMS_H="$ROOT/src/firmware/params.h"
if [[ -f "$GEN" ]]; then
    if $CHECK_ONLY; then
        if [[ -f "$PARAMS_PY" && -f "$PARAMS_H" ]]; then
            ok "params.py + params.h exist (may be stale if params.yaml changed)"
        else
            warn "params.py or params.h missing — run: python3 tools/generate_params.py"
        fi
    else
        python3 "$GEN" 2>/dev/null && ok "params.py + params.h generated from params.yaml" || {
            warn "generate_params.py failed — run manually after filling config/params.yaml"
        }
    fi
else
    warn "tools/generate_params.py not found"
fi

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}=================================================${NC}"
if [[ $ERRORS -eq 0 ]]; then
    echo -e "${GREEN}  READY — Open Claude Code and say:${NC}"
    echo -e "${GREEN}  → \"engram conectó\"${NC}"
else
    echo -e "${RED}  $ERRORS issue(s) found — fix them and re-run:${NC}"
    echo -e "${RED}  bash tools/init_child.sh${NC}"
fi
echo -e "${CYAN}=================================================${NC}"
echo ""

exit $ERRORS
