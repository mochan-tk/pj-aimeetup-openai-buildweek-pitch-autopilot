# Copilot Repository Instructions

Trust these instructions. Search the codebase only when something here is
missing or demonstrably wrong — and when that happens, propose a fix to this
file as part of your PR (see the retro skill).

`AGENTS.md` at the repository root defines the operating protocol
(persistence rule, record-before-report, verify-before-done, unit of work,
single-writer rule, Ambiguity rule). It applies to you in full. This file adds the operational
details Copilot needs to work efficiently in this repository.

## Project: Pitch Autopilot

A one-command CLI that turns a repository's development evidence (git log,
README, sources, screenshots) into a bilingual (Japanese/English) 6-slide
pitch deck and 90-second talk scripts:

```
pitch build <repo path> --langs ja,en -o out/
```

Authoritative specs — read before designing anything:
- `docs/agreements/requirements.md` — REQ-001..013 (MVP), REQ-101..102 (stretch)
- `docs/agreements/adr-0001-architecture.md` — 3-stage pipeline and the two
  frozen JSON contracts (`context.json`, `SlideDeck`). Do not change a
  contract without `needs:replan`.

## Repository layout

- `collect.py` — stage 1: repo facts → `out/context.json` (caps: 50 commits,
  200 lines/file, 10 files).
- `generate.py` — stage 2: OpenAI Structured Outputs, fixed SlideDeck
  schema; pure function `generate(context, langs)`; 1 retry on schema
  violation.
- `render.py` — stage 3: SlideDeck JSON → Marp `slides.md` → `deck.html`
  via npx.
- `theme/pitch.css` — custom Marp theme (`/* @theme pitch */`, Noto Sans JP,
  `.en` class renders English smaller).
- `cli.py`, `pitch` — CLI entry point and executable shim.
- `tests/` — offline unit tests (mocked API; no network).
- `assets/screenshots/` — humans drop demo screenshots here (optional
  input; absence triggers the text-diagram fallback).
- `out/` — generated artifacts; git-ignored, never committed.
- `docs/agreements/` — reviewed requirements + ADR.
- `.github/skills/` — procedures. `.github/instructions/` — path-scoped rules.
- `.github/agents/` — role definitions (orchestrator, planner, reviewer).

## Environment setup and validated commands

Run steps in this order. Do not improvise alternative commands when these work.

1. Python 3.11+ (`python3 --version`). No virtualenv ceremony needed today.
2. `pip install -r requirements.txt` — the only dependency is `openai`.
3. `export OPENAI_API_KEY=...` — required by the generate stage. In the
   Codex cloud environment this arrives as a configured secret; do not
   hardcode or echo it.
4. `npx @marp-team/marp-cli --version` — Marp needs no install; npx runs it
   one-shot (first invocation downloads, ~30 s).
5. Stage self-tests (each module runs standalone; see the ADR contracts):
   - `python3 collect.py . -o out/context.json`
   - `python3 -m unittest discover tests` — offline, no API key needed.
6. Full pipeline self-test (the repository is its own test fixture):
   `./pitch build . --langs ja,en -o out/` then
   `test -f out/slides.md && test -f out/deck.html`.

### Cloud vs local verification split (binding)

- **Codex cloud container: no Chrome, no CJK fonts.** Definition of done in
  the cloud = `out/slides.md` and `out/deck.html` generated and non-empty.
  Never attempt or promise `deck.pdf` in the cloud: PDF export is a
  headless-browser print and Japanese renders as tofu without CJK fonts.
- **Local Mac (human):** `npx @marp-team/marp-cli out/slides.md -o out/deck.pdf`
  (same command, `.pptx` for PowerPoint) + visual check that Japanese
  renders. Note: Marp PPTX is image-per-slide by default (not editable);
  PDF is the primary distribution format.

### Hackathon overrides (2026-07-18, one-day event)

- Flat Task issues, no Epics. Retro, CODEOWNERS approval waits, and the
  full evidence-table ceremony are suspended for today. Verify-before-done
  still applies: paste the Verification commands' actual output into the PR
  body (a pasted log is acceptable evidence today).
- `ci.yml` and `copilot-setup-steps.yml` still carry CUSTOMIZE markers —
  intentionally skipped for hackathon (the tuning check in CI is
  warning-only and does not fail the build). The firmware area instruction
  file was removed at onboarding (no firmware paths in this project).
- The ADR lives flat at `docs/agreements/adr-0001-architecture.md` (no
  `adr/` subfolder today).

## Working a Task issue

The Task issue body is your work order. It follows
`.github/ISSUE_TEMPLATE/ai-task.yml` and contains: Objective, Context &
references, Acceptance criteria, Out of scope, File ownership, Verification,
and Routing. Read all of it before writing code.

1. Comment on the issue that you are starting (one line is enough).
2. Work on branch `task/<issue-number>-<short-slug>`. Touch only paths listed
   under **File ownership**.
3. Keep the PR description synchronized with reality: for each acceptance
   criterion, paste the verification command output that proves it.
4. Run every command in the issue's **Verification** section before marking the
   PR ready. If a command fails, fix the cause or report the blocker — never
   delete or weaken the check.
5. If the task turns out to be materially different from its description,
   follow the Ambiguity rule in `AGENTS.md` (comment, label `needs:human` or
   `needs:replan`, stop).
6. Finish with the record-before-report comment on the issue: status, evidence,
   deviations, follow-ups (format in
   `.github/skills/session-orchestration/SKILL.md`).

## Pull request conventions

- Title: imperative mood, mirrors the Task issue title.
- Body: fill `.github/PULL_REQUEST_TEMPLATE.md`, including `Closes #<n>`;
  today a pasted verification log satisfies the Evidence section.
- Keep PRs reviewable: one Task issue per PR; if the diff exceeds roughly 400
  changed lines outside generated code, propose splitting via `needs:replan`
  instead of pushing on.

## Things that will get your PR rejected

- Diff touches paths outside the issue's File ownership section.
- Acceptance criteria without evidence, or verification commands not run.
- Committed `out/` artifacts, secrets, tokens, or credentials.
- A cloud PR that claims PDF/PPTX verification (local-only by design).
- Deck or script content naming features absent from `context.json`
  (REQ-006 — fact grounding is the product).
- Modified CI workflows, rulesets, or checks without an explicit mandate.
- Non-English persistent artifacts (code comments, docs, commit messages).
