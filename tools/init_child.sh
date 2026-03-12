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
echo -e "${CYAN}[1/6] CLAUDE.md${NC}"
if [[ -f "$ROOT/CLAUDE.md" ]]; then
    ok "CLAUDE.md found — orchestrator protocol loaded"
else
    err "CLAUDE.md missing — this is required for the agent to operate"
    info "Fix: git fetch belico && git merge belico/main"
    ERRORS=$((ERRORS + 1))
fi

# ── STEP 2: Verify Engram is installed ───────────────────────────────
echo -e "${CYAN}[2/6] Engram binary${NC}"
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
echo -e "${CYAN}[3/6] Engram MCP (Claude Code)${NC}"
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
echo -e "${CYAN}[4/6] Engram DB${NC}"
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
echo -e "${CYAN}[5/6] GGA pre-commit hook${NC}"
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

# ── STEP 6: config/params.yaml domain check ──────────────────────────
echo -e "${CYAN}[6/6] SSOT domain config${NC}"
PARAMS="$ROOT/config/params.yaml"
if [[ -f "$PARAMS" ]]; then
    DOMAIN=$(grep "domain:" "$PARAMS" | head -1 | awk '{print $2}' | tr -d '"' || echo "")

    # Check if domain is registered in config/domains/
    DOMAIN_REGISTRY="$ROOT/config/domains"
    if [[ -f "$DOMAIN_REGISTRY/${DOMAIN}.yaml" ]]; then
        STATUS=$(grep "^status:" "$DOMAIN_REGISTRY/${DOMAIN}.yaml" 2>/dev/null | awk '{print $2}' || echo "registered")
        ok "Domain: $DOMAIN [$STATUS] — registered in config/domains/${DOMAIN}.yaml"
    elif [[ "$DOMAIN" == "structural" || "$DOMAIN" == "water" || "$DOMAIN" == "air" ]]; then
        ok "Domain: $DOMAIN (core domain)"
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
