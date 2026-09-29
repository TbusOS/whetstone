# CLI · `whetstone`

A runtime-agnostic command-line entry point so Whetstone is usable outside an
agent runtime (CI, scripting, muscle memory). Pure bash, zero deps, paths
resolved relative to the repo — clone anywhere and run.

```bash
./cli/whetstone help
# or put it on PATH:
ln -s "$PWD/cli/whetstone" ~/.local/bin/whetstone
```

## Commands

| Command | Wraps | What it does |
|---|---|---|
| `whetstone pack [--src D] [--out F] [--only a,b]` | `bin/pack.sh` | package a skill library → tarball + MANIFEST |
| `whetstone deploy <pack.tar.gz> [--dest D] [--force]` | `bin/deploy.sh` | install a pack into a skills dir (collision-safe) |
| `whetstone promote <proposal> [--list] [--dry-run] [--force]` | `bin/promote.sh` | apply an approved `inbox/` proposal to the live library |
| `whetstone sync engram <skill> [--dry-run]` | `adapters/sync/engram.sh` | push a skill into engram (optional sink) |
| `whetstone lint [--src D] [--strict] [--json] [--listing F\|-] [--menu-budget N] [--menu-reserve N]` | `bin/lint.py` | flag empty / overlapping / colliding skill descriptions, and whether the whole menu fits its budget |
| `whetstone menu-snapshot [--session ID]` | `adapters/menu/claude-code.py` | print the menu Claude Code last sent; pipe it to `lint --listing -` |
| `whetstone menu-snapshot --events [--session ID]` | `adapters/menu/claude-code.py` | one session's skill events by name: menu updates (the UI's "N skill available") vs real loads |
| `whetstone lint-selftest` / `lint-mutation` | `bin/lint_selftest.sh` / `bin/lint_mutation_test.sh` | lint selftest; break each menu check, the selftest must go red |
| `whetstone index [--src D] [--out F]` | `bin/index.py` | generate a grouped `INDEX.md` catalog |
| `whetstone capture [--clean]` | `adapters/capture/claude-code.sh` | the Claude Code session journaler |
| `whetstone selftest` | `adapters/capture/selftest.sh` | run the capture-hook selftest |
| `whetstone journal` | — | list captured sessions |
| `whetstone version` / `help` | — | — |

## Why `distill` is NOT a CLI command

Mining the transcript + git diff and layering into L1–L4 is **agent work** — it
needs a model in the loop. The CLI refuses to fake it: `whetstone distill` prints
a pointer to invoke the `/distill` skill (or run `SKILL.md` Phase 0–5) instead.
The CLI owns the deterministic steps *around* distillation: `promote` / `pack` /
`deploy` / `sync`.

This keeps the boundary honest — runtime-neutral scripting for the mechanical
parts, agent runtime for the judgement parts.

## Index hygiene (`lint` / `index`)

The skill **selection menu** = every skill's `name` + `description`, always in the
agent's context. As the library grows, vague or overlapping descriptions make the
model pick the wrong skill or miss the right one. `lint` checks that menu against the
description contract (extraction-framework §13): missing triggers, overlapping trigger
sets, name near-collisions (e.g. `foo-review` vs `foo-review-framework`). `index`
emits a grouped `INDEX.md` for humans. Run `lint` after adding or editing any skill.

Descriptions can each be fine and still not fit together. The menu has a budget set by
the runtime; over it, the runtime keeps every name but drops descriptions, and a skill
shown by name alone is almost never picked from its triggers (measured on one library:
26% of trigger-word messages loaded the skill when its description was in the menu, 1%
when only its name was). `lint` adds up the menu, compares it with `--menu-budget`
(default 25000 chars, Claude Code as measured in 2026-09), and when it is over prints the
fair share per description and which descriptions to trim first. To see what the runtime
actually did, feed it the real menu:

```bash
whetstone menu-snapshot | whetstone lint --listing -   # which skills are name-only right now
```

