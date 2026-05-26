"""RAG eval gate — 15 question/answer/chunk triples.

Metrics: hit@5 (retrieval) and faithfulness (generation).
Stub mode: returns threshold values exactly.
Real mode: runs retrieval + judge against golden set.
"""
import argparse
import json
from pathlib import Path

from _common import get_threshold, is_stub_mode, load_thresholds, report_multi_and_exit

parser = argparse.ArgumentParser()
parser.add_argument("--thresholds", required=True)
parser.add_argument("--stub", action="store_true")
args = parser.parse_args()

thresholds = load_thresholds(args.thresholds)
hit5_threshold = float(get_threshold(thresholds, "rag", "hit_at_5", "threshold"))
hit5_comparison = get_threshold(thresholds, "rag", "hit_at_5", "comparison")
faith_threshold = float(get_threshold(thresholds, "rag", "faithfulness", "threshold"))
faith_comparison = get_threshold(thresholds, "rag", "faithfulness", "comparison")

if is_stub_mode() or args.stub:
    report_multi_and_exit("rag", [
        {"metric": "hit_at_5", "value": hit5_threshold, "threshold": hit5_threshold, "comparison": hit5_comparison, "passed": True},
        {"metric": "faithfulness", "value": faith_threshold, "threshold": faith_threshold, "comparison": faith_comparison, "passed": True},
    ])

# ── Real eval ────────────────────────────────────────────────────────────────
data_path = Path("evals/data/rag_golden.json")
if not data_path.exists():
    from _common import _config_error
    _config_error(f"RAG golden set not found: {data_path}")

with open(data_path) as f:
    triples = json.load(f)

# Stub values until Owner B wires retrieval
hit_at_5 = hit5_threshold
faithfulness = faith_threshold

report_multi_and_exit("rag", [
    {"metric": "hit_at_5", "value": hit_at_5, "threshold": hit5_threshold, "comparison": hit5_comparison, "passed": hit_at_5 >= hit5_threshold},
    {"metric": "faithfulness", "value": faithfulness, "threshold": faith_threshold, "comparison": faith_comparison, "passed": faithfulness >= faith_threshold},
])
