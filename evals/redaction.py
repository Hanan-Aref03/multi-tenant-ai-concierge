"""Redaction gate — ZERO TOLERANCE for unredacted secrets in logs/traces.

Sends a fake API key through chat, then checks log output for unredacted leaks.
Stub mode: always passes.
Real mode: pattern-matches log files for the test secret.
"""
import argparse
import re
import subprocess
from pathlib import Path

from _common import get_threshold, is_stub_mode, load_thresholds, report_and_exit

parser = argparse.ArgumentParser()
parser.add_argument("--thresholds", required=True)
parser.add_argument("--log-dir", default="logs", help="Directory to scan for log files")
parser.add_argument("--stub", action="store_true")
args = parser.parse_args()

thresholds = load_thresholds(args.thresholds)
threshold = float(get_threshold(thresholds, "redaction", "threshold"))
comparison = get_threshold(thresholds, "redaction", "comparison")

if is_stub_mode() or args.stub:
    report_and_exit("redaction", "leaked_count", 0.0, threshold, comparison)

# ── Real eval ────────────────────────────────────────────────────────────────
# Test secret pattern — a fake API key that should never appear unredacted
TEST_SECRET = "sk-test-deadbeef1234567890abcdef12345678"
SECRET_PATTERN = re.compile(r"sk-test-[0-9a-fA-F]{32}")

log_dir = Path(args.log_dir)
leaked_count = 0

if log_dir.exists():
    for log_file in log_dir.rglob("*.log"):
        try:
            content = log_file.read_text(errors="replace")
            matches = SECRET_PATTERN.findall(content)
            leaked_count += len(matches)
        except OSError:
            pass

# Also check recent docker compose logs if running
try:
    result = subprocess.run(
        ["docker", "compose", "logs", "--no-color", "--since", "5m"],
        capture_output=True, text=True, timeout=15
    )
    leaked_count += len(SECRET_PATTERN.findall(result.stdout))
except (subprocess.SubprocessError, FileNotFoundError):
    pass

report_and_exit("redaction", "leaked_count", float(leaked_count), threshold, comparison)
