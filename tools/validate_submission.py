#!/usr/bin/env python3
"""
tools/validate_submission.py — Pre-Submission Validator for EIU Papers
=======================================================================
Checks that a draft meets all requirements before submission to a journal.

Checks:
  0. AI prose detection (blacklisted phrases, structural patterns)
  0.5. Data traceability (manifest.yaml vs quartile requirements)
  0.6. COMPUTE gate (COMPUTE_MANIFEST.json required)
  0.7. Style calibration gate (style_card.json required for Q1/Q2)
  0.8. Statistics Citation Gate (cv_results.json p-values must appear in draft for Q1/Q2)
  1. YAML frontmatter present and complete
  2. AI_Assist markers in all AI-generated sections
  3. HV (Human Validation) markers with initials
  4. All referenced figures exist in articles/figures/
  5. Bibliography references resolved (no broken [?])
  6. Word count within target range
  7. Required IMRaD sections present
  8. No TODO markers remaining
  9. Journal specs quality gates (from .agent/specs/journal_specs.yaml):
     - Reference count, figure count, required sections, novelty gate
     - Normative framework: Q1 min 2 intl codes (ERROR), Q2 min 1 (WARN)
     - Multi-structure: Q1 requires min 2 structures/specimens (ERROR)

Usage:
  python3 tools/validate_submission.py articles/drafts/paper_Q2_xxx.md
  python3 tools/validate_submission.py articles/drafts/*.md   # batch check
  python3 tools/validate_submission.py articles/drafts/paper.md --diagnose
"""

import re
import sys
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "articles" / "figures"
SPECS_PATH = ROOT / ".agent" / "specs" / "journal_specs.yaml"

IMRAD_SECTIONS = ["Abstract", "Introduction", "Methodology", "Results",
                  "Discussion", "Conclusion"]

# Anti-AI blacklisted phrases — instant rejection if found in draft
# SSOT: Belico.md — keep synced
AI_BLACKLISTED_PHRASES = [
    "it is worth mentioning",
    "it is worth noting",
    "it is important to note",
    "it should be noted",
    "intricacies",
    "delve into",
    "delve deeper",
    "shed light on",
    "leverages",
    "leveraging",
    "noteworthy",
    "utilizing",
    "harnessing",
    "novel framework",
    "novel approach",
    "novel methodology",
    "plays a crucial role",
    "has gained significant attention",
    "in recent years",
    "in the last decade",
    "paradigm shift",
    "game-changer",
    "groundbreaking",
    "revolutionary",
    "a myriad of",
    "a plethora of",
    "a multitude of",
    "in conclusion, this study has demonstrated",
    "paving the way for future research",
    "seamless",
    "straightforward",
    "cutting-edge",
    # NOTE: "comprehensive", "robust", and "state-of-the-art" are NOT banned here.
    # Per Belico.md they are only banned "without citation", which requires context
    # analysis. The Reviewer Simulator sub-agent enforces this rule during VERIFY
    # since it can check whether a supporting citation accompanies the term.
]

# Phrases that are only banned as sentence starters
AI_BLACKLISTED_STARTERS = [
    "furthermore,",
    "moreover,",
    "additionally,",
    "in this study, we",
    "this paper presents",
    "this work proposes",
]


