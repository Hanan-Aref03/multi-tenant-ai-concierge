"""Classifier eval gate — macro-F1 on held-out test set.

Stub mode: returns threshold value exactly (always passes).
Real mode: loads model artifact + test set, computes macro-F1.
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
threshold = float(get_threshold(thresholds, "classifier", "threshold"))
comparison = get_threshold(thresholds, "classifier", "comparison")

if is_stub_mode() or args.stub:
    report_and_exit("classifier", "macro_f1", threshold, threshold, comparison)

# ── Real eval (runs once model artifacts land) ────────────────────────────

data_path = Path("evals/data/classifier_test.json")
if not data_path.exists():
    from _common import _config_error
    _config_error(f"Test data not found: {data_path}")

with open(data_path) as f:
    test_data = json.load(f)

labels = [d["label"] for d in test_data]
predictions = [d["prediction"] for d in test_data]

from sklearn.metrics import f1_score  # noqa: E402
macro_f1 = float(f1_score(labels, predictions, average="macro", zero_division=0))

report_and_exit("classifier", "macro_f1", macro_f1, threshold, comparison)
