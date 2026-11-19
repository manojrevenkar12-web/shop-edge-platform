"""The project's invariants, as tests (see AGENTS.md)."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = ["sep/edge", "sep/scale", "sep/slo", "sep/release", "sep/cost"]


def _imports(path: Path) -> set[str]:
    out = set()
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module)
        elif isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
    return out


def test_the_truth_stays_in_the_world():
    for d in PLATFORM:
        for f in (ROOT / d).rglob("*.py"):
            assert not {m for m in _imports(f) if m.startswith(("sep.world", "sep.sim"))}, f


def test_the_world_does_not_read_the_platforms_settings():
    for f in (ROOT / "sep/world").rglob("*.py"):
        text = f.read_text()
        assert not re.search(r'load\("(platform|slo|gate|value)"\)', text), f
        assert not {m for m in _imports(f) if m.startswith(("sep.edge", "sep.scale", "sep.slo", "sep.release",
                                                             "sep.cost", "sep.sim", "sep.eval"))}, f


def test_same_luck_every_draw_is_keyed():
    for f in (ROOT / "sep").rglob("*.py"):
        text = f.read_text()
        assert "np.random.default_rng(" not in text or f.name == "keyed.py", f
        assert "import random" not in text, f


def test_generated_kubernetes_rules_match():
    from sep.eval.cli import rules

    assert rules() is False, "deploy/k8s/base/slo-rules.yaml or ops/prometheus/rules.yml is out of date"