def _load_journal_specs() -> dict:
    """Load journal quality gates from specs file."""
    if not HAS_YAML or not SPECS_PATH.exists():
        return {}
    with open(SPECS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _extract_quartile(text: str) -> str:
    """Extract quartile from frontmatter."""
    m = re.search(r"quartile:\s*[\"']?(\w+)[\"']?", text)
    return m.group(1) if m else ""


def check_ai_prose(text: str, lines: list[str]) -> list[dict]:
    """Check draft for AI-generated prose patterns. Returns list of issues."""
    issues = []
    text_lower = text.lower()

    # Strip frontmatter before checking
    body_start = 0
    if text.startswith("---"):
        fm_end = text.find("---", 3)
        if fm_end != -1:
            body_start = fm_end + 3

    body = text[body_start:]
    body_lower = body.lower()
    body_lines = body.split("\n")

    # 1. Check blacklisted phrases
    for phrase in AI_BLACKLISTED_PHRASES:
        # Find all occurrences with line numbers
        for i, line in enumerate(lines):
            if phrase in line.lower():
                issues.append({
                    "severity": "ERROR", "check": "ai_prose",
                    "msg": f"Blacklisted phrase '{phrase}' at line {i + 1}"
                })

    # 2. Check blacklisted sentence starters (including mid-line after ". ")
    for starter in AI_BLACKLISTED_STARTERS:
        for i, line in enumerate(lines):
            # Split line into sentences to catch mid-line starters
            sentences = line.strip().split(". ")
            for sent in sentences:
                if sent.strip().lower().startswith(starter):
                    issues.append({
                        "severity": "ERROR", "check": "ai_prose",
                        "msg": f"Blacklisted sentence starter '{starter}' at line {i + 1}"
                    })
                    break  # one match per line per starter is enough

    # 3. Check sentences longer than 40 words
    # Split body into sentences (rough but effective)
    sentences = re.split(r'(?<=[.!?])\s+', body)
    for sent in sentences:
        word_count = len(sent.split())
        if word_count > 40:
            # Find line number of this sentence
            snippet = sent[:60].strip()
            for i, line in enumerate(lines):
                if snippet[:30] in line:
                    issues.append({
                        "severity": "WARN", "check": "ai_prose",
                        "msg": f"Sentence > 40 words ({word_count}w) at line {i + 1}: '{snippet}...'"
                    })
                    break

    # 4. Check consecutive paragraphs starting with same word
    paragraphs = re.split(r'\n\s*\n', body)
    para_starters = []
    for para in paragraphs:
        first_line = para.strip().split('\n')[0].strip()
        if first_line and not first_line.startswith('#') and not first_line.startswith('!'):
            first_word = re.split(r'\s+', first_line)[0].lower().strip('*_')
            if first_word:
                para_starters.append(first_word)

    for i in range(len(para_starters) - 1):
        if para_starters[i] == para_starters[i + 1]:
            issues.append({
                "severity": "WARN", "check": "ai_prose",
                "msg": f"Consecutive paragraphs start with '{para_starters[i]}' — vary openers"
            })

    # 5. Check 3+ consecutive sentences starting with "The"
    the_streak = 0
    for sent in sentences:
        stripped = sent.strip()
        if stripped.lower().startswith("the "):
            the_streak += 1
            if the_streak >= 3:
                issues.append({
                    "severity": "WARN", "check": "ai_prose",
                    "msg": f"{the_streak} consecutive sentences start with 'The' — vary structure"
                })
        else:
            the_streak = 0

    return issues


def check_data_traceability(content: str, frontmatter: str, issues: list[dict]):
    """Check that paper references real data matching its quartile requirements.

    Reads db/manifest.yaml (top-level keys: excitation, benchmarks, calibration,
    validation, traceability) and verifies against quartile requirements.
    """
    quartile = _extract_quartile(frontmatter).lower()

    if not quartile:
        issues.append({
            "severity": "ERROR", "check": "data_traceability",
            "msg": "Paper missing 'quartile' field in frontmatter. "
                   "Data traceability cannot be verified."
        })
        return

    # Quartile requirements matrix: section -> set of quartiles that REQUIRE it
    quartile_requires = {
        "excitation":   {"conference", "q4", "q3", "q2", "q1"},
        "benchmarks":   {"q3", "q2", "q1"},
        "calibration":  {"q2", "q1"},
        "validation":   {"q2", "q1"},
    }

    manifest_path = ROOT / "db" / "manifest.yaml"

    if not manifest_path.exists():
        issues.append({
            "severity": "ERROR", "check": "data_traceability",
            "msg": "db/manifest.yaml not found. Run: python3 tools/select_ground_motions.py"
        })
        return

    # Load manifest
    manifest = {}
    if HAS_YAML:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f) or {}
    else:
        # Fallback: simple line parsing for key fields
        raw = manifest_path.read_text(encoding="utf-8")
        if re.search(r"paper_id:\s*\S+", raw):
            manifest["paper_id"] = "present"
        if re.search(r"excitation:", raw):
            manifest["excitation"] = {"status": "unknown"}
        for section in ("benchmarks", "calibration", "validation"):
            if re.search(rf"^{section}:", raw, re.MULTILINE):
                manifest[section] = [{"status": "unknown"}]
        if re.search(r"traceability:", raw):
            manifest["traceability"] = "present"

    # Check 1: paper_id configured
    paper_id = manifest.get("paper_id", "")
    if not paper_id:
        issues.append({
            "severity": "ERROR", "check": "data_traceability",
            "msg": "db/manifest.yaml paper_id is empty. Run: python3 tools/select_ground_motions.py"
        })
        # Still show quartile requirements so user knows what data to gather
        if quartile:
            needed = [k for k, qs in quartile_requires.items() if quartile in qs]
            issues.append({
                "severity": "INFO", "check": "data_traceability",
                "msg": f"Quartile '{quartile}' requires: {', '.join(needed)}"
            })
        return

    # Check 1.5: Quartile mismatch between paper and manifest
    manifest_quartile = manifest.get("quartile", "").lower()
    if manifest_quartile and quartile and manifest_quartile != quartile:
        issues.append({
            "severity": "WARN", "check": "data_traceability",
            "msg": f"Quartile mismatch: paper says '{quartile}', manifest says "
                   f"'{manifest_quartile}'. Update db/manifest.yaml to match."
        })

    # Check 2: Excitation (ALL quartiles)
    excitation = manifest.get("excitation", {})
    if isinstance(excitation, dict):
        exc_status = excitation.get("status", "pending")
        records_present = excitation.get("records_present", [])

        if exc_status == "pending" and not records_present:
            issues.append({
                "severity": "ERROR", "check": "data_traceability",
                "msg": "No excitation records. PEER benchmark is mandatory for ALL quartiles"
            })
        elif exc_status == "pending" and records_present:
            # Records listed but status not updated — treat as partial
            issues.append({
                "severity": "WARN", "check": "data_traceability",
                "msg": f"Excitation has {len(records_present)} records but status is 'pending'. "
                       "Verify files and update status."
            })
        elif exc_status == "partial":
            issues.append({
                "severity": "WARN", "check": "data_traceability",
                "msg": "Excitation records partially downloaded. "
                       "Complete download from ngawest2.berkeley.edu"
            })
        # "complete" → no issue

        # Verify records_present files exist on disk
        if records_present:
            ext_dir = ROOT / "db" / "excitation" / "records"
            missing = []
            for rec in records_present:
                fname = rec.get("filename", "") if isinstance(rec, dict) else str(rec)
                if fname and not (ext_dir / fname).exists():
                    missing.append(fname)
            if missing:
                issues.append({
                    "severity": "WARN", "check": "data_traceability",
                    "msg": f"{len(missing)}/{len(records_present)} excitation files not found on disk: "
                           f"{', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}"
                })
    else:
        issues.append({
            "severity": "ERROR", "check": "data_traceability",
            "msg": "No excitation records. PEER benchmark is mandatory for ALL quartiles"
        })

    # Helper: check if a list section has at least one "complete" entry
    def _has_complete(section_data: list) -> bool:
        if not isinstance(section_data, list):
            return False
        return any(
            isinstance(item, dict) and item.get("status") == "complete"
            for item in section_data
        )

    # Check 3: Benchmarks (Q3+)
    if quartile in quartile_requires["benchmarks"]:
        benchmarks = manifest.get("benchmarks", [])
        if not _has_complete(benchmarks):
            issues.append({
                "severity": "ERROR", "check": "data_traceability",
                "msg": "Q3+ requires benchmark dataset for method validation"
            })

    # Check 4: Calibration (Q2+)
    if quartile in quartile_requires["calibration"]:
        calibration = manifest.get("calibration", [])
        if not _has_complete(calibration):
            issues.append({
                "severity": "ERROR", "check": "data_traceability",
                "msg": "Q2+ requires site-specific calibration data"
            })

    # Check 5: Validation (Q2+)
    if quartile in quartile_requires["validation"]:
        validation = manifest.get("validation", [])
        if not _has_complete(validation):
            issues.append({
                "severity": "ERROR", "check": "data_traceability",
                "msg": "Q2+ requires independent validation measurements (field or lab)"
            })

    # Check 6: Traceability chain
    traceability = manifest.get("traceability", [])
    if not traceability:
        issues.append({
            "severity": "WARN", "check": "data_traceability",
            "msg": "No traceability entries in manifest. Fill traceability section during IMPLEMENT."
        })


