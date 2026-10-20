# Whetstone · 磨刀石

Finish a feature, and whetstone turns what the session taught you into a skill package for
your own skill library. The next time you do that kind of work, your agent picks the package
up by itself. Every entry has to say where it came from; an entry that cannot is not let in.

*Every "distill your sessions into skills" tool writes knowledge in. This one also refuses it.*

中文版:[README.zh.md](README.zh.md)

## How one lesson travels

```
session transcript + git diff
   │ 1. distill: the agent follows SKILL.md; every entry cites its source
   ▼
a skill package: one directory, three files
   │ 2. gate: whetstone verify checks the evidence, then a human reviews
   ▼
your own skill library (~/.claude/skills/, ~/.agents/skills/, ...)
   │ 3. reuse: the runtime shows the model every package's name + description
   ▼
the topic matches → the model reads SKILL.md → reads params/<platform>.md
                                                 when it gets to that step
```

Each step has a different owner, on purpose:

- **Step 1 is model work.** Telling a lesson from chatter takes reading, not rules, so the
  distiller is a set of instructions for the agent ([`SKILL.md`](SKILL.md), Phase 0-5), not a
  program. `whetstone distill` only tells you to run it inside your agent.
- **Step 2 is where the model is not trusted.** A model fills gaps and grades its own work
  generously. What it writes must cite a commit or a session, pass a command that involves no
  model, and get past a person, twice: *is the mining right*, then *does it go in*.
- **Step 3 is your runtime's own skill mechanism.** Whetstone triggers nothing. It keeps the
  menu entry good (`whetstone lint`) and keeps the library reachable once the menu is too
  long to show in full (`whetstone find`).
- The packages live in **your** library, never in this repository: they carry real platform
  values. This repository is the tool.

## What a correct package looks like

[`examples/good-skill/`](examples/good-skill) is a complete package for a made-up domain:
storage that can be written only once. `whetstone verify` finds nothing wrong with it.

```
examples/good-skill/
├── SKILL.md          how it gets picked (name + description), then
│                     principle · method · never-do list · pointers
├── pitfalls.md       what went wrong: symptom · cause · fix · values
└── params/soc-x.md   values true on soc-x only; one file per platform
```

**`SKILL.md`: the two lines that get it picked.** Until the topic matches, the runtime shows
the model only these. The description says what the package is for (writing and checking
write-once storage) and the words that should bring it up.

<!-- excerpt: examples/good-skill/SKILL.md -->
```yaml
name: good-skill
description: "一次性写入的存储(写坏就回不去)怎么写、怎么核对:写前先存原始内容,写后直接读回底层比对。触发词:一次性写入 / 写入前备份 / 读回比对 / write-once storage。"
```

The body has one section per kind of knowledge: 原理与约束 (principle, L1) · 设计与流程
(method, L2) · 坑 (pitfalls, pointing at `pitfalls.md`) · 禁止 (what never to do) ·
平台参数 (pointing at `params/soc-x.md`) · 溯源 (where it all came from).

**`pitfalls.md`: one pitfall.** "Reading the low-level state off a higher layer gets it
wrong": symptom, root cause, fix, and which values it involves. Its evidence block follows,
with the same fields as the table below.

<!-- excerpt: examples/good-skill/pitfalls.md -->
```markdown
## 从上层状态反推底层状态会看错

- 症状:上层字段显示未生效,底层其实已经生效。
- 真因:中间层缓存了一份过期副本。
- 修法:直接读底层,不看中间层。
- 涉及事实:见 `params/soc-x.md`
```

**`params/soc-x.md`: the values, each with its evidence.**

<!-- excerpt: examples/good-skill/params/soc-x.md -->
| 参数 | 值 | 来源 · 日期 | 验证方式 · 实测 | 复现记录 | 置信度 |
|---|---|---|---|---|---|
| 存储起始位置 | `SLOT_A` | commit 1a2b3c4d · 2026-08-01 | 读回比对 · 实测:通过 2026-09-01 | 2026-08-01 · commit 1a2b3c4d; 2026-09-01 · commit 5e6f7a8b | high |
| 读回起始地址 | `0x1A40` | commit 1a2b3c4d · 2026-08-01 | 读回比对 · 实测:通过 2026-09-01 | 2026-08-01 · commit 1a2b3c4d | med |

| Column | What it holds | First row |
|---|---|---|
| 参数 · parameter | what the value is | storage start |
| 值 · value | the value, true on this platform only | `SLOT_A` |
| 来源 · 日期 · source · date | the commit it came from, and the day | commit 1a2b3c4d · 2026-08-01 |
| 验证方式 · 实测 · check · tested | how to re-check it, and whether that was actually run | read back and compare · passed 2026-09-01 |
| 复现记录 · reproductions | every later confirmation, one line each | 2 lines |
| 置信度 · confidence | computed from the two columns before it, never typed by feel | `high` |

