# Requirements — Pitch Autopilot

One row per verifiable requirement. IDs are permanent: never reuse or
renumber; supersede instead (`Status: superseded by REQ-###`). Every `REQ`
must be provable by a command or an observable behavior.

Product in one line: a CLI that turns a repository's development evidence
(git log, README, sources, screenshots) into a bilingual (ja/en) 6-slide
pitch deck plus 90-second talk scripts.

Architecture and interface contracts: `docs/agreements/adr-0001-architecture.md`.

## MVP requirements (must hold today)

| ID | Requirement | Source | Verification hint | Status |
|---|---|---|---|---|
| REQ-001 | A single command `pitch build <repo> --langs ja,en -o out/` runs the whole pipeline (collect → generate → render) and completes in 2 minutes or less on a typical hackathon-sized repository | Brief §1, §5 | `time ./pitch build . --langs ja,en -o out/` | agreed |
| REQ-002 | The output directory contains `context.json`, `slides.md`, `deck.html`, `script_ja.md`, `script_en.md`. `deck.pdf` / `deck.pptx` come from the same Marp command (extension change) and are produced/verified on the local Mac only — never a cloud acceptance criterion | Brief §2, master plan | `test -f out/slides.md && test -f out/deck.html && test -f out/script_ja.md && test -f out/script_en.md` | agreed |
| REQ-003 | The deck has exactly 6 slides in this fixed order: title / problem / solution / demo / architecture / next | Brief §2 | count `---` slide separators in `out/slides.md`; inspect SlideDeck JSON `slides[].id` | agreed |
| REQ-004 | Every slide is bilingual on one page: Japanese as the primary (large) text, English as the secondary (smaller) text below it | Brief §2 | open `out/deck.html`; theme rule `.en { font-size: … }` applied | agreed |
| REQ-005 | Talk scripts fit 90 seconds: `script_ja.md` is 300 Japanese characters or fewer; `script_en.md` is 90 words or fewer | Brief §2 | char count / `wc -w` on the script bodies | agreed |
| REQ-006 | Fact grounding: slides and scripts mention no feature or capability name that is absent from `context.json` (git log, README, sources). Hallucinated feature names are a release blocker | Brief §5 | cross-read `out/slides.md` and scripts against `out/context.json`; generation prompt carries the facts-only constraint | agreed |
| REQ-007 | The generate stage uses OpenAI Structured Outputs with a fixed JSON schema; on a schema-invalid response it retries exactly once, then exits non-zero with a readable error | Brief §7 | offline unit test with a mocked invalid response; observe exit code | agreed |
| REQ-008 | When `assets/screenshots/` is missing or empty, the demo slide automatically falls back to a text architecture diagram — no broken image links in the deck | Brief §7 | run against a repo without screenshots; `grep -c 'img' out/slides.md` shows no dangling paths | agreed |
| REQ-009 | `--langs ja` alone and `--langs en` alone both work; only the requested languages are generated and emitted (deck text and script files) | Design session | `./pitch build . --langs ja -o out_ja/` produces `script_ja.md` and no `script_en.md` | agreed |
| REQ-010 | A custom Marp theme (`theme/pitch.css`, Noto Sans JP family) is applied — the deck must not look like default Marp. Theme effort is capped at ~10 minutes | Brief §2 | `grep -q 'theme: pitch' out/slides.md`; visual check of `deck.html` | agreed |
| REQ-011 | The collect stage bounds its input: `git log --stat` capped at 50 commits + README at HEAD + first 200 lines of up to 10 key source files + `assets/screenshots/` file listing, aggregated into one `context.json` | Brief §2 | `python3 collect.py . -o out/context.json`; inspect keys and caps | agreed |
| REQ-012 | `generate(context: dict, langs: list) -> SlideDeck` is a pure function (no I/O besides the API call injected via client) covered by at least one offline unit test | Brief §8-1 | `python3 -m unittest discover tests` passes without network | agreed |
| REQ-013 | Self-hosting proof: running the tool on this repository itself produces `out/slides.md` and `out/deck.html` (cloud definition of done); Japanese renders correctly when the HTML is opened locally | Brief §5, master plan | `./pitch build . --langs ja,en -o out/` then open `out/deck.html` | agreed |

## Stretch requirements (only after REQ-001..013 hold)

| ID | Requirement | Source | Verification hint | Status |
|---|---|---|---|---|
| REQ-101 | Batch mode builds decks for multiple repositories in one invocation (today: the 3 hackathon repos); one failing repo does not stop the others | Brief §2 stretch | `python3 build_all.py <repoA> <repoB> -o out_all/` | stretch |
| REQ-102 | Automatic script-length check warns (non-fatal) when REQ-005 limits are exceeded | Brief §2 stretch | run against an over-long fixture; observe warning | stretch |

## Non-goals (today, hackathon mode)

- Gamma-like visual design, video editing, any Web UI.
- Automated demo-asset capture (Playwright screenshots, vhs terminal GIFs).
  Screenshots are placed by humans into `assets/screenshots/`.
- Editable PPTX output (`--pptx-editable` is experimental and needs
  LibreOffice); PDF is the primary distribution format, produced locally.
- Multi-model support, caching, incremental builds.
