#!/usr/bin/env python3
"""
tests/test_simulation.py -- AutoResearch Room 4: Simulation Code Quality Evaluator
Scores Python code quality via AST analysis. No runtime execution, no heavy imports.
Run:  python3 tests/test_simulation.py --score   |   pytest tests/test_simulation.py
"""
import ast, json, re, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = {
    "torture_chamber": ROOT / "src/physics/torture_chamber.py",
    "spectral_engine": ROOT / "src/physics/spectral_engine.py",
    "cross_validation": ROOT / "src/physics/cross_validation.py",
}
WEIGHTS = {"documentation": 0.25, "type_hints": 0.15, "error_handling": 0.20,
           "ssot_compliance": 0.20, "code_quality": 0.20}
TRIVIAL = {0, 1, 2, -1, 0.0, 1.0}


def _parse_file(path):
    try:
        src = path.read_text(encoding="utf-8")
        return ast.parse(src, filename=str(path)), src
    except (SyntaxError, FileNotFoundError, OSError):
        return None, None


def _get_funcs(tree):
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _func_lines(node):
    if not node.body:
        return 0
    return (node.body[-1].end_lineno or node.body[-1].lineno) - node.body[0].lineno + 1


def _has_docstring(node):
    return (node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str))


def score_documentation(tree, funcs):
    mod_doc = 1.0 if _has_docstring(tree) else 0.0
    if not funcs:
        return mod_doc * 0.3
    pct = sum(1 for f in funcs if _has_docstring(f)) / len(funcs)
    return mod_doc * 0.3 + pct * 0.7


def score_type_hints(funcs):
    if not funcs:
        return 0.0
    ret = sum(1 for f in funcs if f.returns is not None) / len(funcs)
    total, annot = 0, 0
    for f in funcs:
        for a in f.args.args:
            if a.arg == "self":
                continue
            total += 1
            annot += a.annotation is not None
    arg_pct = annot / total if total else 0.0
    return ret * 0.5 + arg_pct * 0.5


def score_error_handling(tree, source):
    tc = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Try))
    rc = len(re.findall(r'\braise\b', source))
    return min(1.0, tc * 0.3 + rc * 0.2)


def score_ssot_compliance(tree, source):
    reads = 1.0 if re.search(r'params\.yaml|load_ssot|_load_ssot', source) else 0.0
    direct = len(re.findall(r'\w+\[[\'\"][a-zA-Z_]+[\'\"]\]', source))
    safe = len(re.findall(r'\.get\(', source))
    ratio = safe / (direct + safe) if (direct + safe) else 1.0
    return reads * 0.5 + ratio * 0.5


def _count_magic(tree, funcs):
    ranges = [(f.lineno, f.end_lineno or f.lineno) for f in funcs]
    ct = 0
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            if n.value not in TRIVIAL and any(s <= getattr(n, 'lineno', 0) <= e for s, e in ranges):
                ct += 1
    return ct


def score_code_quality(tree, funcs):
    mp = max(0.0, 1.0 - _count_magic(tree, funcs) * 0.02)
    if not funcs:
        return mp * 0.5
    short = sum(1 for f in funcs if _func_lines(f) < 50) / len(funcs)
    return mp * 0.5 + short * 0.5


def score_file(path):
    tree, src = _parse_file(path)
    if tree is None:
        return {d: 0.0 for d in WEIGHTS}
    funcs = _get_funcs(tree)
    return {"documentation": score_documentation(tree, funcs),
            "type_hints": score_type_hints(funcs),
            "error_handling": score_error_handling(tree, src),
            "ssot_compliance": score_ssot_compliance(tree, src),
            "code_quality": score_code_quality(tree, funcs)}


def compute_weighted(ds):
    return sum(ds[d] * WEIGHTS[d] for d in WEIGHTS)


def run_evaluation():
    fd, fs = {}, {}
    for name, path in TARGETS.items():
        fd[name] = score_file(path)
        fs[name] = round(compute_weighted(fd[name]), 4)
    da = {d: round(sum(fd[n][d] for n in fd) / len(fd), 4) for d in WEIGHTS}
    acc = round(sum(fs.values()) / len(fs), 4) if fs else 0.0
    return {"accuracy_score": acc, "details": {
        "file_scores": fs, "dimension_averages": da, "total_files": len(TARGETS),
        "weakest_file": min(fs, key=fs.get) if fs else "",
        "weakest_dimension": min(da, key=da.get) if da else ""}}


# --- Unit tests ---

_GOOD = '"""Mod doc."""\n\ndef greet(name: str) -> str:\n    """Hi."""\n    try:\n        if not name:\n            raise ValueError("empty")\n        return f"hello {name}"\n    except Exception:\n        return "hello"\n'
_BAD = 'def f(x):\n    return x * 3.14159 + 42 + 99.9\n'


class TestASTScoring(unittest.TestCase):
    def _p(self, code):
        t = ast.parse(code); return t, _get_funcs(t), code

    def test_doc_full(self):
        t, f, _ = self._p(_GOOD)
        self.assertGreaterEqual(score_documentation(t, f), 0.9)

    def test_doc_none(self):
        t, f, _ = self._p(_BAD)
        self.assertLessEqual(score_documentation(t, f), 0.1)

    def test_hints_present(self):
        self.assertEqual(score_type_hints(self._p(_GOOD)[1]), 1.0)

    def test_hints_absent(self):
        self.assertEqual(score_type_hints(self._p(_BAD)[1]), 0.0)

    def test_error_present(self):
        t, _, s = self._p(_GOOD)
        self.assertGreater(score_error_handling(t, s), 0.0)

    def test_error_absent(self):
        t, _, s = self._p(_BAD)
        self.assertEqual(score_error_handling(t, s), 0.0)

    def test_magic_bad(self):
        t, f, _ = self._p(_BAD)
        self.assertGreaterEqual(_count_magic(t, f), 2)

    def test_magic_good(self):
        t, f, _ = self._p(_GOOD)
        self.assertEqual(_count_magic(t, f), 0)

    def test_quality_penalty(self):
        t, f, _ = self._p(_BAD)
        self.assertLess(score_code_quality(t, f), 1.0)

    def test_ssot(self):
        t, _, s = self._p('cfg = _load_ssot()\nv = cfg.get("k", 0)\n')
        self.assertGreaterEqual(score_ssot_compliance(t, s), 0.9)

    def test_parse_fail(self):
        self.assertTrue(all(v == 0.0 for v in score_file(Path("/no/file.py")).values()))

    def test_weighted(self):
        self.assertAlmostEqual(compute_weighted({d: 1.0 for d in WEIGHTS}), 1.0)

    def test_eval_structure(self):
        r = run_evaluation()
        self.assertIn("accuracy_score", r)
        d = r["details"]
        for k in ("file_scores", "dimension_averages", "total_files", "weakest_file", "weakest_dimension"):
            self.assertIn(k, d)
        self.assertEqual(d["total_files"], 3)

    def test_score_range(self):
        s = run_evaluation()["accuracy_score"]
        self.assertTrue(0.0 <= s <= 1.0)

    def test_func_length(self):
        self.assertEqual(_func_lines(self._p("def f():\n    return 1\n")[1][0]), 1)


if __name__ == "__main__":
    if "--score" in sys.argv:
        print(json.dumps(run_evaluation(), indent=2))
    else:
        unittest.main()
