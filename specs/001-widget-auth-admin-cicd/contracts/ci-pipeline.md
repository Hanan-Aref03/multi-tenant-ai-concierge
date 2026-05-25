# CI/CD Pipeline Contract (Owner D)

**Date**: 2026-05-25
**Platform**: GitHub Actions

---

## Pipeline Structure

```
push / pull_request
  └── job: lint-typecheck
        └── (on success) job: build-images
              └── (on success) job: eval-gates (matrix)
                    ├── gate: classifier
                    ├── gate: agent-tool-selection
                    ├── gate: rag
                    ├── gate: injection-redteam
                    └── gate: redaction
              └── (on success) job: smoke-test
```

All jobs must pass. Any failure blocks merge.

---

## Eval Gate Interface Contract

Each eval gate is a standalone Python script in `evals/`. The pipeline calls:

```bash
python evals/<gate_name>.py --thresholds eval_thresholds.yaml [--stub]
```

**Exit codes**:
- `0` — gate passed (metric at or above threshold)
- `1` — gate failed (metric below threshold)
- `2` — configuration error (missing threshold key, malformed YAML)

**Stdout format** (machine-readable, one JSON line):
```json
{"gate": "classifier", "metric": "macro_f1", "value": 0.81, "threshold": 0.75, "passed": true}
```

**--stub mode**: returns the threshold value exactly, always exits `0`. Used until real artifacts exist.

---

## Threshold File Contract

File: `eval_thresholds.yaml` (committed in repo root)

Rules:
- The file MUST exist. A missing file causes all gates to exit `2`.
- A missing gate key causes that gate to exit `2` (not silently pass).
- Thresholds are bumped up (never down) once real data is available. Lowering a threshold requires a PR with justification comment.

---

## Branch Protection Contract

GitHub branch protection on `main` / `master`:
- Required status checks: `lint-typecheck`, `build-images`, `eval/classifier`, `eval/agent-tool-selection`, `eval/rag`, `eval/injection-redteam`, `eval/redaction`, `smoke-test`
- "Require branches to be up to date before merging" — enabled
- No direct push to `main`

---

## Smoke Test Contract

The smoke test job:
1. Checks out the repo fresh (no cached state)
2. Copies `.env.example` to `.env`
3. Runs `docker-compose up -d --wait` (timeout: 120 s)
4. Hits `GET /health` on the API service — expects `200`
5. Runs `docker-compose down`

If any step fails or times out → job exits `1` → merge blocked.
