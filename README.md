# Whetstone · 磨刀石

**Every "distill your sessions into skills" tool writes knowledge in. This one also refuses it.**

Whetstone turns a finished dev session into a portable Agent Skill — and then holds that
skill to an evidence standard you can run as a command. Confidence levels come from a
mechanical table, not from a model's mood. A lesson seen on one platform cannot enter the
skill body. A fact is appended and marked superseded, never quietly replaced. None of that
is a paragraph of documentation — it is `whetstone verify`, exit code and all.

```console
$ whetstone verify examples/demo-skill --brief

whetstone verify — examples/demo-skill

ERROR (5)
  ✗ SKILL.md:31  [V16] [溯源] 复现记录 has two lines for the same platform/project: 'soc-x'
  ✗ SKILL.md:31  [V12] [溯源] L2 claims 置信度 high, the table allows only low — 复现记录 has 1 line(s), needs 2 (single-platform L1/L2 is capped at low — the §7 constraint outranks the table)
  ✗ pitfalls.md:5  [V14] [从上层状态反推底层状态会看错] 复现记录 is a bare count 「2 次」
  ✗ pitfalls.md:5  [V12] [从上层状态反推底层状态会看错] L2 claims 置信度 high, the table allows only low — 复现记录 has 0 line(s), needs 2 (single-platform L1/L2 is capped at low — the §7 constraint outranks the table)
  ✗ params/soc-x.md:6  [V10] [存储起始位置] L3 claims 置信度 high, the table allows only low — 验证方式 never passed a test; 复现记录 has 1 line(s), needs 2

WARN (3)
  ! SKILL.md:18  [V19] concrete value in the body (hex address/value): '0x1A40'
  ! SKILL.md  [V25] no section says what must NEVER be done in this domain
  ! params/soc-x.md  [V22] no 替代记录 section

summary: 5 error(s), 3 warning(s), 0 info
```

Five refusals, in order: the same platform counted twice to fake cross-platform evidence ·
a method claiming `high` on one platform · a reproduction count written as a number instead
of a record · the same again · a platform value claiming `high` that was never actually
tested. Drop `--brief` and every line gains the rule it came from.

That transcript is copied from a real run. `examples/demo-skill` ships in this repo,
deliberately flawed, so you can reproduce it in one command. Field names stay in Chinese
because that is what they are called inside the files you would be editing.

> 中文说明:把开发经验蒸馏成可移植 Agent Skill,并用一条能跑的命令守住证据纪律 ——
> 置信度按机械表判、单平台经验进不了正文、事实不许被悄悄改掉。规矩不是散文,是退出码。
> 详见 [`references/extraction-framework.md`](references/extraction-framework.md)。

---

