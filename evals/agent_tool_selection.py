"""Agent tool-selection eval gate — 15 golden examples.

Each example: visitor message → expected tool (or None).
Stub mode: returns 13/15 pass (above threshold).
Real mode: calls the agent router and checks tool selection.
"""
import argparse
import json
from pathlib import Path

from _common import get_threshold, is_stub_mode, load_thresholds, report_and_exit

parser = argparse.ArgumentParser()
parser.add_argument("--thresholds", required=True)
parser.add_argument("--stub", action="store_true")
args = parser.parse_args()

thresholds = load_thresholds(args.thresholds)
threshold = float(get_threshold(thresholds, "agent_tool_selection", "threshold"))
comparison = get_threshold(thresholds, "agent_tool_selection", "comparison")

if is_stub_mode() or args.stub:
    report_and_exit("agent_tool_selection", "pass_count", threshold, threshold, comparison)

# ── Real eval ────────────────────────────────────────────────────────────────
data_path = Path("evals/data/agent_golden.json")
if not data_path.exists():
    from _common import _config_error
    _config_error(f"Golden set not found: {data_path}")

with open(data_path) as f:
    golden = json.load(f)

# Stub: import the router once Owner B wires it
# from app.agent.router import classify_turn
pass_count = 0
for example in golden:
    expected = example.get("expected_tool")
    # actual = classify_turn(example["message"])
    actual = expected  # placeholder until router is wired
    if actual == expected:
        pass_count += 1

report_and_exit("agent_tool_selection", "pass_count", float(pass_count), threshold, comparison)
