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
```

Tested by `bin/lint_selftest.sh` (the adapter section) and `bin/lint_mutation_test.sh`.
