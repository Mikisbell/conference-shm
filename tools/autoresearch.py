#!/usr/bin/env python3
"""
AutoResearch: Self-improving paper factory.

Inspired by Andrej Karpathy's autoresearch (github.com/karpathy/autoresearch).
Runs an autonomous loop that proposes, evaluates, and keeps/discards changes
to the belico-stack template.

Usage:
    python tools/autoresearch.py                    # 10 experiments, all rooms
    python tools/autoresearch.py --experiments 20   # 20 experiments
    python tools/autoresearch.py --room validator    # only validator room
    python tools/autoresearch.py --dry-run           # propose but don't apply
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml")
    sys.exit(1)

# LLM provider: GitHub Models (free with GITHUB_TOKEN) or Anthropic (fallback)
LLM_PROVIDER = None  # set in main()
LLM_CLIENT = None

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
ROOMS_PATH = ROOT / ".agent" / "autoresearch" / "rooms.yaml"
PROGRAM_PATH = ROOT / ".agent" / "autoresearch" / "program.md"
RESULTS_PATH = ROOT / ".agent" / "autoresearch" / "results.tsv"


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------
def load_rooms_config():
    """Load rooms.yaml and return (rooms_dict, settings_dict)."""
    with open(ROOMS_PATH) as f:
        cfg = yaml.safe_load(f)
    return cfg.get("rooms", {}), cfg.get("settings", {})


def load_results(room_name=None, last_n=10):
    """Load last N results from results.tsv, optionally filtered by room."""
    if not RESULTS_PATH.exists():
        return []
    results = []
    with open(RESULTS_PATH) as f:
        header = f.readline().strip().split("\t")
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < len(header):
                continue
            row = dict(zip(header, parts))
            if room_name and row.get("room") != room_name:
                continue
            results.append(row)
    return results[-last_n:]


def init_results_file():
    """Create results.tsv with header if it doesn't exist."""
    if not RESULTS_PATH.exists():
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RESULTS_PATH, "w") as f:
            f.write("timestamp\troom\texperiment\tfile_changed\t"
                    "score\tbaseline\tdelta\tstatus\tdescription\n")