def _extract_frontmatter(text: str) -> str:
    """Extract raw frontmatter content (between --- delimiters). Returns empty str if none."""
    if not text.startswith("---"):
        return ""
    fm_end = text.find("---", 3)
    if fm_end == -1:
        return ""
    return text[3:fm_end]


def _extract_fm_field(fm: str, field: str) -> str:
    """Extract a single scalar field from raw frontmatter text."""
    m = re.search(rf"^{re.escape(field)}:\s*[\"\']?([^\n\"\']+)[\"\']?", fm, re.MULTILINE)
    return m.group(1).strip() if m else ""


def check_pipeline_state(draft_path: Path, issues: list[dict]):
    """Gate 0.0 — One-paper-at-a-time enforcement.

    Scans all .md files in articles/drafts/ looking for any paper whose
    status is not 'archived' or 'submitted'. If one is found that is NOT
    the draft being validated, block with an ERROR.

    Only files with a known paper status (draft, review, submitted, archived)
    in their frontmatter are considered. Utility files (novelty_report,
    style_card, etc.) have no recognized status and are ignored.
    """
    drafts_dir = ROOT / "articles" / "drafts"
    if not drafts_dir.exists():
        return  # Nothing to check

    # Extract identifiers from the draft being validated (for WARN if missing)
    current_text = draft_path.read_text(encoding="utf-8")
    current_fm = _extract_frontmatter(current_text)
    current_paper_id = _extract_fm_field(current_fm, "paper_id")
    current_title = _extract_fm_field(current_fm, "title")

    if not current_paper_id and not current_title:
        # Warn but still scan for other active papers
        issues.append({
            "severity": "WARN",
            "check": "pipeline_state",
            "msg": (
                "Draft has no \'paper_id\' in frontmatter. "
                "Pipeline state gate cannot fully identify this paper. "
                "Add \'paper_id: <slug>\' to frontmatter."
            ),
        })

    active_others: list[dict] = []
    known_statuses = {"draft", "review", "submitted", "archived"}

    for md_file in sorted(drafts_dir.glob("*.md")):
        # Skip the draft being validated
        if md_file.resolve() == draft_path.resolve():
            continue

        try:
            raw = md_file.read_text(encoding="utf-8")
        except OSError:
            continue  # Unreadable file — skip silently

        # Only inspect the first 30 lines (frontmatter lives there)
        first_lines = "\n".join(raw.split("\n")[:30])
        fm = _extract_frontmatter(first_lines)
        if not fm:
            # No frontmatter — not a paper draft, skip
            continue

        status = _extract_fm_field(fm, "status").lower()
        paper_id = _extract_fm_field(fm, "paper_id")
        title = _extract_fm_field(fm, "title")
        label = paper_id or title or md_file.stem

        # Only files with a recognized paper status are considered.
        # Utility files (novelty_report, style_card) have no status or
        # an unrecognized one, and are safely ignored.
        if status not in known_statuses:
            continue

        if status not in ("archived", "submitted"):
            active_others.append({
                "file": md_file.name,
                "label": label,
                "status": status,
            })

    if active_others:
        for other in active_others:
            _label = other["label"]
            _status = other["status"]
            _fname = other["file"]
            issues.append({
                "severity": "ERROR",
                "check": "pipeline_state",
                "msg": (
                    f"PIPELINE_BLOCKED: '{_label}' (status: {_status}) "
                    f"in '{_fname}' is still active. "
                    f"Archive it before starting a new paper. "
                    f"Set 'status: archived' in its frontmatter."
                ),
            })
    else:
        issues.append({
            "severity": "OK",
            "check": "pipeline_state",
            "msg": "Pipeline state OK — no other active papers detected",
        })


