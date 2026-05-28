# Contributing

This repo uses `dev` for team integration and `main` for releases.

## Branch Rules

- Never work directly on `main`.
- Branch from `dev` for normal work.
- Use a short-lived feature branch for each task.
- Open a PR back into `dev`.
- Merge `dev` into `main` only for releases.

## Suggested Branch Names

Use `<owner>/<type>-<short-description>`.

Examples:

- `hanan/feat-tenant-rls`
- `hanan/fix-isolation-policy`
- `mohammad/feat-rag-pipeline`
- `mohammad/feat-router-agent`
- `rayan/feat-guardrails`
- `rayan/test-redteam-gate`
- `ali/feat-widget-auth`
- `ali/feat-ci-pipeline`

## Before You Commit

1. Run the checks relevant to the files you changed.
2. Fix formatting, lint, type, test, or eval failures.
3. Review the diff for accidental edits.
4. Confirm no secrets or machine-specific files are staged.
5. Keep each commit focused on one task.

## Before You Push

1. Re-run the relevant checks for the whole branch.
2. For cross-team work, run `powershell -ExecutionPolicy Bypass -File scripts/run_team_checks.ps1`.
3. Rebase or merge the latest `dev` if it moved.
4. Make sure your branch is clean and ready for review.
5. Push only after the branch is green for its scope.

## Required Work Habits

- Every meaningful change should have tests or evals where applicable.
- Security-related changes should include a verification step.
- Do not skip review just because the change is small.
- Do not merge if CI is red.

## PR Checklist

- [ ] Branch name follows the owner/type pattern
- [ ] Scope is narrow and easy to review
- [ ] Tests or evals were run before push
- [ ] No secrets or accidental files are included
- [ ] CI is green
- [ ] At least one reviewer approved
- [ ] The branch was merged into `dev`, not `main`

## Escalation

If you are unsure whether a change belongs in `dev` or `main`, ask before merging.
