#!/usr/bin/env bash
# tools/sync_env.sh — Sync mother .env to all child projects
# ===========================================================
# Copies new/updated variables from the mother .env to each child
# without overwriting values the child has already customized.
#
# Usage:
#   bash tools/sync_env.sh                    # auto-discover children
#   bash tools/sync_env.sh --dry-run          # show what would change
#   bash tools/sync_env.sh --child /path/dir  # sync to specific child

set -euo pipefail

MOTHER_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MOTHER_ENV="$MOTHER_ROOT/.env"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}[OK]${NC}    $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC}  $1"; }
err()  { echo -e "  ${RED}[FAIL]${NC}  $1"; }
info() { echo -e "  ${CYAN}[INFO]${NC}  $1"; }

DRY_RUN=false
SPECIFIC_CHILD=""

while [[ $# -gt 0 ]]; do
    case "${1:-}" in
        --dry-run) DRY_RUN=true ;;
        --child)   SPECIFIC_CHILD="${2:-}"; shift ;;
        *) ;;
    esac
    shift
done

echo ""
echo -e "${CYAN}=================================================${NC}"
echo -e "${CYAN}  BELICO STACK — Sync .env → Children${NC}"
echo -e "${CYAN}  Mother: $(basename "$MOTHER_ROOT")${NC}"
$DRY_RUN && echo -e "${YELLOW}  DRY RUN — no changes will be written${NC}"
echo -e "${CYAN}=================================================${NC}"
echo ""

# ── Verify mother .env exists ─────────────────────────────────────────
if [[ ! -f "$MOTHER_ENV" ]]; then
    err "Mother .env not found at $MOTHER_ENV"
    exit 1
fi

# ── Discover children ─────────────────────────────────────────────────
CHILDREN=()

if [[ -n "$SPECIFIC_CHILD" ]]; then
    if [[ -d "$SPECIFIC_CHILD" ]]; then
        CHILDREN+=("$SPECIFIC_CHILD")
    else
        err "Child directory not found: $SPECIFIC_CHILD"
        exit 1
    fi
else
    # Look for sibling directories that have CLAUDE.md (= belico-stack children)
    PARENT_DIR="$(dirname "$MOTHER_ROOT")"
    while IFS= read -r -d '' dir; do
        candidate="$(dirname "$dir")"
        # Skip the mother itself
        [[ "$candidate" == "$MOTHER_ROOT" ]] && continue
        # Must have a .git dir (is a repo) and a .env or .env.example
        [[ -d "$candidate/.git" ]] || continue
        CHILDREN+=("$candidate")
    done < <(find "$PARENT_DIR" -maxdepth 3 -name "CLAUDE.md" -not -path "$MOTHER_ROOT/*" -print0 2>/dev/null)
fi

if [[ ${#CHILDREN[@]} -eq 0 ]]; then
    warn "No child projects found in $(dirname "$MOTHER_ROOT")"
    info "Use --child /path/to/child to specify one manually"
    exit 0
fi

info "Found ${#CHILDREN[@]} child project(s)"
echo ""

# ── Sync function ─────────────────────────────────────────────────────
sync_env() {
    local child_dir="$1"
    local child_env="$child_dir/.env"
    local child_name
    child_name="$(basename "$child_dir")"

    echo -e "${CYAN}── $child_name${NC}"

    # Parse mother vars into associative array
    declare -A MOTHER_VARS
    while IFS= read -r line; do
        [[ -z "$line" || "$line" == \#* ]] && continue
        key="${line%%=*}"
        val="${line#*=}"
        [[ -n "$key" ]] && MOTHER_VARS["$key"]="$val"
    done < "$MOTHER_ENV"

    # If child has no .env, copy the whole mother .env
    if [[ ! -f "$child_env" ]]; then
        if $DRY_RUN; then
            warn "No .env found — would copy full mother .env"
        else
            cp "$MOTHER_ENV" "$child_env"
            ok "No .env found — copied full mother .env"
        fi
        return
    fi

    # Parse child vars
    declare -A CHILD_VARS
    while IFS= read -r line; do
        [[ -z "$line" || "$line" == \#* ]] && continue
        key="${line%%=*}"
        val="${line#*=}"
        [[ -n "$key" ]] && CHILD_VARS["$key"]="$val"
    done < "$child_env"

    # Find vars in mother that are missing or empty in child
    ADDED=0
    SKIPPED=0
    for key in "${!MOTHER_VARS[@]}"; do
        mother_val="${MOTHER_VARS[$key]}"
        # Skip if child already has a non-empty, non-placeholder value
        if [[ -n "${CHILD_VARS[$key]:-}" ]]; then
            child_val="${CHILD_VARS[$key]}"
            if [[ "$child_val" != *"your_"*"_here"* && "$child_val" != '""' && "$child_val" != "''" ]]; then
                SKIPPED=$((SKIPPED + 1))
                continue
            fi
        fi
        # Add or update
        if $DRY_RUN; then
            info "Would add: $key"
        else
            # Append if missing, update if placeholder
            if grep -q "^${key}=" "$child_env" 2>/dev/null; then
                sed -i "s|^${key}=.*|${key}=${mother_val}|" "$child_env"
            else
                echo "${key}=${mother_val}" >> "$child_env"
            fi
        fi
        ADDED=$((ADDED + 1))
    done

    if [[ $ADDED -gt 0 ]]; then
        $DRY_RUN && info "$ADDED var(s) would be synced, $SKIPPED already set" \
                 || ok "$ADDED var(s) synced, $SKIPPED already set (preserved)"
    else
        ok "Already up to date ($SKIPPED vars preserved)"
    fi
}

# ── Run sync for each child ───────────────────────────────────────────
for child in "${CHILDREN[@]}"; do
    sync_env "$child"
    echo ""
done

echo -e "${CYAN}=================================================${NC}"
echo -e "${GREEN}  Done.${NC}"
$DRY_RUN && echo -e "${YELLOW}  Re-run without --dry-run to apply changes.${NC}"
echo -e "${CYAN}=================================================${NC}"
echo ""
