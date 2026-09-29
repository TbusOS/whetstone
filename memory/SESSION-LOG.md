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

---

## 2026-09 · utility features, the review-decision log, tag consistency

Research pass over two Microsoft papers that study exactly what this tool does — SkillLens
(the full lifecycle: raw experience → extraction → consumption) and SkillOpt (training the
skill document as the state of a frozen agent). Both landed findings the framework could use,
and one it had to absorb about its own limits.

### The limit worth writing down first
Every check in `verify` asks whether an entry is **true and traceable**. None asks whether
installing the package makes its consumer better. SkillLens measured those two as
uncorrelated: 25% of extractor/consumer pairings transferred *negatively* (47% in the worst
domain), an unguided judge picks the better of two skills 46.4% of the time, and format has no
significant effect (p>0.34) while "the skill that reads better is often the one that performs
worse". So a clean run means the evidence discipline held — nothing more. That boundary is now
stated in §14, `--explain`, the spec and the README rather than left implied.

### §14 — the package's own prohibition list (+ V25)
SkillLens found an explicit "never do X here" list to be one of three features tracking real
utility. The framework had a blacklist (§9) but it governs the **distiller**; nothing ever
required the shipped package to carry one. §14 adds that, the template gets a section, and V25
checks it — W, not E, because presence is decidable and content is not. Its failure direction
is permissive (a filler list passes unnoticed), so the limit is written wherever the check is.

### §4 — "push it down to L3" means values, not commands
V19 only ever scanned five things (hex, IP, system path, pinned version, dimensioned number);
it never touched tool, command or function names. That was only true in the code. Read
together, §9#1 ("no concrete values in the body") and §3 ("when unsure, place it lower")
push toward a document of abstract steps — which is precisely what the same paper measured as
worst-performing. §4 now states the distinction with a worked table.

### The review-decision log — the framework's own raw material
Nothing recorded what the reviewer *did* to a proposal. Yet each accept/amend/reject is a free
label saying where the framework's judgement and the reviewer's diverged, and the whole
self-improvement literature is stuck on where to get a grading signal. §7 (2026-08) and §14
both came from outside reading plus a human call — the tool's own history did not exist to
learn from. `whetstone decision` records it, and only records: no analysis, no rule changes.
`stats` counts **distinct sources**, never lines, and a record with no source counts with all
the others as one — independence that cannot be shown is not granted.

### Tag consistency, done without guessing
A tag only accumulates while one meaning keeps one string. Measured on the starter vocabulary,
no similarity threshold does this job: 0.72 misses `priority-wrong`/`priority-mistake` (0.60)
while 0.60 wrongly pairs `missing-feature`/`missing-split` (0.643); word order
(`layer-wrong`/`wrong-layer`, 0.455) and language (0.0 across scripts) defeat it outright, and
the two pairs are structurally identical — the difference is semantic. So: `add` shows the
existing vocabulary when a new tag appears (similarity orders the list, never judges it), and
`alias` folds two spellings at **read time**, leaving every stored line byte-identical.
Chains resolve, loops are refused on write and reported rather than folded on read.

### A mutation that never applied was passing
`mut()` printed a lowercase note and returned when its anchor text had drifted — counted as
neither caught nor missed, so an entry that had silently stopped testing anything kept the run
green. Both batteries now count that separately and fail on it, and both wrap the suite in a
timeout since a mutation can remove a loop guard. Verified by breaking an anchor on purpose:
`caught: 13 missed: 0` exit 0 before, `did-not-apply: 1` exit 1 after.

### Where it left off
verify 124 checks + 14 mutations; decision 46 checks + 8 mutations. The decision log holds its
first five records — this session's own framework changes, including one recording that the
meta-level work was ranked last and the ranking was wrong. Nothing has reached the 3-source
threshold, which is the expected state. The log's one failure mode is nobody filling it in,
and that failure is silent.

---

## 2026-09-28 · use-time conflicts, recorded in two steps

### Why the review moved to use time
The question was whether human review of distilled knowledge could become AI review. A
four-way survey (open-source memory systems read at the code level, papers on self-evolving
experience libraries, work on calibrating LLM judges against humans, and the autoresearch /
darwin / nuwa family) agreed on one point: no system lets an AI decide on its own whether an
old entry should change. The ones that work share a shape — mechanical checks underneath, the
AI only classifying, escalation when unsure, autonomy granted per class from measured
agreement. One large memory library removed LLM-driven UPDATE/DELETE entirely in 2026-04.
The reviewer then reframed the problem: judge an entry when it is USED, not when it enters.
At use time the code and the board are in front of the agent, so "is this still right" has an
answer. `spec/use-time-conflicts.md` is that protocol: classify first (a mismatch is not
necessarily a wrong entry — the entry may be stale, platform-scoped, or the code may be
repeating the very mistake a pitfall warns about), grade the evidence, report before changing
anything, and change only on a human yes.