def append_result(row: dict):
    """Append one result row to results.tsv."""
    cols = ["timestamp", "room", "experiment", "file_changed",
            "score", "baseline", "delta", "status", "description"]
    with open(RESULTS_PATH, "a") as f:
        f.write("\t".join(str(row.get(c, "")) for c in cols) + "\n")


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------
def git_run(*args, check=True):
    """Run a git command in ROOT directory."""
    result = subprocess.run(
        ["git"] + list(args),
        cwd=ROOT, capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result


def git_current_branch():
    return git_run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def git_create_branch(name):
    git_run("checkout", "-b", name)


def git_commit(file_path, message):
    git_run("add", str(file_path))
    git_run("commit", "-m", message)


def git_merge_and_cleanup(branch_name):
    git_run("checkout", "--", ".", check=False)
    git_run("checkout", "main")
    git_run("merge", branch_name, "--no-edit")
    git_run("branch", "-d", branch_name)


def git_discard_branch(branch_name):
    # Reset any uncommitted changes before switching branches
    git_run("checkout", "--", ".", check=False)
    git_run("checkout", "main")
    git_run("branch", "-D", branch_name, check=False)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def run_evaluation(room_cfg: dict) -> dict:
    """Run a room's evaluation command and return the score dict."""
    eval_cfg = room_cfg["evaluation"]
    cmd = eval_cfg["command"]
    timeout = eval_cfg.get("timeout_seconds", 120)

    try:
        result = subprocess.run(
            cmd, shell=True, cwd=ROOT,
            capture_output=True, text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return {"composite_score": 0.0, "status": "timeout", "error": "timeout"}

    if result.returncode != 0:
        return {
            "composite_score": 0.0,
            "status": "crash",
            "error": result.stderr[:500]
        }

    # Try to parse JSON from stdout (last line or full output)
    try:
        # Look for JSON in output (may have print statements before it)
        lines = result.stdout.strip().split("\n")
        for line in reversed(lines):
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
        # If no JSON line found, try full output
        return json.loads(result.stdout)
    except (json.JSONDecodeError, IndexError):
        return {
            "composite_score": 0.0,
            "status": "parse_error",
            "error": f"Could not parse score from: {result.stdout[:300]}"
        }


# ---------------------------------------------------------------------------
# LLM proposal
# ---------------------------------------------------------------------------
def _call_llm(prompt: str, model: str, max_retries: int = 3) -> str:
    """Call LLM (GitHub Models or Anthropic) with retry on rate limits."""
    global LLM_PROVIDER, LLM_CLIENT

    for attempt in range(max_retries):
        try:
            if LLM_PROVIDER == "github":
                response = LLM_CLIENT.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_completion_tokens=2000,
                )
                return response.choices[0].message.content.strip()
            else:
                response = LLM_CLIENT.messages.create(
                    model=model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text.strip()
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                wait = 30 * (2 ** attempt)  # 30s, 60s, 120s
                print(f"  Rate limited, waiting {wait}s (attempt {attempt + 1}/{max_retries})...")
                import time
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Rate limited after {max_retries} retries")


def propose_change(model: str, room_name: str, room_cfg: dict,
                   history: list, eval_result: dict = None) -> dict:
    """Ask LLM to propose a change. Returns {file, old_content, new_content, description}."""
    editable_files = room_cfg["editable"]

    # Pick the first editable file (or rotate based on history)
    target_file = editable_files[0]
    if len(editable_files) > 1:
        # Rotate: pick file least recently modified in history
        modified_counts = {}
        for r in history:
            f = r.get("file_changed", "")
            modified_counts[f] = modified_counts.get(f, 0) + 1
        # Pick least modified
        for ef in editable_files:
            if ef not in modified_counts:
                target_file = ef
                break
        else:
            target_file = min(editable_files,
                              key=lambda x: modified_counts.get(x, 0))

    # Read current content
    file_path = ROOT / target_file
    if not file_path.exists():
        return {"error": f"File not found: {target_file}"}
    current_content = file_path.read_text()

    # Truncate if too long (keep first/last 100 lines)
    lines = current_content.split("\n")
    if len(lines) > 250:
        current_content = "\n".join(
            lines[:125] + ["", "... (truncated) ...", ""] + lines[-125:]
        )

    # Format history
    history_text = "No previous experiments." if not history else ""
    for r in history[-5:]:
        history_text += (
            f"- [{r.get('status', '?')}] score={r.get('score', '?')} "
            f"delta={r.get('delta', '?')} | {r.get('description', '?')}\n"
        )

    # Format eval diagnostics
    eval_diag = ""
    if eval_result:
        status = eval_result.get("status", "ok")
        error = eval_result.get("error", "")
        score = eval_result.get("composite_score", 0.0)
        details = eval_result.get("details", {})
        eval_diag = f"""EVALUATION RESULT (score={score:.4f}, status={status}):
{f'ERROR OUTPUT: {error[:500]}' if error else 'No errors.'}
{f'DETAILS: {json.dumps(details, indent=2)[:500]}' if details else ''}
"""

    prompt = f"""You are the AutoResearch agent improving belico-stack.

ROOM: {room_name} — {room_cfg.get('description', '')}
TARGET FILE: {target_file}
METRIC: {room_cfg.get('metric', 'composite_score')} (higher = better)

{eval_diag}
RECENT EXPERIMENTS FOR THIS ROOM:
{history_text}

CURRENT FILE CONTENT:
```
{current_content}
```

RULES:
- Propose ONE small, atomic change to this file
- Prefer deletions and simplifications over additions
- Do NOT add new dependencies
- The change should plausibly improve the evaluation score
- If recent experiments show a pattern (e.g., adding checks works), build on it
- If recent experiments all failed, try a different approach

RESPOND WITH EXACTLY THIS JSON FORMAT (no other text):
{{
  "file": "{target_file}",
  "description": "one-line description of the change",
  "search": "exact text to find in the file (must be unique)",
  "replace": "exact replacement text"
}}

If you cannot propose a useful change, respond:
{{
  "file": "{target_file}",
  "description": "skip — no useful change found",
  "search": "",
  "replace": ""
}}"""

    text = _call_llm(prompt, model)

    # Extract JSON from response (may have markdown code fences)
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        proposal = json.loads(text)
    except json.JSONDecodeError:
        return {"error": f"Could not parse proposal: {text[:200]}"}

    proposal["file_path"] = str(ROOT / proposal["file"])
    proposal["current_content"] = (ROOT / proposal["file"]).read_text()
    return proposal


def apply_change(proposal: dict) -> bool:
    """Apply a proposed change to a file. Returns True if successful."""
    if not proposal.get("search") or not proposal.get("replace"):
        return False
    if proposal["search"] == proposal["replace"]:
        return False

    file_path = Path(proposal["file_path"])
    content = file_path.read_text()

    if proposal["search"] not in content:
        return False

    # Check uniqueness
    count = content.count(proposal["search"])
    if count != 1:
        return False

    new_content = content.replace(proposal["search"], proposal["replace"], 1)
    file_path.write_text(new_content)
    return True


def revert_change(proposal: dict):
    """Revert a file to its original content."""
    file_path = Path(proposal["file_path"])
    file_path.write_text(proposal["current_content"])


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def select_room(rooms: dict, settings: dict, history: list,
                target_room: str = None) -> str:
    """Select next room using priority + consecutive failure avoidance."""
    if target_room and target_room in rooms:
        return target_room

    max_failures = 5
    sorted_rooms = sorted(rooms.items(),
                          key=lambda x: x[1].get("priority", 99))

    for room_name, room_cfg in sorted_rooms:
        # Check consecutive failures
        room_history = [r for r in history if r.get("room") == room_name]
        recent = room_history[-max_failures:] if room_history else []
        if len(recent) >= max_failures and all(
            r.get("status") in ("discard", "crash", "timeout")
            for r in recent
        ):
            continue  # Skip this room
        return room_name

    return None  # All rooms exhausted


def run_loop(max_experiments: int, target_room: str = None,
             dry_run: bool = False):
    """Main autoresearch loop."""
    rooms, settings = load_rooms_config()
    min_threshold = settings.get("min_improvement_threshold", 0.001)

    # Pick model based on provider
    if LLM_PROVIDER == "github":
        model = settings.get("github_model", "openai/gpt-4o-mini")
    else:
        model = settings.get("model", "claude-sonnet-4-20250514")

    init_results_file()

    # Verify we're on main
    current_branch = git_current_branch()
    if current_branch != "main":
        print(f"WARNING: Not on main branch (on {current_branch}). Switching.")
        git_run("checkout", "main")

    experiment_count = 0
    kept_count = 0
    discarded_count = 0

    print(f"\n{'='*60}")
    print(f"  AUTORESEARCH — Belico Stack Self-Improvement")
    print(f"  Model: {model}")
    print(f"  Max experiments: {max_experiments}")
    print(f"  Target room: {target_room or 'all (round-robin)'}")
    print(f"  Dry run: {dry_run}")
    print(f"{'='*60}\n")

    for i in range(max_experiments):
        history = load_results(last_n=50)
        room_name = select_room(rooms, settings, history, target_room)

        if room_name is None:
            print("\nAll rooms exhausted (5+ consecutive failures each). Stopping.")
            break

        room_cfg = rooms[room_name]
        room_history = load_results(room_name=room_name, last_n=10)
        experiment_count += 1
        branch_name = f"autoresearch/{room_name}/{experiment_count}"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        print(f"\n--- Experiment {experiment_count}/{max_experiments} "
              f"[{room_name}] ---")

        # 1. Get baseline score
        print("  Measuring baseline...")
        baseline_result = run_evaluation(room_cfg)
        baseline_score = baseline_result.get("composite_score", 0.0)
        print(f"  Baseline score: {baseline_score:.4f}")

        # 2. Propose change
        print("  Proposing change...")
        proposal = propose_change(model, room_name, room_cfg,
                                  room_history, baseline_result)

        if "error" in proposal:
            print(f"  Proposal error: {proposal['error']}")
            append_result({
                "timestamp": now, "room": room_name,
                "experiment": experiment_count,
                "file_changed": "", "score": "0",
                "baseline": str(baseline_score), "delta": "0",
                "status": "error",
                "description": f"proposal error: {proposal['error'][:100]}"
            })
            continue

        desc = proposal.get("description", "no description")
        print(f"  Proposal: {desc}")
        print(f"  File: {proposal.get('file', '?')}")

        if desc.startswith("skip"):
            print("  Agent skipped — no useful change found.")
            append_result({
                "timestamp": now, "room": room_name,
                "experiment": experiment_count,
                "file_changed": proposal.get("file", ""),
                "score": str(baseline_score),
                "baseline": str(baseline_score), "delta": "0",
                "status": "skip",
                "description": desc
            })
            continue

        if dry_run:
            print(f"  [DRY RUN] Would apply: {desc}")
            print(f"  Search: {proposal.get('search', '')[:80]}...")
            print(f"  Replace: {proposal.get('replace', '')[:80]}...")
            continue

        # 3. Create branch and apply
        try:
            git_create_branch(branch_name)
        except RuntimeError as e:
            print(f"  Git branch error: {e}")
            git_run("checkout", "main")
            continue

        applied = apply_change(proposal)
        if not applied:
            print("  Could not apply change (search text not found or not unique).")
            git_discard_branch(branch_name)
            append_result({
                "timestamp": now, "room": room_name,
                "experiment": experiment_count,
                "file_changed": proposal.get("file", ""),
                "score": "0", "baseline": str(baseline_score), "delta": "0",
                "status": "apply_failed",
                "description": f"apply failed: {desc}"
            })
            continue

        # 4. Commit
        git_commit(proposal["file"], f"autoresearch({room_name}): {desc}")

        # 5. Evaluate
        print("  Evaluating...")
        eval_result = run_evaluation(room_cfg)
        new_score = eval_result.get("composite_score", 0.0)
        delta = new_score - baseline_score
        print(f"  New score: {new_score:.4f} (delta: {delta:+.4f})")

        # 6. Keep or discard
        if eval_result.get("status") in ("crash", "timeout", "parse_error"):
            status = eval_result["status"]
            print(f"  {status.upper()} — discarding.")
            git_discard_branch(branch_name)
            discarded_count += 1
        elif delta > min_threshold:
            status = "keep"
            print(f"  KEEP — improvement of {delta:+.4f}")
            git_merge_and_cleanup(branch_name)
            kept_count += 1
        else:
            status = "discard"
            print(f"  DISCARD — no improvement (delta={delta:+.4f})")
            git_discard_branch(branch_name)
            discarded_count += 1

        # 7. Record
        append_result({
            "timestamp": now, "room": room_name,
            "experiment": experiment_count,
            "file_changed": proposal.get("file", ""),
            "score": f"{new_score:.4f}",
            "baseline": f"{baseline_score:.4f}",
            "delta": f"{delta:+.4f}",
            "status": status,
            "description": desc
        })

    # Summary
    print(f"\n{'='*60}")
    print(f"  AUTORESEARCH COMPLETE")
    print(f"  Total experiments: {experiment_count}")
    print(f"  Kept: {kept_count}")
    print(f"  Discarded: {discarded_count}")
    print(f"  Results: {RESULTS_PATH}")
    print(f"{'='*60}\n")

    # Commit results.tsv
    if not dry_run and RESULTS_PATH.exists():
        try:
            git_run("add", str(RESULTS_PATH))
            git_run("commit", "-m",
                    f"autoresearch: {now} — {kept_count}/{experiment_count} kept")
        except RuntimeError:
            pass  # No changes to commit

    return kept_count, discarded_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _init_llm_client():
    """Initialize LLM client. Priority: GITHUB_TOKEN > ANTHROPIC_API_KEY."""
    global LLM_PROVIDER, LLM_CLIENT

    github_token = os.environ.get("GITHUB_TOKEN")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if github_token:
        try:
            from openai import OpenAI
            LLM_CLIENT = OpenAI(
                base_url="https://models.github.ai/inference",
                api_key=github_token,
            )
            LLM_PROVIDER = "github"
            print("  LLM: GitHub Models (free with GITHUB_TOKEN)")
            return
        except ImportError:
            print("WARNING: openai SDK not installed for GitHub Models.")
            print("  pip install openai")

    if anthropic_key:
        try:
            import anthropic
            LLM_CLIENT = anthropic.Anthropic()
            LLM_PROVIDER = "anthropic"
            print("  LLM: Anthropic API")
            return
        except ImportError:
            print("WARNING: anthropic SDK not installed.")
            print("  pip install anthropic")

    print("ERROR: No LLM provider available.")
    print("  Set GITHUB_TOKEN (free) or ANTHROPIC_API_KEY")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="AutoResearch: Self-improving paper factory"
    )
    parser.add_argument("--experiments", type=int, default=10,
                        help="Max experiments per run (default: 10)")
    parser.add_argument("--room", type=str, default=None,
                        help="Target room (default: all, round-robin)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Propose changes without applying")
    args = parser.parse_args()

    _init_llm_client()

    kept, discarded = run_loop(
        max_experiments=args.experiments,
        target_room=args.room,
        dry_run=args.dry_run
    )
    # Exit 0 always — the workflow commit step handles "no changes" gracefully
    sys.exit(0)


if __name__ == "__main__":
    main()
