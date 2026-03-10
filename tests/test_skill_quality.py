#!/usr/bin/env python3
"""Evaluation harness for AutoResearch Room 3: skill file quality scoring."""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / ".agent" / "skills"
SKILL_NAMES = [
    "paper_production", "signal_processing", "literature_review",
    "cfd_domain", "wind_domain", "norms_codes",
]
WEIGHTS = {"structure": 0.25, "content_richness": 0.35, "consistency": 0.20, "coverage": 0.20}


def _read_skill(name: str) -> str | None:
    p = SKILLS_DIR / f"{name}.md"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    return None


def _extract_frontmatter(text: str) -> str:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if m:
        return m.group(1)
    m = re.match(r"^```ya?ml\s*\n(.*?)\n```", text, re.DOTALL)
    return m.group(1) if m else ""


def _has_section(text: str, heading: str) -> bool:
    return bool(re.search(rf"^#{1,2}\s+.*{re.escape(heading)}", text, re.IGNORECASE | re.MULTILINE))


def _count_anti_pattern_items(text: str) -> int:
    m = re.search(r"(?:^#{1,2}\s+.*Anti.?Pattern.*$)(.*?)(?=^#{1,2}\s|\Z)", text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if not m:
        return 0
    return len(re.findall(r"^\s*[-*]\s+\S", m.group(1), re.MULTILINE))


def _count_numbered_steps(text: str) -> int:
    steps = re.findall(r"(?:^\s*\d+[.)]\s+|(?:Phase|Step|PASO)\s+\d)", text, re.MULTILINE | re.IGNORECASE)
    return len(steps)


def score_structure(text: str) -> tuple[float, dict]:
    fm = _extract_frontmatter(text)
    checks = {
        "frontmatter_yaml": bool(fm and re.search(r"(?:name|description|metadata)\s*:", fm)),
        "when_to_use": _has_section(text, "When to Use"),
        "critical_patterns": _has_section(text, "Critical Patterns"),
        "anti_patterns": _has_section(text, "Anti") and _count_anti_pattern_items(text) >= 3,
        "engram_section": _has_section(text, "Engram"),
        "min_headers": len(re.findall(r"^#{1,2}\s+", text, re.MULTILINE)) >= 6,
    }
    return sum(checks.values()) / len(checks), checks


def score_content_richness(text: str) -> tuple[float, dict]:
    cross_refs = len(set(re.findall(r"(?:tools/|\.agent/|src/|config/)\S+", text)))
    checks = {
        "ssot_references": bool(re.search(r"(?:config/)?params\.yaml", text)),
        "tool_list": bool(re.search(r"\|.*tool.*\||^\s*-\s+\w+\s*:", text, re.IGNORECASE | re.MULTILINE)),
        "code_blocks": len(re.findall(r"```", text)) >= 4,  # pairs -> >=2 blocks
        "formulas_thresholds": bool(re.search(r"[<>≥≤]=?\s*\d|[=]{1,2}\s*\d|\b\d+\.\d+\b", text)),
        "step_by_step": bool(re.search(r"(?:^\s*\d+[.)]\s+|(?:Phase|Step|PASO)\s+\d)", text, re.MULTILINE | re.IGNORECASE)),
        "cross_file_refs": cross_refs >= 2,
    }
    return sum(checks.values()) / len(checks), checks


def score_consistency(text: str) -> tuple[float, dict]:
    fm = _extract_frontmatter(text)
    domain_m = re.search(r"domain\s*:\s*(\S+)", fm)
    checks = {
        "domain_valid": bool(domain_m and domain_m.group(1).strip("\"'") in {"structural", "water", "air", "all"}),
        "engram_format": bool(re.search(r"mem_save\s*\(\s*[\"'](?:result:|decision:|pattern:)", text)),
        "version_exists": bool(re.search(r"version\s*:", fm)),
    }
    return sum(checks.values()) / len(checks), checks


def score_coverage(text: str) -> tuple[float, dict]:
    checks = {
        "anti_pattern_count": _count_anti_pattern_items(text) >= 4,
        "procedural_depth": _count_numbered_steps(text) >= 5,
        "word_count_adequate": len(text.split()) >= 400,
    }
    return sum(checks.values()) / len(checks), checks


def evaluate_skill(text: str) -> dict:
    s_str, _ = score_structure(text)
    s_cr, _ = score_content_richness(text)
    s_con, _ = score_consistency(text)
    s_cov, _ = score_coverage(text)
    dims = {"structure": s_str, "content_richness": s_cr, "consistency": s_con, "coverage": s_cov}
    overall = sum(dims[k] * WEIGHTS[k] for k in dims)
    return {"overall": round(overall, 4), "dimensions": {k: round(v, 4) for k, v in dims.items()}}


def run_scoring() -> dict:
    skill_scores: dict[str, float] = {}
    dim_totals: dict[str, float] = {k: 0.0 for k in WEIGHTS}
    counted = 0
    for name in SKILL_NAMES:
        text = _read_skill(name)
        if text is None:
            skill_scores[name] = 0.0
            continue
        result = evaluate_skill(text)
        skill_scores[name] = result["overall"]
        for k in dim_totals:
            dim_totals[k] += result["dimensions"][k]
        counted += 1
    n = max(counted, 1)
    dim_avgs = {k: round(v / n, 4) for k, v in dim_totals.items()}
    avg_score = round(sum(skill_scores.values()) / max(len(skill_scores), 1), 4)
    weakest_skill = min(skill_scores, key=skill_scores.get) if skill_scores else "none"
    weakest_dim = min(dim_avgs, key=dim_avgs.get) if dim_avgs else "none"
    return {
        "coverage_score": avg_score,
        "details": {
            "skill_scores": {k: round(v, 4) for k, v in skill_scores.items()},
            "dimension_averages": dim_avgs,
            "total_skills": len(SKILL_NAMES),
            "weakest_skill": weakest_skill,
            "weakest_dimension": weakest_dim,
        },
    }


# --------------- pytest / unittest ---------------

class TestSkillQuality(unittest.TestCase):
    """Integration tests: verify each skill meets minimum quality bars."""

    @classmethod
    def setUpClass(cls):
        cls.results = run_scoring()
        cls.skill_texts = {n: _read_skill(n) for n in SKILL_NAMES}

    def test_all_skill_files_exist(self):
        for name in SKILL_NAMES:
            self.assertIsNotNone(self.skill_texts[name], f"{name}.md missing from {SKILLS_DIR}")

    def test_overall_score_above_threshold(self):
        self.assertGreaterEqual(self.results["coverage_score"], 0.40,
                                "Overall coverage score too low")

    def test_no_skill_below_minimum(self):
        for name, score in self.results["details"]["skill_scores"].items():
            self.assertGreaterEqual(score, 0.20, f"{name} score {score} below minimum 0.20")

    def test_structure_dimension(self):
        for name, text in self.skill_texts.items():
            if text is None:
                continue
            s, _ = score_structure(text)
            self.assertGreaterEqual(s, 0.16, f"{name} structure score {s} too low")

    def test_content_richness_dimension(self):
        for name, text in self.skill_texts.items():
            if text is None:
                continue
            s, _ = score_content_richness(text)
            self.assertGreaterEqual(s, 0.17, f"{name} content_richness score {s} too low")

    def test_each_skill_has_frontmatter(self):
        for name, text in self.skill_texts.items():
            if text is None:
                continue
            fm = _extract_frontmatter(text)
            self.assertTrue(len(fm) > 0, f"{name} has no frontmatter")

    def test_word_count_minimum(self):
        for name, text in self.skill_texts.items():
            if text is None:
                continue
            wc = len(text.split())
            self.assertGreaterEqual(wc, 200, f"{name} has only {wc} words")


if __name__ == "__main__":
    if "--score" in sys.argv:
        print(json.dumps(run_scoring(), indent=2))
    else:
        unittest.main()
