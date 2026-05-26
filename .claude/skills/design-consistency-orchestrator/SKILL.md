---
name: design-consistency-orchestrator
description: Apply visual and architectural consistency rules when editing components, layouts, dashboards, styling, or any frontend file. Use when creating or modifying UI elements, reviewing design decisions, or checking visual consistency.
when_to_use: Triggered when the user asks to edit, create, or review components, pages, dashboards, layouts, forms, buttons, modals, styling, CSS, SCSS, or any frontend code. Also applies when the user asks "is this consistent with the rest of the UI?" or "what does this component look like elsewhere?"
argument-hint: "[component or page name]"
allowed-tools: Read Grep Glob
paths:
  - "**/*.css"
  - "**/*.scss"
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.html"
  - "**/components/**"
  - "**/layouts/**"
  - "**/pages/**"
  - "**/styles/**"
  - "**/dashboard/**"
  - "**/ui/**"
---

# Design Consistency Orchestrator

Use this skill for UI, layouts, dashboards, components, and styling.

## Goals
Maintain visual consistency and architectural consistency across the project.

## Rules
- Reuse existing components before creating new ones.
- Keep spacing, colors, shadows, typography, and buttons consistent.
- Check similar pages before editing.
- Avoid changing unrelated files.
- Maintain responsive design quality.
- Explain modified files after changes.
- Keep frontend and backend patterns consistent.

# Design Consistency Orchestrator

Use this skill for all UI, UX, layout, dashboard, component, and styling work.

## Core Philosophy
The UI should feel:
- modern
- natural
- elegant
- premium
- responsive
- visually balanced
- smooth without excessive effects

## Design Rules

### Visual Consistency
- Reuse existing components before creating new ones.
- Keep spacing, typography, border radius, shadows, and colors consistent.
- Avoid visual clutter.
- Maintain alignment and visual hierarchy.

### User Experience
- Interfaces should feel intuitive and effortless.
- Reduce cognitive overload.
- Prioritize readability and clean interaction flow.
- Important actions must stand out naturally.

### Aesthetics
- Prefer clean modern layouts.
- Use subtle animations and transitions.
- Avoid excessive gradients or flashy effects.
- Maintain a premium startup-quality feel.

### Components
- Buttons should feel consistent across the app.
- Cards should have consistent padding and hierarchy.
- Forms should be clean and easy to scan.
- Tables/charts should feel modern and readable.

### Responsiveness
- UI must work smoothly on desktop and mobile.
- Prevent overflow and broken layouts.
- Keep spacing adaptive.

### Dashboard Quality
- Dashboards should feel structured and calm.
- Information density should remain readable.
- Use sections/cards with clear separation.

### Before Editing
1. Inspect existing UI patterns.
2. Reuse the closest design pattern.
3. Improve consistency before adding complexity.
4. Avoid redesigning unrelated sections.

### After Changes
- Summarize modified files.
- Explain design reasoning briefly.
- Mention consistency improvements made.