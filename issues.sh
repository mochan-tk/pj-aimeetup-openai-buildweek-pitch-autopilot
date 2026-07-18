#!/usr/bin/env bash
# issues.sh — file the Pitch Autopilot task issues (hackathon flat plan).
#
# Usage: run from the repository root after the design pack is committed:
#   bash issues.sh
# Requires: gh CLI authenticated against this repository.
#
# Issues #1-#3 (collect / generate / render+theme) are parallel-safe with
# disjoint file ownership; dispatch all three to Codex cloud at once
# (recommended: --attempts 2). Issue #4 (CLI integration) dispatches after
# #1-#3 merge. Issue #5 (batch mode) is a stretch goal — dispatch only if
# the 15:00 gate leaves slack.

set -euo pipefail

command -v gh >/dev/null 2>&1 || { echo "error: gh CLI not found" >&2; exit 1; }

# Labels used below (idempotent; ignore failures if they already exist).
gh label create "type:task" --color "0E8A16" \
  --description "Self-contained work order for one agent session" || true
gh label create "ai:ready" --color "1D76DB" \
  --description "Brief meets the planner quality bar; dispatchable when unblocked" || true
gh label create "exec:cloud" --color "C2E0C6" \
  --description "Route: cloud coding agent - async, parallel, draft PR" || true

new_task() { # $1 = title, $2 = body
  gh issue create --title "$1" --body "$2" \
    --label "type:task" --label "exec:cloud" --label "ai:ready"
}

BODY_COLLECT="$(cat <<'EOF'
## Objective

Implement stage 1: `collect.py` gathers this repository's development facts into a single `out/context.json` matching the frozen contract in the ADR.

## Context & references

- Epic: none (hackathon flat task list)
- Requirements: REQ-011, REQ-008 (screenshot listing part), REQ-006 (facts-only input)
- Decisions: docs/agreements/adr-0001-architecture.md (context.json contract — do not change it)
- Read first: AGENTS.md, .github/copilot-instructions.md

## Acceptance criteria

- [ ] `python3 collect.py <repo> -o <dir>/context.json` works on any git repository path; on this repository it emits valid JSON with keys `repo`, `commits`, `readme`, `sources`, `screenshots` exactly as specified in ADR-0001.
- [ ] Caps enforced: max 50 commits (newest first, each with hash/date/subject/stat), README full text at HEAD (empty string when absent), up to 10 key source files with first 200 lines each (extension allowlist, most recently modified first), `assets/screenshots/` listing (empty list when the directory is absent).
- [ ] Exposes `collect(repo_path: str) -> dict` importable by `cli.py`, plus an argparse `__main__`.
- [ ] Non-git or nonexistent path fails with a readable error and non-zero exit.

## Out of scope

- OpenAI calls, rendering, the `pitch` CLI wrapper (issues #2-#4).
- Diff bodies or full file contents (caps are the contract).

## File ownership

- collect.py

## Verification

```bash
python3 collect.py . -o out/context.json
python3 -c "import json; d=json.load(open('out/context.json')); assert set(d)=={'repo','commits','readme','sources','screenshots'}; assert len(d['commits'])<=50; print('context.json OK')"
python3 collect.py /nonexistent -o out/x.json; test $? -ne 0
```

## Routing

- Surface: exec:cloud
- Suggested role: default
- Model/reasoning tier: standard
- Parallel-safe: yes — owns only collect.py; the context.json contract is frozen in ADR-0001

## Handoff notes

- Dispatch to Codex cloud with `--attempts 2`.
- Issue #4 will import `collect()`; keep the function signature exactly as stated.
EOF
)"

BODY_GENERATE="$(cat <<'EOF'
## Objective

Implement stage 2: `generate.py` turns `context.json` into a SlideDeck JSON (6 slides + ja/en 90-second scripts) via OpenAI Structured Outputs with the fixed schema from the ADR.

## Context & references

- Epic: none (hackathon flat task list)
- Requirements: REQ-003, REQ-004 (content side), REQ-005, REQ-006, REQ-007, REQ-009, REQ-012
- Decisions: docs/agreements/adr-0001-architecture.md (SlideDeck contract and retry policy — do not change them)
- Read first: AGENTS.md, .github/copilot-instructions.md

## Acceptance criteria

- [ ] `generate(context: dict, langs: list) -> dict` is a pure function (API client injectable) returning JSON that conforms to the SlideDeck contract: exactly 6 slides with ids title/problem/solution/demo/architecture/next in order (REQ-003).
- [ ] Uses OpenAI Structured Outputs (strict JSON schema, default model constant `gpt-4o-mini`); a schema-invalid response is retried exactly once, then raises so the CLI exits non-zero (REQ-007).
- [ ] The system prompt forbids naming any feature absent from the context and enforces script budgets: ja <= 300 chars, en <= 90 words (REQ-005, REQ-006).
- [ ] Language subsetting per ADR: unrequested-language fields come back as empty strings (REQ-009).
- [ ] At least one offline unit test (mocked client — happy path and the retry-then-fail path) in `tests/`; no network needed (REQ-012).
- [ ] Argparse `__main__`: `python3 generate.py <context.json> -o <dir>/deck.json --langs ja,en`.