def validate_draft(draft_path: Path) -> list[dict]:
    """Validate a single draft. Returns list of issues."""
    issues = []
    text = draft_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    # 0.0 Pipeline State Gate (runs FIRST — blocks if another paper is active)
    check_pipeline_state(draft_path, issues)

    # 0. AI Prose Detection (first check — blocks everything if fails)
    ai_issues = check_ai_prose(text, lines)
    issues.extend(ai_issues)

    # 0.5. Data Traceability (manifest vs quartile requirements)
    fm_text = ""
    if text.startswith("---"):
        fm_end = text.find("---", 3)
        if fm_end != -1:
            fm_text = text[3:fm_end]
    check_data_traceability(text, fm_text, issues)

    # 0.6. COMPUTE Gate — blocks submission if COMPUTE phase never ran
    # COMPUTE_MANIFEST.json is created by the COMPUTE phase (C5) and proves
    # that real simulations/data were generated before writing the paper.
    compute_manifest_path = ROOT / "data" / "processed" / "COMPUTE_MANIFEST.json"
    if not compute_manifest_path.exists():
        issues.append({
            "severity": "ERROR",
            "check": "compute_gate",
            "msg": (
                "BLOQUEADO: data/processed/COMPUTE_MANIFEST.json not found. "
                "The COMPUTE phase (C0-C5) must run before IMPLEMENT. "
                "Run simulations first, then verify: python3 tools/validate_submission.py --diagnose"
            )
        })
    else:
        try:
            import json as _json
            with open(compute_manifest_path) as _f:
                manifest_data = _json.load(_f)
            is_demo = manifest_data.get("is_template_demo", False)
            all_sources_exist = manifest_data.get("all_design_sources_exist", False)
            simulations_run = manifest_data.get("simulations_run", 0)
            emulation_ran = manifest_data.get("emulation_ran", False)
            guardian_validated = manifest_data.get("guardian_validated", False)

            if not all_sources_exist:
                issues.append({
                    "severity": "ERROR",
                    "check": "compute_gate",
                    "msg": (
                        "COMPUTE_MANIFEST.json exists but all_design_sources_exist=false. "
                        "Some planned data files are missing. Re-run COMPUTE phase."
                    )
                })
            elif simulations_run == 0:
                issues.append({
                    "severity": "ERROR",
                    "check": "compute_gate",
                    "msg": "COMPUTE_MANIFEST.json shows 0 simulations run. No real data produced."
                })
            elif not is_demo and not emulation_ran:
                # All digital-twin projects require Arduino/LoRa emulation (C3).
                # The template demo is exempt; real project clones are not.
                issues.append({
                    "severity": "ERROR",
                    "check": "compute_gate",
                    "msg": (
                        "BLOQUEADO: emulation_ran=false in COMPUTE_MANIFEST.json. "
                        "All digital-twin projects must run Arduino/LoRa emulation (C3). "
                        "Run: python3 tools/arduino_emu.py [mode] && bash tools/run_battle.sh"
                    )
                })
            elif not is_demo and not guardian_validated:
                issues.append({
                    "severity": "ERROR",
                    "check": "compute_gate",
                    "msg": (
                        "BLOQUEADO: guardian_validated=false in COMPUTE_MANIFEST.json. "
                        "Guardian Angel (S1-S4 gates) must be validated before submission. "
                        "Run: bash tools/run_guardian_test.sh"
                    )
                })
            else:
                emu_note = " (template demo — emulation exempt)" if is_demo else ""
                issues.append({
                    "severity": "OK",
                    "check": "compute_gate",
                    "msg": (
                        f"COMPUTE gate passed: {simulations_run} simulations, "
                        f"emulation={'OK' if (emulation_ran or is_demo) else 'SKIP'}, "
                        f"guardian={'OK' if (guardian_validated or is_demo) else 'SKIP'}"
                        f"{emu_note}"
                    )
                })
        except Exception as _e:
            issues.append({
                "severity": "WARN",
                "check": "compute_gate",
                "msg": f"Could not read COMPUTE_MANIFEST.json: {_e}"
            })

    # 0.7. Style Calibration Gate — warns/blocks if style_card.json is missing
    # Style calibration is mandatory for Q1/Q2 (ERROR) and recommended for others (WARN).
    # Run: python3 tools/style_calibration.py --venue '<journal>' --paper-id '<paper_id>'
    style_card_path = ROOT / "data" / "processed" / "style_card.json"
    if not style_card_path.exists():
        # Extract quartile and journal for helpful message
        sc_quartile = _extract_quartile(text).lower()
        sc_journal_match = re.search(r"journal:\s*[\"']?([^\n\"']+)[\"']?", text)
        sc_journal = sc_journal_match.group(1).strip() if sc_journal_match else "<journal>"
        sc_paper_id_match = re.search(r"paper_id:\s*[\"']?([^\n\"']+)[\"']?", text)
        sc_paper_id = sc_paper_id_match.group(1).strip() if sc_paper_id_match else "<paper_id>"
        sc_severity = "ERROR" if sc_quartile in ("q1", "q2") else "WARN"
        issues.append({
            "severity": sc_severity,
            "check": "style_gate",
            "msg": (
                f"Style calibration not found. "
                f"Run: python3 tools/style_calibration.py --venue '{sc_journal}' --paper-id '{sc_paper_id}'"
            )
        })
    else:
        issues.append({
            "severity": "OK",
            "check": "style_gate",
            "msg": "Style card found at data/processed/style_card.json"
        })

    # 0.8. Statistics Citation Gate — cv_results.json p-values must be cited in draft (Q1/Q2)
    cv_results_path = ROOT / "data" / "processed" / "cv_results.json"
    if cv_results_path.exists():
        try:
            import json as _json_cv
            with open(cv_results_path) as _fcv:
                cv_data = _json_cv.load(_fcv)

            # Detect if cv_results.json contains computed statistics.
            # Accept: statistics_summary.p_value or any key ending in _pvalue / p_value.
            has_stats = False
            detected_pvalue = None

            stats_block = cv_data.get("statistics_summary", {})
            if isinstance(stats_block, dict):
                for pv_key in ("p_value", "p_value_u", "p_value_mw"):
                    pv = stats_block.get(pv_key)
                    if pv is not None:
                        has_stats = True
                        detected_pvalue = pv
                        break

            if not has_stats:
                # Scan top-level and one level of nested dicts for *_pvalue / *p_value keys
                for k, v in cv_data.items():
                    if isinstance(k, str) and (k.endswith("_pvalue") or k.endswith("p_value")):
                        if v is not None:
                            has_stats = True
                            detected_pvalue = v
                            break
                    if isinstance(v, dict):
                        for kk, vv in v.items():
                            if isinstance(kk, str) and (kk.endswith("_pvalue") or kk.endswith("p_value")):
                                if vv is not None:
                                    has_stats = True
                                    detected_pvalue = vv
                                    break
                    if has_stats:
                        break

            if has_stats:
                # Patterns that indicate the draft cites statistical results
                stats_citation_patterns = [
                    r"p\s*[=<]\s*0\.",          # p = 0.03, p < 0.05, p=0.001
                    r"\bp\s*<\s*0\.",            # p < 0.001
                    r"Cohen'?s?\s+[dg]",         # Cohen's d, Cohens g
                    r"effect\s+size",            # effect size
                    r"Mann.Whitney",             # Mann-Whitney U
                    r"confidence\s+interval",   # confidence interval
                    r"\bCI\b",                   # CI (abbreviation)
                ]
                draft_cites_stats = any(
                    re.search(pat, text, re.IGNORECASE)
                    for pat in stats_citation_patterns
                )

                quartile_stats = _extract_quartile(text)
                q_lower = quartile_stats.lower()

                if not draft_cites_stats:
                    pval_str = (f"p={detected_pvalue}" if detected_pvalue is not None
                                else "p-value present")
                    stats_msg = (
                        f"STATS_NOT_CITED: cv_results.json contains computed statistics "
                        f"({pval_str}) but draft does not reference them. "
                        f"Cite p-values and effect sizes in Results section "
                        f"(e.g., 'Mann-Whitney U test yielded p < 0.05')."
                    )
                    if q_lower in ("q1", "q2"):
                        issues.append({
                            "severity": "ERROR",
                            "check": "stats_citation",
                            "msg": stats_msg,
                        })
                    elif q_lower == "q3":
                        issues.append({
                            "severity": "WARN",
                            "check": "stats_citation",
                            "msg": stats_msg,
                        })
                    # Conference / Q4 → skip silently
                else:
                    issues.append({
                        "severity": "OK",
                        "check": "stats_citation",
                        "msg": (
                            "Statistics citation check passed "
                            "(p-values/effect sizes cited in draft)"
                        ),
                    })
        except Exception as _e_cv:
            issues.append({
                "severity": "WARN",
                "check": "stats_citation",
                "msg": f"Could not read cv_results.json: {_e_cv}",
            })
    # cv_results.json absent → skip silently (no issue appended)

    # 1. YAML frontmatter
    if not text.startswith("---"):
        issues.append({"severity": "ERROR", "check": "frontmatter",
                        "msg": "Missing YAML frontmatter (must start with ---)"})
    else:
        fm_end = text.find("---", 3)
        if fm_end == -1:
            issues.append({"severity": "ERROR", "check": "frontmatter",
                            "msg": "Unclosed YAML frontmatter"})
        else:
            fm = text[3:fm_end]
            for field in ["title", "domain", "quartile", "status", "version"]:
                if field + ":" not in fm:
                    issues.append({"severity": "WARN", "check": "frontmatter",
                                    "msg": f"Missing frontmatter field: {field}"})
            if 'status: draft' in fm:
                issues.append({"severity": "INFO", "check": "frontmatter",
                                "msg": "Status is still 'draft' -- update before submission"})

    # 2. AI_Assist markers
    ai_count = text.count("<!-- AI_Assist -->")
    if ai_count == 0:
        issues.append({"severity": "ERROR", "check": "ai_markers",
                        "msg": "No <!-- AI_Assist --> markers found (required for transparency)"})

    # 3. HV markers
    hv_matches = re.findall(r"<!-- HV: (.+?) -->", text)
    unsigned = [m for m in hv_matches if "INICIALES" in m or not m.strip()]
    if not hv_matches:
        issues.append({"severity": "ERROR", "check": "hv_markers",
                        "msg": "No <!-- HV: --> markers found (human validation required)"})
    elif unsigned:
        issues.append({"severity": "WARN", "check": "hv_markers",
                        "msg": f"{len(unsigned)} HV markers still unsigned (contain 'INICIALES')"})

    # 4. Figure references
    fig_refs = re.findall(r"!\[.*?\]\((.+?)\)", text)
    for fig_ref in fig_refs:
        fig_path = ROOT / fig_ref if not Path(fig_ref).is_absolute() else Path(fig_ref)
        if not fig_path.exists():
            issues.append({"severity": "ERROR", "check": "figures",
                            "msg": f"Referenced figure not found: {fig_ref}"})

    # Also check inline Fig. N references
    fig_nums = re.findall(r"Fig\.?\s*(\d+)", text)
    # Just count them for info
    if fig_nums:
        issues.append({"severity": "INFO", "check": "figures",
                        "msg": f"References {len(set(fig_nums))} figures (Fig. {', '.join(sorted(set(fig_nums)))})"})

    # 5. Broken references
    broken_refs = text.count("[?]")
    if broken_refs:
        issues.append({"severity": "ERROR", "check": "bibliography",
                        "msg": f"{broken_refs} broken reference(s) found ([?])"})

    # 6. Word count
    # Strip markdown syntax for word count
    clean = re.sub(r"---.*?---", "", text, count=1, flags=re.DOTALL)
    clean = re.sub(r"[#*|`\[\]()!<>-]", " ", clean)
    clean = re.sub(r"\$.*?\$", "MATH", clean)
    words = len(clean.split())

    # Primary check: journal_specs wc_min/wc_max (when quartile is known)
    quartile_for_wc = _extract_quartile(text)
    specs_for_wc = _load_journal_specs()
    spec_for_wc = specs_for_wc.get(quartile_for_wc, specs_for_wc.get(quartile_for_wc.lower(), {}))
    wc_min_spec = spec_for_wc.get("word_count", {}).get("min", 0) if spec_for_wc else 0
    wc_max_spec = spec_for_wc.get("word_count", {}).get("max", 0) if spec_for_wc else 0

    if wc_min_spec and wc_max_spec:
        # Journal specs available — use as primary (ERROR severity)
        if words < wc_min_spec:
            issues.append({"severity": "ERROR", "check": "word_count",
                            "msg": f"Word count {words} < spec min {wc_min_spec} for {quartile_for_wc}"})
        elif words > wc_max_spec:
            issues.append({"severity": "ERROR", "check": "word_count",
                            "msg": f"Word count {words} > spec max {wc_max_spec} for {quartile_for_wc}"})
        else:
            issues.append({"severity": "OK", "check": "word_count",
                            "msg": f"Word count: {words} (spec range: {wc_min_spec}-{wc_max_spec} for {quartile_for_wc})"})

    # Secondary check: frontmatter target (INFO severity)
    target_match = re.search(r"word_count_target:\s*(\d+)", text)
    target = int(target_match.group(1)) if target_match else None
    if target:
        pct = (words / target) * 100
        if pct < 30:
            issues.append({"severity": "INFO", "check": "word_count",
                            "msg": f"Word count: {words}/{target} ({pct:.0f}%) -- very incomplete"})
        elif pct < 80:
            issues.append({"severity": "INFO", "check": "word_count",
                            "msg": f"Word count: {words}/{target} ({pct:.0f}%) -- in progress"})
        else:
            issues.append({"severity": "OK", "check": "word_count",
                            "msg": f"Word count: {words}/{target} ({pct:.0f}%)"})
    elif not wc_min_spec:
        # No specs and no frontmatter target — fallback
        issues.append({"severity": "INFO", "check": "word_count",
                        "msg": f"Word count: {words} (no spec or target available)"})

    # 7. IMRaD sections — prefer journal_specs required_sections if available
    # spec is loaded in check #9; reuse spec_for_wc which is the same lookup
    spec = spec_for_wc
    spec_sections = spec.get("required_sections", []) if spec else []
    sections_to_check = spec_sections if spec_sections else IMRAD_SECTIONS
    for section in sections_to_check:
        if section.lower() not in text.lower():
            source = "journal_spec" if spec_sections else "IMRaD default"
            issues.append({"severity": "WARN", "check": "structure",
                            "msg": f"Missing section ({source}): {section}"})

    # 7.5. Abstract word count (against journal_specs abstract.max_words)
    abstract_match = re.search(
        r"##\s*Abstract\s*\n(.*?)(?=\n##\s|\Z)", text, re.DOTALL | re.IGNORECASE
    )
    if abstract_match:
        abstract_text = abstract_match.group(1).strip()
        abstract_clean = re.sub(r"[#*|`\[\]()!<>-]", " ", abstract_text)
        abstract_clean = re.sub(r"\$.*?\$", "MATH", abstract_clean)
        abstract_words = len(abstract_clean.split())
        abstract_max = (spec_for_wc.get("abstract", {}).get("max_words", 0)
                        if spec_for_wc else 0)
        if abstract_max and abstract_words > abstract_max:
            issues.append({
                "severity": "WARN", "check": "abstract_length",
                "msg": f"Abstract has {abstract_words} words, spec max is "
                       f"{abstract_max} for {quartile_for_wc}"
            })
        elif abstract_words > 0:
            issues.append({
                "severity": "OK", "check": "abstract_length",
                "msg": f"Abstract word count: {abstract_words}"
                       + (f" (max {abstract_max})" if abstract_max else "")
            })

    # 7.6. Semicolon density (max 1 per paragraph — Belico.md structural rule)
    body_for_semi = text
    if text.startswith("---"):
        fm_end_semi = text.find("---", 3)
        if fm_end_semi != -1:
            body_for_semi = text[fm_end_semi + 3:]
    paragraphs_semi = re.split(r'\n\s*\n', body_for_semi)
    para_num = 0
    for para in paragraphs_semi:
        stripped_para = para.strip()
        # Skip headings, empty lines, and non-prose blocks
        if not stripped_para or stripped_para.startswith('#') or stripped_para.startswith('!'):
            continue
        para_num += 1
        semicolons = stripped_para.count(';')
        if semicolons > 1:
            issues.append({
                "severity": "WARN", "check": "semicolon_density",
                "msg": f"Paragraph {para_num} has {semicolons} semicolons (max 1 per paragraph)"
            })

    # 8. TODO markers
    todos = re.findall(r"\[TODO.*?\]", text, re.IGNORECASE)
    if todos:
        issues.append({"severity": "WARN", "check": "completeness",
                        "msg": f"{len(todos)} TODO markers remaining"})

    # 9. Journal specs quality gates
    quartile = _extract_quartile(text)
    specs = _load_journal_specs()
    spec = specs.get(quartile, specs.get(quartile.lower(), {}))

    if spec:
        # Reference count
        # Count both pandoc [@key] and numbered [N] reference formats
        cite_keys = re.findall(r"\[@([\w_]+)\]", text)
        numbered_refs = re.findall(r"^\[(\d+)\]\s+\S", text, re.MULTILINE)
        ref_count = max(len(set(cite_keys)), len(numbered_refs))
        ref_min = spec.get("references", {}).get("min", 0)
        ref_max = spec.get("references", {}).get("max", 999)
        if ref_count < ref_min:
            issues.append({"severity": "WARN", "check": "journal_spec",
                            "msg": f"References: {ref_count} < min {ref_min} for {quartile}"})
        elif ref_count > ref_max:
            issues.append({"severity": "WARN", "check": "journal_spec",
                            "msg": f"References: {ref_count} > max {ref_max} for {quartile}"})

        # Figure count
        fig_count = len(set(fig_nums)) if fig_nums else 0
        fig_min = spec.get("figures", {}).get("min", 0)
        if fig_count < fig_min:
            issues.append({"severity": "WARN", "check": "journal_spec",
                            "msg": f"Figures: {fig_count} < min {fig_min} for {quartile}"})

        # Word count range from spec — handled in check #6 (primary word count)

        # Required sections from spec
        for section in spec.get("required_sections", []):
            if section.lower() not in text.lower():
                issues.append({"severity": "ERROR", "check": "journal_spec",
                                "msg": f"Missing required section for {quartile}: {section}"})

        # Novelty gate
        if spec.get("novelty_gate") and "novelty" not in text.lower():
            issues.append({"severity": "WARN", "check": "journal_spec",
                            "msg": f"{quartile} requires explicit novelty statement"})

        # ── Normative framework enforcement (Q1: min 2 intl codes, Q2: min 1) ──
        # From journal_specs.yaml normative_framework.minimum_international_codes
        min_codes = (spec.get("normative_framework", {}) or {}).get("minimum_international_codes", 0)
        if min_codes and min_codes > 0:
            # Known international codes — search text (case-insensitive)
            intl_code_patterns = [
                (r"\bEurocode\s*8\b",     "Eurocode 8"),
                (r"\bEN\s*1998\b",         "Eurocode 8 (EN 1998)"),
                (r"\bASCE\s*7[-\s]\d+",   "ASCE 7"),
                (r"\bACI\s*318",           "ACI 318"),
                (r"\bfib\s+Model\s+Code", "fib Model Code"),
                (r"\bISO\s*13822",         "ISO 13822"),
                (r"\bIBC\s*20\d\d",        "IBC"),
                (r"\bECCS\b",              "ECCS"),
            ]
            cited_codes = [name for pat, name in intl_code_patterns
                           if re.search(pat, text, re.IGNORECASE)]
            n_found = len(cited_codes)
            if n_found < min_codes:
                sev = "ERROR" if quartile.lower() == "q1" else "WARN"
                issues.append({
                    "severity": sev,
                    "check": "normative_framework",
                    "msg": (
                        f"{quartile} requires min {min_codes} international normative code(s), "
                        f"found {n_found} ({', '.join(cited_codes) or 'none'}). "
                        f"Add references to: Eurocode 8, ASCE 7-22, ACI 318-19, or fib Model Code."
                    )
                })
            else:
                issues.append({
                    "severity": "OK",
                    "check": "normative_framework",
                    "msg": (
                        f"Normative framework: {n_found} international code(s) found "
                        f"({', '.join(cited_codes)}) — meets min {min_codes} for {quartile}"
                    )
                })

        # ── Multi-structure check (Q1: min 2 structures/specimens) ──
        # Q1 data_requirements: "min 2 structures or test specimens"
        if quartile.lower() == "q1":
            data_reqs = spec.get("data_requirements", [])
            needs_multi = any("2 struct" in r.lower() or "2 spec" in r.lower()
                              for r in data_reqs)
            if needs_multi:
                # Look for explicit multi-structure mentions in text
                multi_patterns = [
                    r"\btwo\s+(?:RC\s+)?(?:frame|building|structure|specimen|bridge|dam)\b",
                    r"\b2\s+(?:RC\s+)?(?:frame|building|structure|specimen|bridge|dam)\b",
                    r"\bstructure[s]?\s*(?:A|1)\b.*?\bstructure[s]?\s*(?:B|2)\b",
                    r"\bbuilding\s+(?:A|1)\b.*?\bbuilding\s+(?:B|2)\b",
                    r"\bspecimen\s+(?:A|1)\b.*?\bspecimen\s+(?:B|2)\b",
                    r"\bCase\s+(?:A|1)\b.*?\bCase\s+(?:B|2)\b",
                ]
                found_multi = any(re.search(p, text, re.IGNORECASE | re.DOTALL)
                                  for p in multi_patterns)
                if not found_multi:
                    issues.append({
                        "severity": "ERROR",
                        "check": "multi_structure",
                        "msg": (
                            "Q1 requires min 2 structures or test specimens with independent data. "
                            "Paper appears to present only 1 case study. "
                            "Add a second structure (different height, material, or soil class) "
                            "or explicitly label cases as 'Structure A/B' or 'Case 1/2'."
                        )
                    })
                else:
                    issues.append({
                        "severity": "OK",
                        "check": "multi_structure",
                        "msg": "Multi-structure requirement met (2+ structures/cases detected)"
                    })

    return issues


