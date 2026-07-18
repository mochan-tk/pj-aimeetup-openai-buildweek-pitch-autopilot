# ADR-0001: Three-stage pipeline — collect / generate / render (Marp)

- **Status:** accepted
- **Date:** 2026-07-18
- **Supersedes:** none

Note: hackathon mode keeps this ADR flat at
`docs/agreements/adr-0001-architecture.md` (the scaffold's `adr/` subfolder
convention is intentionally not used today).

## Context

- One-day hackathon (build window 13:30–16:30). The tool must generate its
  own presentation at 15:00 (dry run, deck_v1) and 15:45 (production run,
  v2) — see the operational plan. Reliability beats features.
- Input is development evidence (git history, README, sources, screenshots),
  not a free prompt; output is a bilingual 6-slide deck + 90-second scripts
  (REQ-001..013 in `docs/agreements/requirements.md`).
- Implementation is delegated to the Codex cloud agent, whose container has
  **no Chrome and no CJK fonts**; the operator's local Mac has both.
- Four work items must run as parallel cloud tasks with disjoint file
  ownership (AGENTS.md §5), so module boundaries and data contracts must be
  frozen up front.

## Decision

Build a Python 3.11 CLI composed of three standalone stages joined by two
frozen JSON contracts. Sole Python dependency: `openai`. Marp is executed
via `npx @marp-team/marp-cli` (no install step).

```
[target repo] → collect.py → context.json
                    → generate.py (Azure OpenAI Structured Outputs) → SlideDeck JSON
                        → render.py + theme/pitch.css → slides.md
                            → npx @marp-team/marp-cli → deck.html
                               (local Mac only: deck.pdf / deck.pptx)
cli.py / ./pitch  = thin orchestrator: pitch build <repo> --langs ja,en -o out/
```

### Stage 1 — collect (`collect.py`)

Gathers facts only, with hard caps so the LLM context stays bounded:
`git log --stat` newest-first, max 50 commits; README at HEAD; first 200
lines of up to 10 key source files (extension allowlist, most recently
modified first); file listing of `assets/screenshots/` (empty list when
absent). Emits `context.json`. Rationale: caps make cost and latency
predictable (REQ-001) and the facts-only input is what prevents inflated
decks (REQ-006).

### Stage 2 — generate (`generate.py`)

One Azure OpenAI API call using **Structured Outputs with a fixed JSON
schema** (strict mode), wrapped as a pure function
`generate(context: dict, langs: list) -> SlideDeck`. On a schema-invalid
response: retry exactly once, then fail non-zero (REQ-007). The system
prompt forbids naming features absent from the context (REQ-006) and
enforces script budgets (ja ≤ 300 chars, en ≤ 90 words, REQ-005).
Rationale: schema enforcement eliminates the classic "JSON parse roulette"
failure mode; a pure function makes the one required unit test trivial and
offline (REQ-012). The default client is `AzureOpenAI` with key-based
authentication. It reads `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`,
and application-defined `AZURE_OPENAI_DEPLOYMENT`; the deployment name is
passed as `model`. `OPENAI_API_VERSION` defaults to `2024-10-21`. Azure
resource provisioning and Microsoft Entra ID authentication are outside
this decision.

### Stage 3 — render (`render.py` + `theme/pitch.css`)

Fills a Marp Markdown template from the SlideDeck JSON and runs
`npx @marp-team/marp-cli out/slides.md -o out/deck.html --theme theme/pitch.css`.
Bilingual layout: Japanese is normal Markdown text (large); English is
wrapped in elements with class `en`, which the theme renders smaller and
muted. The theme declares `/* @theme pitch */`, sets Noto Sans JP with
system-font fallbacks, and is referenced from the slide front matter
(`theme: pitch`). Theme effort is capped at ~10 minutes (REQ-010). If the
demo slide has no screenshot, it renders `arch_text` (a fenced text
architecture diagram) instead of an image (REQ-008).

