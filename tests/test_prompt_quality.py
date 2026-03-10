#!/usr/bin/env python3
"""Evaluation harness for AutoResearch Room 2: sub-agent prompt quality scoring."""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / ".agent" / "prompts"

PROMPT_FILES = {
    "verifier": "verifier.md",
    "physical_critic": "physical_critic.md",
    "bibliography_agent": "bibliography_agent.md",
    "figure_agent": "figure_agent.md",
    "reviewer_simulator": "reviewer_simulator.md",
}

SIGNALS = [
    ("identity", 0.08, lambda t: bool(re.search(r"##\s*(Identidad|Identity)", t) or re.search(r"(?i)(eres el|you are the|rol:|role:)", t))),
    ("activation", 0.07, lambda t: bool(re.search(r"##\s*(Condiciones de Activaci[oó]n|Activation)", t) and re.search(r"^\s*[-*]\s+", t, re.M))),
    ("engram_protocol", 0.10, lambda t: bool(re.search(r"mem_search\(", t) and re.search(r"mem_save\(", t))),
    ("numbered_steps", 0.10, lambda t: bool(re.search(r"###\s*(PASO|Step)\s*\d", t, re.I))),
    ("ssot_refs", 0.10, lambda t: bool(re.search(r"(config/)?params\.yaml", t))),
    ("manifest_refs", 0.08, lambda t: bool(re.search(r"(manifest\.yaml|COMPUTE_MANIFEST)", t))),
    ("output_format", 0.10, lambda t: bool(re.search(r"(REPORTE|VEREDICTO|```)", t) and re.search(r"[|].*[|].*[|]", t))),
    ("anti_patterns", 0.07, lambda t: bool(re.search(r"(?i)(anti.?pattern|prohibi|NUNCA|never\b|NO\s+hacer)", t))),
    ("quantitative", 0.08, lambda t: bool(re.search(r"(<\s*\d|>\s*\d|[≥≤]\s*\d|\d+\s*%)", t))),
    ("tool_refs", 0.05, lambda t: bool(re.search(r"tools/\w+\.py", t) or re.search(r"\.agent/skills/\w+\.md", t))),
    ("fail_fast", 0.07, lambda t: bool(re.search(r"(?i)(bloqu|block|gate|abort|fail.?fast|antes de continuar)", t))),
    ("risk_aware", 0.05, lambda t: bool(re.search(r'mem_search\(\s*["\']risk:', t))),
    ("engram_cycle", 0.05, lambda t: bool(re.search(r'mem_search\(\s*["\']task:', t) and re.search(r'mem_save\(\s*["\']result:', t))),
]


def load_prompts() -> dict[str, str]:
    """Load prompt files, returning empty string for missing ones."""
    result = {}
    for name, filename in PROMPT_FILES.items():
        path = PROMPTS_DIR / filename
        try:
            result[name] = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            result[name] = ""
    return result


def score_prompt(text: str) -> dict[str, float]:
    """Score a single prompt against all signals. Returns {signal_name: 0.0|1.0}."""
    return {name: 1.0 if check(text) else 0.0 for name, _, check in SIGNALS}


def compute_weighted_score(signal_scores: dict[str, float]) -> float:
    """Compute weighted score for a single prompt."""
    weight_map = {name: weight for name, weight, _ in SIGNALS}
    return sum(signal_scores[name] * weight_map[name] for name in signal_scores)


def evaluate_all() -> dict:
    """Run full evaluation across all prompts."""
    prompts = load_prompts()
    max_weight = sum(w for _, w, _ in SIGNALS)
    prompt_details = {}
    signal_coverage = {name: 0 for name, _, _ in SIGNALS}

    for pname, text in prompts.items():
        scores = score_prompt(text)
        prompt_details[pname] = round(compute_weighted_score(scores) / max_weight, 2)
        for sig, val in scores.items():
            signal_coverage[sig] += int(val)

    total = len(prompts)
    overall = sum(prompt_details.values()) / total if total else 0.0
    weakest_prompt = min(prompt_details, key=prompt_details.get) if prompt_details else ""
    weakest_signal = min(signal_coverage, key=signal_coverage.get) if signal_coverage else ""

    return {
        "compliance_score": round(overall, 2),
        "details": {
            "prompt_scores": prompt_details,
            "signal_coverage": signal_coverage,
            "total_prompts": total,
            "weakest_prompt": weakest_prompt,
            "weakest_signal": weakest_signal,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPromptQuality(unittest.TestCase):
    """Unit tests for prompt quality evaluation."""

    @classmethod
    def setUpClass(cls):
        cls.prompts = load_prompts()
        cls.results = evaluate_all()

    def test_all_prompts_loaded(self):
        loaded = [n for n, t in self.prompts.items() if t]
        self.assertGreater(len(loaded), 0, "No prompt files found")

    def test_compliance_score_range(self):
        score = self.results["compliance_score"]
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_prompt_scores_range(self):
        for name, score in self.results["details"]["prompt_scores"].items():
            with self.subTest(prompt=name):
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 1.0)

    def test_signal_coverage_range(self):
        total = self.results["details"]["total_prompts"]
        for sig, count in self.results["details"]["signal_coverage"].items():
            with self.subTest(signal=sig):
                self.assertGreaterEqual(count, 0)
                self.assertLessEqual(count, total)

    def test_identity_present_in_loaded_prompts(self):
        for name, text in self.prompts.items():
            if not text:
                continue
            scores = score_prompt(text)
            with self.subTest(prompt=name):
                self.assertEqual(scores["identity"], 1.0, f"{name} missing identity section")

    def test_engram_protocol_coverage(self):
        covered = self.results["details"]["signal_coverage"]["engram_protocol"]
        loaded = sum(1 for t in self.prompts.values() if t)
        self.assertGreaterEqual(covered, loaded // 2, "Less than half of prompts have Engram protocol")

    def test_weights_sum_to_one(self):
        total = sum(w for _, w, _ in SIGNALS)
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_score_empty_prompt(self):
        scores = score_prompt("")
        self.assertTrue(all(v == 0.0 for v in scores.values()))

    def test_weakest_fields_present(self):
        self.assertIn("weakest_prompt", self.results["details"])
        self.assertIn("weakest_signal", self.results["details"])

    def test_json_serializable(self):
        try:
            json.dumps(self.results)
        except (TypeError, ValueError) as exc:
            self.fail(f"Results not JSON-serializable: {exc}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--score" in sys.argv:
        print(json.dumps(evaluate_all(), indent=2))
    else:
        unittest.main(argv=[sys.argv[0]])