def print_report(draft_path: Path, issues: list[dict]):
    """Print formatted validation report."""
    print(f"\n{'='*60}")
    print(f"  VALIDATION: {draft_path.name}")
    print(f"{'='*60}")

    severity_icons = {"ERROR": "[X]", "WARN": "[!]", "INFO": "[i]", "OK": "[+]"}
    errors = sum(1 for i in issues if i["severity"] == "ERROR")
    warns = sum(1 for i in issues if i["severity"] == "WARN")

    for issue in issues:
        icon = severity_icons.get(issue["severity"], "[ ]")
        print(f"  {icon} [{issue['check']:14s}] {issue['msg']}")

    print(f"{'='*60}")
    if errors:
        print(f"  RESULT: BLOCKED -- {errors} error(s), {warns} warning(s)")
    elif warns:
        print(f"  RESULT: REVIEW NEEDED -- {warns} warning(s)")
    else:
        print(f"  RESULT: READY FOR SUBMISSION")
    print(f"{'='*60}\n")

    return errors == 0


def diagnose(draft_path: Path, issues: list[dict]):
    """DAG diagnostic: map each failure to a fix action and pipeline step."""
    fix_map = {
        "ai_prose": "Rewrite flagged sentences to remove AI patterns → IMPLEMENT step",
        "data_traceability": "Configure db/manifest.yaml with data sources → DESIGN step",
        "frontmatter": "Edit draft YAML header → loop back to DESIGN step",
        "ai_markers": "Add <!-- AI_Assist --> to AI-generated paragraphs → IMPLEMENT step",
        "hv_markers": "Request human validation from the researcher → VERIFY step (blocked)",
        "figures": "Run: python3 tools/plot_figures.py --domain X → IMPLEMENT step",
        "bibliography": "Run: python3 tools/generate_bibtex.py → IMPLEMENT step",
        "word_count": "Expand sections with scientific_narrator.py → IMPLEMENT step",
        "structure": "Add missing IMRaD sections → DESIGN step",
        "completeness": "Resolve all TODO markers → IMPLEMENT step",
        "journal_spec": "Review .agent/specs/journal_specs.yaml gates → SPEC step",
        "abstract_length": "Shorten abstract to meet journal word limit → IMPLEMENT step",
        "semicolon_density": "Split semicolons into separate sentences → IMPLEMENT step",
        "normative_framework": "Cite Eurocode 8, ASCE 7-22, ACI 318-19 in Methodology/Introduction → IMPLEMENT",
        "multi_structure": "Add second structure/specimen (Case A/B or Structure 1/2) → DESIGN step",
        "style_gate": "Run style_calibration.py before writing batches → Pre-Batch step",
        "stats_citation": "Cite p-values from cv_results.json in Results section (e.g., 'Mann-Whitney U test yielded p < 0.05') → IMPLEMENT step",
        "pipeline_state": "Set 'status: archived' in the other paper's frontmatter, then re-run → ARCHIVE step",
    }

    errors_and_warns = [i for i in issues if i["severity"] in ("ERROR", "WARN")]
    if not errors_and_warns:
        print("\n  [DAG] All checks passed. Ready for next step: compile PDF")
        return

    print(f"\n{'='*60}")
    print(f"  DAG DIAGNOSTIC: {draft_path.name}")
    print(f"{'='*60}")
    print(f"  Failures: {len(errors_and_warns)} — Loop back required\n")

    for issue in errors_and_warns:
        fix = fix_map.get(issue["check"], "Manual investigation needed")
        print(f"  [{issue['severity']:5s}] {issue['msg']}")
        print(f"         FIX → {fix}\n")

    # Determine furthest loop-back step
    steps = {"SPEC": 0, "DESIGN": 1, "IMPLEMENT": 2, "VERIFY": 3}
    furthest = "VERIFY"
    for issue in errors_and_warns:
        fix = fix_map.get(issue["check"], "")
        for step in ("SPEC", "DESIGN", "IMPLEMENT"):
            if step in fix and steps.get(step, 99) < steps.get(furthest, 99):
                furthest = step

    print(f"  LOOP BACK TO: {furthest} step")
    print(f"{'='*60}\n")