> What this looked like when it was first run against a real library:
> [**I marked 61 entries "high confidence." Not one could name a test.**](https://doc.tbusos.com/whetstone/why-verify.html)

## Why another one of these

A skill library does not fail loudly. It fills up with plausible, unfalsifiable, once-true
advice that still wears a confident label. Six months later you cannot tell which entries
are load-bearing and which are folklore — and neither can the model reading them.

So the interesting question is not "can an agent write a skill file". It is
**what the pipeline refuses to do**:

| Whetstone will not | Why |
|---|---|
| Auto-write the library | Proposals land in `inbox/`. Two human gates: *is the mining right*, then *does it go in*. |
| Mark anything `high` without an executable check that actually passed | An unfalsifiable claim wearing a high-confidence badge is the exact shape of a rule that quietly expires. |
| Promote a lesson seen on one platform | One data point is a coincidence. A second distinct platform, or it stays out of the skill body. |
| Count the same project twice | A reproduction line is keyed by platform/project. Ten runs on one project is one line — otherwise write-back becomes a back door around the gate. |
| Silently overwrite a fact | Append and mark superseded, especially for safety and irreversible values. |
| Grade its own homework | Quality review runs in a separate context. An unguided LLM judge picks the better of two skills 46.4% of the time — indistinguishable from a coin ([SkillLens, Microsoft](https://microsoft.github.io/SkillLens/)). Self-review is the bias this design assumes, not one it hopes to avoid. |
| Pretend prose is enforcement | The mechanically decidable part of every rule above is a check in `whetstone verify`. |

## The confidence table is a table, not a vibe

| Level | Condition |
|---|---|
| `high` | executable check **passed** *and* reproduced on ≥2 distinct platforms/projects |
| `med` | reproduced on ≥2 distinct platforms/projects; **or** verified once, but that second route is open to L3 facts only |
| `low` | everything else |

Verifying a method once does not make it general, so an L1/L2 entry on a single platform is
capped at `low` even when its check passes. A human reviewer may downgrade any entry and may
**never** upgrade past the conditions — `verify` implements that asymmetry: above the cap is
an ERROR, below it is only an INFO.

## What it deliberately does not decide

Mechanising a judgement that is not mechanical only manufactures false positives. These stay
with the human reviewer, and `whetstone verify --explain` prints the boundary in full:

- is an L1 entry really exception-free
- does an L2 lesson survive deleting every platform-specific value
- was a contradiction preserved rather than averaged away
- were this session's reproduction write-backs applied (needs the session, not the package)
- when in doubt, was the entry placed lower rather than higher (only the outcome is visible)
- is the prohibition list a set of real hazards or filler (V25 sees the heading, not the judgement inside it)

`--explain` also states where each check is narrower than the rule it serves — for instance
that provenance is checked per declared record, so a bare bullet in a `SKILL.md` body with no
provenance at all is not something `verify` can see.

And one boundary sits outside the whole list: every check above asks whether the knowledge is
**true and traceable**. None asks whether installing the package makes its consumer better.
Those two do not predict each other — in the SkillLens corpus 25% of extractor/consumer
pairings transferred *negatively*, and textual plausibility failed to predict utility. So a
clean run means the evidence discipline held. It does not mean the skill is good.

## The four layers

One ruler: **how far does this travel?** Full schema in
[`references/extraction-framework.md`](references/extraction-framework.md).

| Layer | Scope | Lives in |
|---|---|---|
| **L1** principle | true on any platform, any vendor — an objective constraint, not your choice | `SKILL.md` |
| **L2** method / pitfall | still true after a platform change, but it is *your* approach | `SKILL.md` · `pitfalls.md` |
| **L3** platform fact | changes when the platform changes: addresses, lengths, tool names | `params/<platform>.md` |
| **L4** state | changes by the next session: current key, current HEAD, which board | memory, timestamped |

A pitfall is never one layer. It is a transferable lesson (L2) **plus** a one-platform fact
(L3), and not splitting it is a hard error — bind the lesson to the platform and you paid for
the pain twice.

New platform → add one `params/` file. Better method → edit one L2 line and every platform
benefits. That asymmetry is what "gets smarter with use" means here.

## Install

Whetstone is itself an Agent Skill (`SKILL.md`) plus references. Drop the directory into your
runtime's skills directory — Claude Code, Codex, Cursor, or anything that reads the Agent
Skills layout. No agent-runtime lock-in and nothing to install: the CLI is bash, the checks
are Python standard library, and everything it produces is plain markdown.

```bash
git clone https://github.com/TbusOS/whetstone.git
cd whetstone
bash bin/verify_selftest.sh                       # 124 assertions across 38 checks
bash bin/verify_mutation_test.sh                  # delete each check; the suite must go red
./cli/whetstone verify examples/demo-skill --brief
```

The selftest asserts **both directions** for every check — a defective fixture makes it fire,
a conforming one keeps it quiet — and a coverage pass fails the run if any published check is
missing either direction, so that claim cannot drift. The mutation battery then deletes each
piece of checking logic in turn and requires the suite to go red: a check whose removal changes
nothing is not being tested, and a green suite over such a check reports safety that is not
there. Three independent reviews found four ways to slip past the promotion gate — a dropped
separator, a heading that merely mentioned "L3", a parenthesised platform suffix, a table
without leading pipes — and every one of them is now a mutation entry.

Optional, none required: session capture
([`adapters/capture/`](adapters/capture/README.md)), update prompting
(`bash autoupdate/install.sh`), downstream sinks ([`adapters/sync/`](adapters/sync)).

## Use

1. Finish a feature → trigger distillation (`/distill`, or "distill this session").
2. Review the proposal — two gates: *mined correctly?* then *does it go in?*
3. `whetstone verify` the package, `whetstone promote` it into your library.

Mining a transcript is agent work and runs in your runtime. Everything deterministic around
it is CLI:

```bash
whetstone verify <pkg> --strict     # evidence discipline — this is the one that says no
whetstone verify --explain          # all 38 checks, their limits, and what is left to humans
whetstone lint --src ~/skills       # selection-menu hygiene: overlaps, collisions, vague descriptions
whetstone index --src ~/skills      # grouped catalog
whetstone promote <proposal>        # install a proposal, refusing to overwrite an existing skill
whetstone pack | deploy             # move a library between machines
whetstone sync engram <skill>       # optional: push one skill into a local engram memory store
whetstone decision add …            # record what you decided about a proposal, and why
whetstone decision stats            # what those decisions have started to point at
whetstone decision alias --from … --to …   # fold two spellings of one meaning together
```

`lint` and `verify` guard different failures. `lint` guards **retrieval** — a library whose
descriptions overlap makes the model pick the wrong skill. `verify` guards **content** — a
library whose entries carry unearned confidence makes the model believe the wrong thing.

`decision` guards neither; it records. Reviewing a proposal produces a judgement — kept as
proposed, moved down a layer, downgraded, refused — and every one of those says where the
framework's judgement and yours diverged. They used to end with the session. They are the
only labels this tool gets for free, and the only raw material from which the framework
could ever improve on its own evidence rather than on the next paper someone reads. It
analyses nothing yet: see [`spec/review-decisions.md`](spec/review-decisions.md) for what
it deliberately is not.

A tag only accumulates while the same meaning keeps getting the same string, so `add` shows
the existing vocabulary the moment you introduce a new one, and `alias` folds two spellings
together afterwards — at read time, leaving every stored line byte-identical. What it will
not do is guess: measured on this vocabulary no similarity threshold separates
`priority-wrong`/`priority-mistake` (0.60) from `missing-feature`/`missing-split` (0.643),
and word order and language defeat it outright. A bad ordering costs a glance; a bad merge
costs the signal.

## Layout

```
SKILL.md                            distiller entry point (Phase 0-5)
references/extraction-framework.md  the L1-L4 schema — the actual core
spec/skill-package.md               portable skill-package format (the deliverable)
spec/review-decisions.md            what a recorded review decision looks like, and its limits
commands/                           /distill and /promote slash-command definitions
bin/verify.py                       evidence discipline, executable
bin/verify_selftest.sh              124 assertions, both directions, coverage-enforced
bin/verify_mutation_test.sh         deletes each check in turn; the suite must go red
bin/decision.py                     the review-decision log (record only; 46 assertions)
bin/decision_mutation_test.sh       deletes each decision check; the suite must go red
bin/lint.py · bin/index.py          selection-menu hygiene
bin/pack.sh · bin/deploy.sh · bin/promote.sh   move and install packages
cli/whetstone                       runtime-agnostic CLI, pure bash
templates/                          skeletons for a distilled skill / params / pitfalls
examples/demo-skill/                deliberately flawed package behind the demo above
inbox/ · journal/                   proposals awaiting review; mined source material
adapters/capture · adapters/sync    optional: session capture, optional sinks
autoupdate/                         optional: multi-CLI update prompter
docs/                               the project page at doc.tbusos.com/whetstone
```

## Companions

| Project | What it adds |
|---|---|
| [whetstone-curator](https://github.com/TbusOS/whetstone-curator) | team side: pull good entries from a teammate's library, or harvest a shared one |
| engram | sync a package into a local memory store ([notes](adapters/sync/engram.md); scope checked against its code, not its README) |
| llm-wiki | publish knowledge as human-readable pages ([notes](adapters/sync/llm-wiki.md); documentation only, no script yet) |

More background on the project page: **https://doc.tbusos.com/whetstone/**

## License

MIT — see [LICENSE](LICENSE).