## Out of scope

- Collecting repo facts (issue #1), Markdown/Marp rendering (issue #3), CLI wiring (issue #4).
- Model benchmarking or prompt tuning beyond meeting the criteria.

## File ownership

- generate.py
- tests/

## Verification

```bash
python3 -m unittest discover tests   # offline, must pass without OPENAI_API_KEY
# Live smoke (OPENAI_API_KEY is configured in the cloud environment).
# Uses a minimal hand-written context fixture from tests/, since collect.py
# (issue #1) may not be merged yet:
python3 generate.py tests/fixtures/context_sample.json -o out/deck.json --langs ja,en
python3 -c "import json; d=json.load(open('out/deck.json')); assert [s['id'] for s in d['slides']]==['title','problem','solution','demo','architecture','next']; print('deck.json OK')"
```

## Routing

- Surface: exec:cloud
- Suggested role: default
- Model/reasoning tier: standard
- Parallel-safe: yes — owns only generate.py and tests/; both contracts are frozen in ADR-0001

## Handoff notes

- Dispatch to Codex cloud with `--attempts 2`.
- Create `tests/fixtures/context_sample.json` (small, hand-written, contract-conformant) as part of this task; issue #4 relies on `generate()` keeping its signature.
EOF
)"

BODY_RENDER="$(cat <<'EOF'
## Objective

Implement stage 3: `render.py` + `theme/pitch.css` turn a SlideDeck JSON into a bilingual Marp `slides.md` and `deck.html` (via npx), with the no-screenshot fallback.

## Context & references

- Epic: none (hackathon flat task list)
- Requirements: REQ-002 (cloud output set), REQ-003, REQ-004, REQ-008, REQ-010, REQ-013
- Decisions: docs/agreements/adr-0001-architecture.md (SlideDeck contract; cloud/local verification split — PDF is local-only)
- Read first: AGENTS.md, .github/copilot-instructions.md

## Acceptance criteria

- [ ] `python3 render.py <deck.json> -o <dir>/` writes `slides.md` (Marp front matter with `theme: pitch`, 6 slides separated by `---`) and the requested-language script files (`script_ja.md` / `script_en.md`), then runs `npx @marp-team/marp-cli` to produce `deck.html` with `theme/pitch.css`.
- [ ] Bilingual layout per slide: Japanese as normal (large) Markdown, English wrapped in `class="en"` elements the theme renders smaller and muted (REQ-004); empty-string language fields are omitted entirely (REQ-009 side).
- [ ] `theme/pitch.css` declares `/* @theme pitch */`, sets Noto Sans JP with system fallbacks, and visibly departs from default Marp (REQ-010; ~10 minute effort cap — do not gold-plate).
- [ ] Demo slide: uses `image` when set; when null, renders `arch_text` as a fenced text block — never a broken image link (REQ-008).
- [ ] No PDF/PPTX attempt in this environment (cloud has no Chrome/CJK fonts); HTML is the terminal artifact here.

## Out of scope

- Calling OpenAI (issue #2), collecting facts (issue #1), CLI wiring (issue #4).
- PDF/PPTX verification (local Mac, human).

## File ownership

- render.py
- theme/

## Verification

```bash
# Hand-write a minimal SlideDeck-conformant sample.json (per ADR-0001) as
# part of this verification, since generate.py (issue #2) may not be merged:
python3 render.py sample.json -o out/
test -f out/slides.md && test -f out/deck.html
grep -q "theme: pitch" out/slides.md
grep -c -- "^---$" out/slides.md   # expect slide separators for 6 slides
```

## Routing

- Surface: exec:cloud
- Suggested role: default
- Model/reasoning tier: standard
- Parallel-safe: yes — owns only render.py and theme/; the SlideDeck contract is frozen in ADR-0001

## Handoff notes

- Dispatch to Codex cloud with `--attempts 2`.
- First `npx @marp-team/marp-cli` call downloads the package (~30 s) — that is normal.
- Issue #4 will call `render(deck: dict, out_dir, langs)`; keep a callable function in addition to `__main__`. Do not commit `sample.json`.
EOF
)"

BODY_CLI="$(cat <<'EOF'
## Objective

Integrate the three stages behind one command: `pitch build <repo> --langs ja,en -o out/`, self-verified end-to-end on this repository.

## Context & references