The two rows differ for a reason. The first was tested and confirmed twice, so it may say
`high`. The second was tested once, which is enough for `med` on a value. A *method* seen on
one platform stays `low` however well it tested: once does not make it general. The full rule
is [the confidence table](#the-confidence-table-is-a-table-not-a-vibe) below.

<!-- output: whetstone verify examples/good-skill --brief -->
```console
$ whetstone verify examples/good-skill --brief

whetstone verify — examples/good-skill

INFO (2)
  i pitfalls.md:5  [V18] [从上层状态反推底层状态会看错] reproduced on 2 distinct platforms/projects — eligible to move into the SKILL.md L2 body
  i good-skill  [V08d] 2 commit hash(es) cited in 来源 / 复现记录, none checked against git

summary: 0 error(s), 0 warning(s), 2 info
```

No errors, no warnings. The pitfall has been seen on two projects, so it may move up into the
`SKILL.md` body (V18). The commit hashes are made up for the example, so none was looked up
in git (V08d; pass `--repo <git repo>` to check them).

## What a broken one gets

[`examples/demo-skill/`](examples/demo-skill) is the same package with six things broken on
purpose; `diff -r examples/good-skill examples/demo-skill` shows each one. This is the part
of whetstone that says no. Confidence comes from a mechanical table, not from a model's mood;
a lesson seen on one platform cannot enter the skill body; a fact is appended and marked
superseded, never quietly replaced. None of that is a paragraph of documentation: it is
`whetstone verify`, exit code and all.

<!-- output: whetstone verify examples/demo-skill --brief -->
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

INFO (1)
  i demo-skill  [V08d] 2 commit hash(es) cited in 来源 / 复现记录, none checked against git

summary: 5 error(s), 3 warning(s), 1 info
```

Six breaks, eight findings. Five refusals, in order: the same platform counted twice to fake
cross-platform evidence · a method claiming `high` on one platform · a reproduction count
written as a number instead of a record · the same again · a platform value claiming `high`
that was never actually tested. Three warnings: a value in the body that belongs in
`params/` · no list of what must never be done · no record of replaced values. Drop
`--brief` and every line gains the rule it came from.

The INFO line is a check that did not run. The demo's commit hashes are made up; pass
`--repo <git repo>` and each one becomes an error (V08c), because a source that cites a commit
nobody can find is no source at all. Without `--repo` the check is skipped, and says so.

Both transcripts are copied from real runs, and the selftest runs them again and fails if
this README no longer matches; the excerpts above are checked against their files the same
way. Field names stay in Chinese because that is what they are called inside the files you
would be editing.

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
bash bin/verify_selftest.sh                       # 139 assertions across 40 checks
bash bin/verify_mutation_test.sh                  # delete each check; the suite must go red
./cli/whetstone verify examples/good-skill --brief
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

A mutation can also fail to apply, when the anchor text it edits has drifted. That entry then
proves nothing, and counting it as neither caught nor missed kept the run green while one
check quietly stopped being tested. It now has its own counter and fails the run — verified
by breaking an anchor on purpose and watching the suite go red.

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
whetstone verify <pkg> --repo <dir> # also: every commit the provenance cites must exist there
whetstone verify --explain          # all 40 checks, their limits, and what is left to humans
whetstone lint --src ~/skills       # selection-menu hygiene: overlaps, collisions, vague descriptions,
                                    # and whether the whole menu fits (menu-snapshot | lint --listing -)
whetstone index --src ~/skills      # grouped catalog
whetstone promote <proposal>        # install a proposal, refusing to overwrite an existing skill
whetstone pack | deploy             # move a library between machines
whetstone sync engram <skill>       # optional: push one skill into a local engram memory store
whetstone decision add …            # record what you decided about a proposal, and why
whetstone decision stats            # what those decisions have started to point at
whetstone decision alias --from … --to …   # fold two spellings of one meaning together
whetstone find "<what you are about to do>"  # which skills fit; says so plainly when none does
whetstone route events | whetstone route learn --events -   # learn from past sessions how you ask
whetstone route replay --events <file>      # score a routing change on past sessions, in time order
whetstone route plan --project <dir>        # Claude Code: let skills used elsewhere yield (prints; --write merges)
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

`find` and `route` guard **reach**: past a certain size a library no longer fits the menu a
runtime shows the model, and the entries that lose their descriptions stop being picked on
topic (on one machine, 26% with a description, 1% without). Routing keeps the menu short with
switches the runtime already has, answers the rest with one search command any agent can run,
and learns from past sessions — no hooks. The core reads only a neutral event format, so each
agent runtime needs an adapter: **Claude Code's is built and tested; Codex, opencode, pi,
Gemini CLI and Cursor are designed from their source and not written yet.** See the
[routing page](https://doc.tbusos.com/whetstone/routing.html) and
[`spec/routing.md`](spec/routing.md).

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
spec/routing.md                     experience routing: three layers, the neutral event format, six runtimes
commands/                           /distill and /promote slash-command definitions
bin/verify.py                       evidence discipline, executable
bin/verify_selftest.sh              139 assertions, both directions, coverage-enforced; replays README quotes
bin/verify_mutation_test.sh         deletes each check in turn; the suite must go red
bin/decision.py                     the review-decision log (record only; 46 assertions)
bin/decision_mutation_test.sh       deletes each decision check; the suite must go red
bin/lint.py · bin/index.py          selection-menu hygiene, incl. whether the whole menu fits
bin/lint_selftest.sh                65 assertions, both directions; lint_mutation_test.sh breaks 41 checks
bin/route.py                        routing core: find / learn / usage / replay / elsewhere (runtime-neutral)
bin/route_selftest.sh               73 assertions, both directions; route_mutation_test.sh breaks 57 rules
bin/pack.sh · bin/deploy.sh · bin/promote.sh   move and install packages
cli/whetstone                       runtime-agnostic CLI, pure bash
templates/                          skeletons for a distilled skill / params / pitfalls
examples/good-skill/                a correct package: the walkthrough at the top
examples/demo-skill/                the same package with six things broken, behind the verify demo
inbox/ · journal/                   proposals awaiting review; mined source material
adapters/capture · adapters/sync    optional: session capture, optional sinks
adapters/menu                       the menu a runtime actually sent, and its sessions as neutral events (Claude Code)
adapters/levers                     a runtime's own menu switches, set from what routing learned (Claude Code)
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