### Why two steps
The party being scored writes the record. Written in one line after the answer, the AI's
"own" call can be copied from the human's and agreement reads 100% with nothing on screen.
So `decision report` puts the AI's call on file first and prints an id plus a fingerprint the
conflict card must carry, and `decision resolve` appends the answer. A used id cannot be
reported again, an edited report no longer matches its fingerprint and is not scored, an
answer with no report before it is ignored, and an entry reported twice in one source is
scored on its FIRST call. The remaining hole — running `report` only after hearing the answer
— is not something the tool can see; the fingerprint line on the card is what a human glances
at.

### Scoring, and what it may change
Per (type x evidence) group, agreement is judged by an exact one-sided binomial lower bound,
never the point estimate (22 agreeing out of 22 is the least that clears 0.90 at delta 0.1;
18 of 20 clears only 0.755). A tier changes how the human is asked — full, one-line summary,
end-of-task batch — never whether. A guess share above 30% or a miss of
that type all send a group back to full confirmation. decision selftest 46 -> 113, mutations
8 -> 30. A separate known-answer exam was drafted as a further gate and dropped on
2026-09-29 at the reviewer's call: the next real use of an entry is the exam. Relaxing
already needs at least 22 agreeing real records per group, the two traps an exam would
have targeted surface in real records anyway (a changed type drags the group down;
inferred and unseen groups never relax), and a tier only changes how the question is asked.
The one gap that left — agreement earned by one model being credited to the next — was closed
the same day: every report now records the model that made the call (covered by the
fingerprint), and tiers count only the current model's reports, so a model change starts every
group from zero. Older reports without the field read as model "unknown".

### Two old bugs, found while wiring the rule in
Writing the always-on rule meant running `whetstone decision` from PATH, and it failed:
`cli/whetstone` took its directory from the symlink it was called through, so every
subcommand that reads `bin/` had been broken through `~/.local/bin/whetstone` for five
weeks — only `--version` worked, which is why nobody noticed. It now resolves links in a
loop (no `readlink -f`, which older macOS lacks); the decision selftest calls it through a
one-level and a relative two-level link, and both went red on the old script first.

The second one did damage. The autoupdate selftest pins PATH, which on this machine selects
git 2.25; `git init -b` does not exist there, so the fixture repos were never created, and
a later `git -C <plain dir> add -A / commit / push` walked up into the real repository and
pushed a dirty working tree to the public origin under a fake author (that commit was
rewritten away afterwards). Three layers now:
`GIT_CEILING_DIRECTORIES` stops discovery at the fixture directory, every fixture is checked
to be its own repository before any test runs (exit 2 otherwise), and the enclosing repo's
HEAD and working tree are compared before and after. Verified in throwaway clones with fake
remotes: the old script reproduces the leak, the new one passes 44/44 without touching the
clone, a deliberately broken fixture stops before the tests, and the ceiling alone still
holds. On this machine the suite had been 31 passed / 12 failed all along.

### deploy.sh: a fix that lived only in the copy
The missing-value spin in `deploy.sh` (`shift 2` with one argument left fails and shifts
nothing) had been fixed on 2026-09-03 — in the private library's copy of the script, not
here. The private drift checker then kept reporting "upstream is newer, the copy is behind"
and suggesting `--sync`, which would have overwritten the fix with the old version. The
guard is now in this repo, `bin/deploy_selftest.sh` holds it (all six value-taking options
must exit 2 within five seconds; the old script hung on seven checks), and the drift checker
on the other side decides direction by commit time and never overwrites a newer copy.

---

## 2026-09-29 · the menu has a budget, and lint now checks it

### What was measured
Whether a skill gets loaded when the conversation touches its topic. Thirty days of local
sessions on one machine (59 sessions): skills tied to a working directory by an always-loaded
rule were loaded in 8 of 10 sessions; skills that depended on trigger words in their
description were loaded in 5 of 38 session-and-skill pairs where the words came up. The
runtime's menu stayed at about 25K chars while it grew from 69 to 111 entries, so 35 of the
library's 65 skills were shown as a bare name. With the description in the menu, 26% of
trigger-word messages loaded the skill; with only the name, 1%.

### What changed
`lint` used to check descriptions one by one. They can each be fine and still not fit. It now
adds up the whole menu, compares it with a budget (a flag; the default is that measurement),
and when over gives the fair share per description and which to trim first. Trimming every
description above the share down to it always fits, so the only case that needs retiring or
merging skills is a share too small to write a description in. `--listing` takes the menu the
runtime actually sent — `adapters/menu/claude-code.py` reads it from Claude Code's session
records — and names the skills shown as name only, and the ones shown with something other
than their own description.

### What the check found in its own parser
The frontmatter parser read one line of a quoted description. A description whose second
line starts at column 0 (legal inside quotes) was cut short and its second line read as a new
key. The fix was checked against PyYAML on every skill in the library, not on fixtures alone.