- Epic: none (hackathon flat task list)
- Requirements: REQ-001, REQ-002, REQ-009, REQ-013
- Decisions: docs/agreements/adr-0001-architecture.md (stage contracts; cloud definition of done = slides.md + deck.html)
- Depends on: #1 (collect), #2 (generate), #3 (render) merged to main
- Read first: AGENTS.md, .github/copilot-instructions.md

## Acceptance criteria

- [ ] `./pitch build <repo> --langs ja,en -o out/` runs collect → generate → render and, on this repository itself, produces `out/context.json`, `out/slides.md`, `out/deck.html`, `out/script_ja.md`, `out/script_en.md` in <= 2 minutes (REQ-001, REQ-002, REQ-013).
- [ ] `--langs ja` and `--langs en` alone work; only requested-language artifacts are written (REQ-009).
- [ ] A stage failure exits non-zero with a one-line readable error naming the stage; partial outputs already written are left in place.
- [ ] `requirements.txt` (only `openai`), README section with the exact usage command, and `.gitignore` entry for `out/` are in place.
- [ ] `pitch` is an executable shim (`#!/usr/bin/env python3` or bash exec) so no pip install of the tool itself is needed.

## Out of scope

- Any change to collect.py / generate.py / render.py / theme/ (single-writer rule — escalate with needs:replan if their interfaces prove wrong).
- Batch mode (issue #5), PDF/PPTX (local-only).

## File ownership

- cli.py
- pitch
- requirements.txt
- README.md
- .gitignore

## Verification

```bash
pip install -r requirements.txt
time ./pitch build . --langs ja,en -o out/
test -f out/slides.md && test -f out/deck.html && test -f out/script_ja.md && test -f out/script_en.md
./pitch build . --langs ja -o out_ja/
test -f out_ja/script_ja.md && test ! -e out_ja/script_en.md
```

## Routing

- Surface: exec:cloud
- Suggested role: default
- Model/reasoning tier: standard
- Parallel-safe: no — integration task; dispatch only after #1-#3 are merged

## Handoff notes

- Dispatch to Codex cloud with `--attempts 2` once #1-#3 are merged.
- This issue's verification is the product's definition of done in the cloud; the human then runs the local-Mac PDF check (`npx @marp-team/marp-cli out/slides.md -o out/deck.pdf`) before the 15:00 dry run.
EOF
)"

BODY_ALL="$(cat <<'EOF'
## Objective

Stretch: `build_all.py` builds decks for multiple repositories in one invocation (today's 3 hackathon repos), isolating per-repo failures.

## Context & references

- Epic: none (hackathon flat task list)
- Requirements: REQ-101 (stretch)
- Decisions: docs/agreements/adr-0001-architecture.md
- Depends on: #4 (working `./pitch` CLI) merged
- Read first: AGENTS.md, .github/copilot-instructions.md

## Acceptance criteria

- [ ] `python3 build_all.py <repoA> <repoB> ... -o out_all/ --langs ja,en` runs the pitch pipeline per repo (subprocess call to `./pitch build`), writing to `out_all/<repo-name>/`.
- [ ] One failing repository does not stop the others; a final summary line reports ok/failed per repo and the exit code is non-zero if any failed.

## Out of scope

- Changes to cli.py or any stage module (single-writer rule).
- Parallel execution, config files (a sequential loop is fine today).

## File ownership

- build_all.py

## Verification

```bash
git clone . /tmp/selfcopy
python3 build_all.py . /tmp/selfcopy -o out_all/ --langs ja
test -f "out_all/$(basename "$PWD")/slides.md"
python3 build_all.py . /nonexistent -o out_all2/ --langs ja; test $? -ne 0
test -f "out_all2/$(basename "$PWD")/slides.md"   # good repo still built
```

## Routing

- Surface: exec:cloud
- Suggested role: default
- Model/reasoning tier: fast
- Parallel-safe: yes — owns only build_all.py; but requires #4 merged, so dispatch last

## Handoff notes

- Stretch goal (REQ-101): dispatch only if the 15:00 gate leaves slack; a shell loop over `./pitch build` is an acceptable manual substitute.
EOF
)"

new_task "Implement collect.py: repo facts to context.json" "$BODY_COLLECT"
new_task "Implement generate.py: Structured Outputs SlideDeck + offline test" "$BODY_GENERATE"
new_task "Implement render.py + Marp theme: SlideDeck to slides.md and deck.html" "$BODY_RENDER"
new_task "Integrate CLI: pitch build <repo> --langs ja,en -o out/" "$BODY_CLI"
new_task "Stretch: build_all.py multi-repo batch mode" "$BODY_ALL"

echo "Done. 5 task issues filed (dispatch #1-#3 in parallel now; #4 after merge; #5 optional)."
