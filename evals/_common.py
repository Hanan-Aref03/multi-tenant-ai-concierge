"""Shared utilities for all CI eval gate scripts.

Exit codes:
  0 = gate passed
  1 = gate failed (metric below threshold)
  2 = configuration error (missing file, malformed YAML, missing key)

Stdout: one JSON line with gate result.
"""
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml


def is_stub_mode() -> bool:
    return "--stub" in sys.argv or os.environ.get("CI_STUB_MODE", "").lower() == "true"


def load_thresholds(path: str) -> dict:
    """Load eval_thresholds.yaml. Exits with code 2 on any error."""
    p = Path(path)
    if not p.exists():
        _config_error(f"Threshold file not found: {path}")
    try:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        _config_error(f"Malformed YAML in {path}: {e}")
    if not isinstance(data, dict):
        _config_error(f"Threshold file must be a YAML mapping: {path}")
    return data


def get_threshold(thresholds: dict, *keys: str) -> Any:
    """Navigate nested threshold dict. Exits with code 2 if key is missing."""
    node = thresholds
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            _config_error(f"Missing threshold key: {'.'.join(keys)}")
        node = node[key]
    return node


def report_and_exit(gate: str, metric: str, value: float, threshold: float, comparison: str) -> None:
    passed = _compare(value, threshold, comparison)
    result = {
        "gate": gate,
        "metric": metric,
        "value": round(value, 4),
        "threshold": threshold,
        "comparison": comparison,
        "passed": passed,
    }
    print(json.dumps(result), flush=True)
    sys.exit(0 if passed else 1)


def report_multi_and_exit(gate: str, metrics: list[dict]) -> None:
    all_passed = all(m["passed"] for m in metrics)
    result = {"gate": gate, "metrics": metrics, "passed": all_passed}
    print(json.dumps(result), flush=True)
    sys.exit(0 if all_passed else 1)


def _compare(value: float, threshold: float, comparison: str) -> bool:
    ops = {">=": value >= threshold, "==": value == threshold, "<=": value <= threshold, ">": value > threshold, "<": value < threshold}
    if comparison not in ops:
        _config_error(f"Unknown comparison operator: {comparison!r}")
    return ops[comparison]


def _config_error(msg: str) -> None:
    print(json.dumps({"error": msg, "exit_code": 2}), flush=True)
    sys.exit(2)
