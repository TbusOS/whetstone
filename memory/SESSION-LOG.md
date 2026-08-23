# Whetstone · Session Log (generic)

> Continuity log for the **whetstone tool** itself — capability-level only, **0 internal data**.
> The full internal record (distilled skills with real platform values, session details) lives in
> the private data repo (`whetstone-skills-private/memory/`), never here. See also `CLAUDE.md`.

## 2026-06 · pipeline layer + index hygiene + intro pages

A multi-day arc that took whetstone past its v1 core. All tool changes are generic; the skills it
distilled carry real values and stay in a private repo.

### Pipeline layer
- `adapters/capture/claude-code.sh` — hardened + a `selftest.sh` (10/10). Writing the selftest caught
  a real path bug: `SKILL_DIR` used one `..` and would land the journal in `adapters/journal/` instead
  of the skill-root `journal/` that `/distill` reads — fixed to two `..`.
- `bin/promote.sh` (new) — mechanically installs brand-new skills from `inbox/`; refuses to silently
  clobber an existing skill (semantic L2-merge stays with the agent `/promote`); provenance to journal.
- `cli/whetstone` (new) — noun-verb dispatcher over pack/deploy/promote/capture/selftest/journal/sync.
  `distill` honestly points to the agent runtime instead of pretending to run.
- `adapters/sync/engram.sh` (new) — builds the engram `memory add` invocation; `--dry-run` tested; the
  live write is left unverified (engram not runnable on this machine) and the doc says so.

### Index hygiene (the big add)
- Insight: the runtime keeps every skill's **name + description** in context to choose between them —
  that menu is where noise lives, not the bodies (lazy-loaded). As the library grows, vague/overlapping
  descriptions make the model mispick.
- `bin/lint.py` — flags missing triggers, overlapping trigger sets (Jaccard), name near-collisions.
  Later made smarter: companion suffixes (`-audit`/`-validator` that reference their base) and
  mutually-cross-referenced trigger overlaps are downgraded to INFO; only real clashes stay WARN.
- `bin/index.py` — groups skills into families (shared triggers + name-collision + cross-refs) and emits
  a browsable `INDEX.md`. Fixed a clustering bug: a **boundary** reference ("not X / use X instead")
  must NOT count as a family edge — otherwise the boundary lines we add for hygiene glue distinct skills.
- `references/extraction-framework.md` §13 — the **description contract** (capability line + concrete
  triggers + boundary declaration + name not a segment-prefix of another), baked into the skill template.
- A name near-collision the linter caught was resolved by renaming one skill so its name no longer
  prefix-collides with an unrelated one.
- `cli/whetstone lint|index` wired in.

### GitHub Pages
- `docs/index.html` gained an "index hygiene" section (mechanism diagram + lint/index/contract cards).
- A second page `docs/skills.html` (new) — a **generic** showcase: anatomy of a skill package
  (SKILL.md + params/<platform>.md + pitfalls.md), capability archetypes, and how to use one. All
  placeholders (SoC-X / OTP[ADDR] / RSA-N), 0 internal data. Linked from the main nav.
- Both pages pass the anthropic-design 3 gates (verify / visual-audit / screenshot).
- Pages serves `main`/`docs` at the project site; Enforce HTTPS turned on (http → https 301 verified).

### Distillation work (summary; details are private)
- Distilled a new boot-observability skill and a new verified-boot skill family member, and topped up an
  existing verified-boot skill — from a real engineering codebase. Specifics (platform values, addresses,
  commits) live in the private repo.
- The distiller's two gates earned their keep: the **doc + git/code double-check** caught several
  "the doc says X but the code says Y" cases (a fix already landed, a gap already closed, a proposal that
  was never actually taken), and **Phase-3 dedup** shrank one batch by half and rejected a second batch
  entirely as already-covered — "nothing worth adding" is a correct, anti-bloat outcome.

### Discipline reaffirmed
- Tool/data separation: this public repo carries **0 internal data**; real skills + values live private.
- A private repo's HTML is safe to push **only because Pages is never enabled** on it (a private repo's
  Pages site would still be public by default).

## 2026-08 · autoupdate + evidence upgrade (§7)

### autoupdate/ (new component)
- Ported the multi-CLI update prompter from its sibling repo: session-hook check (read-only,
  throttled fetch) + confirmed `git pull --ff-only`. Three adaptations: **join/own install modes**
  (if a compatible `*-autoupdate` hook already exists on the machine, just register this clone in
  its repos config — never double-hook), **union read** of all `~/.config/*-autoupdate/repos`
  (whichever tool's hook is alive sees every watched repo), and two porting bugs fixed (macOS has
  no `timeout` by default → fetch fallback; restart-detection regex missed root-level SKILL.md).
- `autoupdate/selftest.sh` 22/22 against isolated fixtures (fake HOME + fake remote/clones).
  CLI verb: `whetstone autoupdate check|update|install|upgrade|uninstall|selftest`.

### Evidence upgrade: the library now metabolizes after entry (§7 rework)
Research pass (4 parallel agents: this repo, engram internals, local paper notes, external
systems/papers) concluded the design's one structural gap: **quality control was all at the
entrance — nothing flowed back after a piece of knowledge entered the library.** Two cheap fixes,
both spec-level, no new infrastructure:
- **Executable verification slot** (absorbed from the kernel-learn discipline): every entry gets a
  `验证方式` field — a command/script/minimal-repro that can confirm or falsify it. Confidence is
  now decided by a **mechanical table** (high = verified + reproduced ≥2; no executable check caps
  at med), not by feel. Rationale: an unverifiable "high" is how stale lore survives.
- **Reproduction write-back** (ExpeL-style upvote): `复现次数` (a bare number) became `复现记录`
  (an append-only list of `platform/project · date · pointer`). When a new distillation session
  *uses* an existing entry and it holds, Phase 3 appends a confirmation line to that entry —
  inside the proposal, so it still passes human review. Contradiction never appends; it goes the
  supersede/conflict route. Human review stops being one-shot: every session accrues or overturns
  evidence for old entries.
- Touched: extraction-framework §7/§8/§9, SKILL.md Phase 2/3/4/5 + blacklist, both templates
  (also fixed the template bug: its provenance section had dropped the reproduction field),
  spec/skill-package.md. `adapters/sync/engram.md` corrected two overstated claims about engram
  (its dedup is post-hoc heuristic only; memory-asset confidence decay is spec'd but unimplemented)
  — delegation must match measured reality, not docs.
