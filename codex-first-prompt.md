# Codex first prompt — Pitch Autopilot (final)

Paste the block below into Codex cloud as the first task for this
repository. Recommended dispatch: `--attempts 2`. Prerequisites: this design
pack is committed to `main`; the cloud environment has `AZURE_OPENAI_ENDPOINT`,
`AZURE_OPENAI_API_KEY`, and `AZURE_OPENAI_DEPLOYMENT` configured, with
optional `OPENAI_API_VERSION` (default `2024-10-21`) and internet access ON.

Use this single prompt for the fastest path to a working MVP (13:30 kickoff).
The alternative, finer-grained path is `issues.sh` (one task = one PR,
issues #1-#3 in parallel, then #4); prefer it from the second iteration on,
or if a first-prompt attempt needs to be redone in parts.

---

```text
Read, in this order: AGENTS.md, .github/copilot-instructions.md,
docs/agreements/requirements.md, and docs/agreements/adr-0001-architecture.md.
They are the operating rules, the validated commands, the REQ list, and the
pipeline + frozen JSON contracts. Follow them; do not re-derive the
architecture or change a contract.

Then implement the Pitch Autopilot MVP:

1. collect.py — repo facts (git log --stat max 50 commits, README, first 200
   lines of up to 10 key sources, assets/screenshots/ listing) ->
   out/context.json per the ADR contract. Verify on this repository itself.
2. generate.py — Azure OpenAI Structured Outputs with the fixed SlideDeck schema
   from the ADR: 6 slides (title/problem/solution/demo/architecture/next) +
   90-second scripts (ja <= 300 chars, en <= 90 words), facts-only (never
   name a feature absent from context.json), retry once on a schema-invalid
   response then fail non-zero. Add one offline unit test with a mocked
   client in tests/. Use `AzureOpenAI` with key-based authentication and pass
   `AZURE_OPENAI_DEPLOYMENT` as `model`.
3. render.py + theme/pitch.css — Marp Markdown with the bilingual layout
   (Japanese large, English in class="en" rendered smaller), then
   `npx @marp-team/marp-cli out/slides.md -o out/deck.html --theme theme/pitch.css`.
   No screenshot -> render arch_text as a fenced text diagram.
4. cli.py + ./pitch shim — integrate as
   `pitch build <repo> --langs ja,en -o out/`; `--langs ja` or `en` alone
   must also work. Add requirements.txt (openai only), a README usage
   section, and git-ignore out/.

After each step, show the generated file paths and a short summary of their
contents. Definition of done in this cloud environment:
`./pitch build . --langs ja,en -o out/` on this repository produces
out/slides.md and out/deck.html, and `python3 -m unittest discover tests`
passes. Do NOT attempt deck.pdf here (no Chrome, no CJK fonts — PDF/PPTX
are verified on the local Mac). Commit in small steps.
```