def main():
    diagnose_mode = "--diagnose" in sys.argv
    suggest_mode = "--suggest-trace" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not args:
        print("Usage: python3 tools/validate_submission.py <draft.md> [--diagnose] [--suggest-trace]")
        sys.exit(1)

    if suggest_mode:
        for arg in args:
            path = Path(arg)
            if path.exists():
                suggest_traceability(path)
        sys.exit(0)

    all_pass = True
    for arg in args:
        path = Path(arg)
        if not path.exists():
            print(f"[ERROR] File not found: {path}")
            all_pass = False
            continue
        issues = validate_draft(path)
        passed = print_report(path, issues)
        if diagnose_mode:
            diagnose(path, issues)
        if not passed:
            all_pass = False

    sys.exit(0 if all_pass else 1)



def suggest_traceability(draft_path: Path):
    """Scan a draft and suggest traceability entries for manifest.yaml.

    Looks for RSN numbers, figure references, and quantitative claims.
    Prints suggested entries in YAML format for copy-paste into manifest.
    """
    text = draft_path.read_text(encoding="utf-8")

    # Find RSN patterns
    rsns = sorted(set(re.findall(r"RSN\s*(\d+)", text, re.IGNORECASE)))

    # Find figure patterns
    figs = sorted(set(re.findall(r"(?:Fig\.?|Figure)\s*(\d+)", text, re.IGNORECASE)))

    # Find quantitative claims (number + unit)
    claims = re.findall(
        r"(\d+\.?\d*)\s*(%|mm|cm|m/s|Hz|MPa|kPa|kN|g\b|rad|deg)", text
    )

    print(f"{'='*60}")
    print(f"  TRACEABILITY SUGGESTIONS: {draft_path.name}")
    print(f"{'='*60}")

    if rsns:
        print(f"\n  RSNs found: {', '.join('RSN' + r for r in rsns)}")
    else:
        print("\n  RSNs found: NONE — paper must reference PEER records")

    if figs:
        print(f"  Figures found: {', '.join('Fig. ' + f for f in figs)}")
    else:
        print("  Figures found: NONE")

    if claims:
        unique_claims = sorted(set(f"{v} {u}" for v, u in claims))[:10]
        print(f"  Quantitative claims: {', '.join(unique_claims)}")

    print(f"\n  Suggested YAML for db/manifest.yaml traceability section:\n")
    print("  traceability:")
    for i, rsn in enumerate(rsns):
        fig = figs[i] if i < len(figs) else "X"
        print(f'    - claim: "[VERIFY] Result from RSN{rsn}"')
        print(f'      figure: "Fig. {fig}"')
        print(f"      data_file: \"\"")
        print(f'      source: "RSN{rsn}"')
    if not rsns:
        print('    - claim: "[FILL] No RSNs detected — add manually"')
        print('      figure: ""')
        print('      data_file: ""')
        print('      source: ""')

    print(f"\n{'='*60}")

if __name__ == "__main__":
    main()
