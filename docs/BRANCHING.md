# Branching Strategy

This repository uses `dev` as the shared integration branch and `main` as the release branch.

## Branch Roles

- `main` is release-only.
- `dev` is the team integration branch.
- feature branches are short-lived and branch off `dev`.

## Non-Negotiable Rules

- Do not commit directly to `main`.
- Do not merge feature work straight into `main`.
- Use pull requests for every meaningful change.
- Keep feature branches short-lived and delete them after merge.
- Rebase or merge `dev` into your feature branch before opening a PR if `dev` moved.

## Branch Naming

Use this pattern:

`<owner>/<type>-<short-description>`

Examples:

- `hanan/feat-tenant-rls`
- `mohammad/feat-rag-pipeline`
- `rayan/feat-guardrails`
- `ali/feat-widget-auth`

## Workflow

1. Create a feature branch from `dev`.
2. Make changes on the feature branch.
3. Open a PR into `dev`.
4. Get review and CI approval.
5. Merge into `dev`.
6. When the milestone is ready, merge `dev` into `main` through a release PR.

## Suggested Types

- `feat` for new features
- `fix` for bug fixes
- `chore` for maintenance
- `docs` for documentation
- `test` for tests and evals
- `refactor` for code cleanup without behavior change

## Team Rule

If the task is part of the shared project plan, work from `dev`, not `main`.

