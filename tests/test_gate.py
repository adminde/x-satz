import importlib.util
from pathlib import Path

import pytest

GATE = Path(__file__).parents[1] / "tools" / "gates" / "verify.py"


@pytest.fixture(scope="module")
def gate():
    spec = importlib.util.spec_from_file_location("verify", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_green_is_green(gate):
    assert gate.overall(["green", "green"], strict=False) == gate.GREEN


def test_red_wins_over_everything(gate):
    assert gate.overall(["green", "environment error", "red"], strict=False) == gate.RED


def test_environment_error_without_red(gate):
    assert gate.overall(["green", "environment error"], strict=False) == gate.ENV


def test_not_checked_is_never_silent(gate):
    results = [{"stage": "pytest", "result": "green"}, {"stage": "render", "result": "not checked"}]
    code = gate.overall([r["result"] for r in results], strict=False)
    assert code == gate.GREEN
    assert gate.summary(results, code) == "GREEN (1 stage not checked: render)"


def test_strict_turns_not_checked_into_red(gate):
    assert gate.overall(["green", "not checked"], strict=True) == gate.RED