### Why Marp (facts we commit to stating accurately)

- Marp CLI runs as a one-shot `npx` command — no project install, no
  Playwright download. This is the actual advantage over Slidev, whose
  export path requires an additional Playwright installation.
- **PDF export requires a local browser** (Chrome/Edge); it is a headless
  browser print.
- **Marp's PPTX output is, by default, one raster image per slide (not
  editable)**; the editable variant is the experimental `--pptx-editable`
  flag and additionally requires LibreOffice. We therefore treat PDF as the
  primary distribution format and mention PPTX honestly, if at all.
- In containers without CJK fonts, browser-rendered PDF turns Japanese into
  tofu (`fonts-noto-cjk` would be needed). Consequence below.

### Cloud / local verification split (binding)

The Codex cloud environment has no Chrome and no CJK fonts. Therefore the
**cloud definition of done is: `out/slides.md` and `out/deck.html` generated
and non-empty** (REQ-013). PDF/PPTX rendering and the visual Japanese check
run only on the local Mac. Never write a cloud acceptance criterion that
requires `deck.pdf` (this mirrors the hardware rule in
`.github/skills/task-routing/SKILL.md`).

### Frozen interface contracts

Changing either contract is a plan change (`needs:replan`), because four
parallel tasks code against them.

`context.json` (stage 1 → stage 2):

```json
{
  "repo": {"name": "str", "path": "str", "head": "str", "collected_at": "ISO-8601"},
  "commits": [{"hash": "str", "date": "str", "subject": "str", "stat": "str"}],
  "readme": "str (empty string when absent)",
  "sources": [{"path": "str", "head": "str (first 200 lines)"}],
  "screenshots": ["relative paths under assets/screenshots/", "..."]
}
```

`SlideDeck` (stage 2 → stage 3; also the Structured Outputs schema):

```json
{
  "title": "str",
  "slides": [
    {
      "id": "title|problem|solution|demo|architecture|next  (exactly 6, this order)",
      "heading_ja": "str", "heading_en": "str",
      "bullets_ja": ["max 4"], "bullets_en": ["max 4"],
      "image": "screenshot path or null (demo slide only)",
      "arch_text": "text architecture diagram or null (fallback when image is null)"
    }
  ],
  "script_ja": "str, <= 300 Japanese characters",
  "script_en": "str, <= 90 words"
}
```

Language subsetting (REQ-009): with `--langs ja` only, `*_en` fields are
empty strings, `script_en` is empty, and render emits neither English spans
nor `script_en.md` (symmetric for `--langs en`).

## Consequences

- Easier: four disjoint parallel tasks (collect.py / generate.py +
  tests / render.py + theme / cli.py + packaging) integrate mechanically
  because both contracts are frozen here.
- Easier: every stage is runnable standalone
  (`python3 collect.py . -o out/context.json`, etc.), so each task can
  self-verify before `cli.py` exists.
- Harder: schema changes mid-hackathon are expensive — escalate with
  `needs:replan` instead of editing silently.
- Must now be true: the local Mac performs the PDF check before 15:00
  (plus one `npx @marp-team/marp-cli --version` warm-up to cache the
  download); the cloud never gates on PDF.
- Fallback ladder: schema-invalid → 1 retry → fail loudly; no screenshots →
  text architecture diagram; no Chrome → ship `deck.html` and present from
  the browser.

## References

- `docs/agreements/requirements.md` (REQ-001..013, REQ-101..102)
- Brief: `03_brief_pitch-autopilot.md` (planning folder, not in-repo)
- Marp CLI (npx one-shot; PDF needs local browser; PPTX default is
  image-per-slide, editable variant experimental + LibreOffice):
  github.com/marp-team/marp-cli
- Slidev export requires Playwright: sli.dev guide/exporting
- Azure OpenAI Structured Outputs: learn.microsoft.com/azure/ai-foundry/openai/how-to/structured-outputs
