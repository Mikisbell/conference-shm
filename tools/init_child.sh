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
TOTAL=10

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
echo -e "${CYAN}[1/10] CLAUDE.md${NC}"
if [[ -f "$ROOT/CLAUDE.md" ]]; then
    ok "CLAUDE.md found — orchestrator protocol loaded"
else
    err "CLAUDE.md missing — this is required for the agent to operate"
    info "Fix: git fetch belico && git merge belico/main"
    ERRORS=$((ERRORS + 1))
fi

# ── STEP 2: Verify Engram is installed ───────────────────────────────
echo -e "${CYAN}[2/10] Engram binary${NC}"
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
echo -e "${CYAN}[3/10] Engram MCP (Claude Code)${NC}"
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
echo -e "${CYAN}[4/10] Engram DB${NC}"
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
echo -e "${CYAN}[5/10] GGA pre-commit hook${NC}"
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
echo -e "${CYAN}[6/10] Credentials (.env)${NC}"
ENV_FILE="$ROOT/.env"
if [[ -f "$ENV_FILE" ]]; then
    ok ".env already exists — credentials configured"
else
    # Try to find the mother's .env by walking up the directory tree
    MOTHER_ENV=""
    SEARCH_DIR="$(dirname "$ROOT")"
    for _ in 1 2 3; do
        if [[ -f "$SEARCH_DIR/belico-stack/.env" ]]; then
            MOTHER_ENV="$SEARCH_DIR/belico-stack/.env"
            break
        fi
        if [[ -f "$SEARCH_DIR/.env" ]] && grep -q "OPENALEX_API_KEY\|SEMANTIC_SCHOLAR" "$SEARCH_DIR/.env" 2>/dev/null; then
            MOTHER_ENV="$SEARCH_DIR/.env"
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
echo -e "${CYAN}[7/10] Pipeline directories${NC}"
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

# ── STEP 8: config/params.yaml domain check ──────────────────────────
echo -e "${CYAN}[8/10] SSOT domain config${NC}"
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

# ── STEP 9: Python version + pip install -r requirements.txt ─────────
echo -e "${CYAN}[9/10] Python dependencies${NC}"
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

# ── STEP 10: Generate derived params (params.py + params.h) ──────────
echo -e "${CYAN}[10/10] Derived params (generate_params.py)${NC}"
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
