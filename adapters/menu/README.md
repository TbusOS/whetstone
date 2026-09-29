# Menu adapters

`whetstone lint` can estimate how big a library's skill menu is. Which skills the runtime
then shows with their description, and which as a bare name, is the runtime's decision
and is not fully documented. A menu adapter prints the menu a runtime **actually sent**,
so `lint --listing` can say which skills lost their descriptions and which show something
other than what their SKILL.md says.

Output format, the same for every runtime: one entry per line, `- name: description`, or
`- name` when the description was dropped. A description with a line break in it
continues on the following lines (they do not start with `- `).

| Runtime | Adapter | Where the menu comes from |
|---|---|---|
| Claude Code | `claude-code.py` | the latest `skill_listing` attachment with `isInitial: true` in `~/.claude/projects/*/*.jsonl` (records without it are mid-session deltas and are skipped) |
| others | — | write one that prints the format above |

```bash
whetstone menu-snapshot | whetstone lint --listing -
python3 adapters/menu/claude-code.py --session <id>   # one session's menu
whetstone menu-snapshot --events                       # this session's skill events, by name
```

`--events` exists because the UI prints only a count ("1 skill available"). Two kinds of
event look alike there and are not the same thing:

- **menu**: the runtime (re)sent a skill's name and description — the full menu at session
  start, or a delta when a SKILL.md was installed or edited. Nothing of the body is in
  context yet.
- **loaded**: the body entered the context — a `Skill` tool call, a `Read` of a SKILL.md,
  or the replay of already-loaded skills after the conversation was compacted.

The last line lists every skill loaded in the session. Without `--session` it reads the
session named by `$CLAUDE_CODE_SESSION_ID` (Claude Code sets it for the commands it runs);
without that, the session written to most recently, which with several sessions open may
be another one.

Tested by `bin/lint_selftest.sh` (the adapter section) and `bin/lint_mutation_test.sh`.
