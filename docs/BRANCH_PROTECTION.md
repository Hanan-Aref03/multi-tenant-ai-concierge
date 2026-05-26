# GitHub Branch Protection Checklist

Use this checklist in GitHub repository settings to keep `main` and `dev` safe.

## Protect `main`

- [ ] Require a pull request before merging
- [ ] Require at least 2 approvals
- [ ] Dismiss stale approvals when new commits are pushed
- [ ] Require conversation resolution before merging
- [ ] Require status checks to pass before merging
- [ ] Require branches to be up to date before merging
- [ ] Restrict who can push to `main`
- [ ] Block force pushes
- [ ] Block branch deletion
- [ ] Enable linear history if the team uses squash merges
- [ ] Optionally include administrators if you want no bypasses

Recommended required checks for `main`:

- `ci`
- `evals`
- `tests`
- `security`

## Protect `dev`

- [ ] Require a pull request before merging
- [ ] Require at least 1 approval
- [ ] Dismiss stale approvals when new commits are pushed
- [ ] Require conversation resolution before merging
- [ ] Require status checks to pass before merging
- [ ] Require branches to be up to date before merging
- [ ] Restrict who can push to `dev`
- [ ] Block force pushes
- [ ] Block branch deletion

Recommended required checks for `dev`:

- `ci`
- `tests`
- `security`

## Release Flow

- Merge feature branches into `dev`.
- Merge `dev` into `main` only when the release is ready.
- Do not bypass branch protection unless the team agrees it is an emergency.

## Emergency Rule

- If a hotfix is needed, create a dedicated hotfix branch from `main`.
- Merge the hotfix back into both `main` and `dev` after approval and verification.

