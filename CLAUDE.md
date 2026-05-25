# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan at:
`specs/001-widget-auth-admin-cicd/plan.md`
<!-- SPECKIT END -->

## Project

Spec Kit — a structured SDD workflow that drives feature development through **specify → plan → tasks → implement** using Claude as the AI integration. SpecKit version: 0.8.14.dev0.

## Environment

- **Shell**: PowerShell 5.1 (Windows 11). Use PowerShell syntax in all Bash/shell commands — `$env:VAR`, backtick line continuation, no `&&` operator.
- **Script format**: PowerShell (configured in `.specify/init-options.json`).
- **Context file**: this file (`CLAUDE.md`).

## Workflow — SDD Cycle

Run these phases in order. **IMPORTANT: run `/clear` between phases** — each phase reads many files and context pollution between phases causes mistakes.

### 1. Specify
```
/speckit-specify <natural language description>
```
Creates a numbered directory under `specs/` with `spec.md`. Verification: the spec must contain user scenarios (P1/P2/P3), functional requirements (FR-001+), and measurable success criteria before proceeding.

### 2. Clarify _(if spec has gaps)_
```
/speckit-clarify
```
Asks up to 5 targeted questions and encodes answers back into `spec.md`. Skip if spec is already unambiguous.

### 3. Plan
```
/speckit-plan
```
**Before running**: enter plan mode (click the plan mode toggle or use `Ctrl+G` to open the plan in your editor) and read `spec.md` to understand constraints. Generates `research.md`, `data-model.md`, `contracts/`, and `quickstart.md` inside the feature directory. Verification: confirm all constitution gates pass before proceeding.

### 4. Tasks
```
/speckit-tasks
```
Generates a dependency-ordered `tasks.md`. Verification: tasks must be grouped by user story, have explicit dependency ordering, and identify which tasks can run in parallel.

### 5. Analyze _(cross-artifact check)_
```
/speckit-analyze
```
Non-destructive consistency check across `spec.md`, `plan.md`, and `tasks.md`. Run before implementation if any artifact was edited manually.

### 6. Implement
```
/speckit-implement
```
Executes every task in `tasks.md` in order. Verification: after each task group, run any test commands specified in the plan's `quickstart.md`.

## Branch Naming

**IMPORTANT**: branches follow sequential numbering — `NNN-short-feature-name` (e.g., `001-oauth-login`). Gitflow prefixes (`feature/`, `bugfix/`) are stripped when resolving feature directories. The `/speckit-git-validate` skill enforces this. Never create branches with free-form names.

## Constitution

Before making any architectural decision, read `.specify/memory/constitution.md`. It defines core principles and constraints that govern all implementation choices. The plan phase has an explicit constitution check gate — do not bypass it.

**Note**: the constitution is currently an unfilled template. Run `/speckit-constitution` to populate it with real project principles before starting the first feature.

## Git Hooks

Git operations are automated via `.specify/extensions.yml` hooks:
- `before_specify` → creates a feature branch
- `after_*` → auto-commits changes

These run automatically. Do not manually create feature branches or commit after speckit commands — the hooks handle it.

## Design Consistency

The `/design-consistency-orchestrator` skill auto-activates when working on UI files (`*.tsx`, `*.jsx`, `*.css`, `*.scss`, `**/components/**`, `**/pages/**`, etc.). It enforces: reuse before creating, check similar pages first, explain modified files. Invoke directly with `/design-consistency-orchestrator <component>` for targeted checks.

## Context Management

- Run `/clear` between unrelated tasks and between major workflow phases.
- Use subagents for codebase investigation (`"use a subagent to investigate X"`) to keep the main context clean for implementation.
- If Claude asks questions already answered here, the file may be drifting too long — prune it.
- Customize compaction with: `"When compacting, preserve the current feature directory path, active task list, and any failing test commands."`
