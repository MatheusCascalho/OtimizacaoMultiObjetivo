---
name: paretolab-ui
description: 'Use when designing, implementing, or reviewing ParetoLab frontend screens, visual styles, charts, tables, or interactions. Applies the ParetoLab identity and provides a focused implementation and validation workflow.'
argument-hint: 'Describe the screen, interaction, or visual change'
---

# ParetoLab Interface Workflow

Use this workflow for feature work in `frontend/`, especially the dashboard and mockups.

## 1. Ground the change

- Read `.github/instructions/paretolab-frontend.instructions.md` and `frontend/mockups/README.md`.
- Inspect the specific page, component, style, or interaction being changed, along with its nearest related implementation.
- Identify the user task and the smallest UI surface that supports it. Keep the interface oriented around exploring instances, comparing objectives, and interpreting solutions.

## 2. Design and implement

- Preserve the ParetoLab research-workspace identity: light paper surfaces, deep green structure, coral/blue objective distinction, quiet yellow emphasis, and restrained scientific typography.
- Make data hierarchy visible through alignment, labels, units, and chart/table relationships; do not use color as the only way to distinguish data.
- Follow the existing vanilla HTML/CSS/JavaScript stack and reuse its design tokens and interaction patterns.
- Include loading, empty, error, and success states when the changed workflow needs them. Mark sample results and nonfunctional backend behavior as illustrative.
- Ensure controls have a clear label and keyboard-accessible behavior; preserve responsive layout and reduced-motion preferences.

## 3. Validate the changed behavior

- Run the narrowest available syntax, lint, or test check for the changed files.
- For UI changes, view the interface at a narrow mobile width and a desktop width; check that labels fit and controls do not overlap.
- Exercise the changed interaction, including keyboard use where applicable.
- For the current static mockup, use `docker compose up --build` and inspect `http://localhost:8080`. Do not claim API, database, or solver integration unless it exists in the repository.

## Completion

Summarize the user-visible change and the checks performed. Call out any visual or browser checks that could not be run.