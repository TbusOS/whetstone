<!-- Keep this short. Delete rows that do not apply. -->

**What changed and why**


**If this adds or changes a check in `verify`**

- [ ] Published in `--explain`, including where it is narrower than the rule it serves
- [ ] Selftest asserts **both** directions (fires on a defective fixture, quiet on a clean one)
- [ ] Mutation entry added — deleting the logic makes the suite fail
- [ ] The fixture is discriminating: with the logic removed, the assertion would *not*
      still pass for some unrelated reason

**If this changes a rule in the framework or spec**

- [ ] Said below which of `SKILL.md` / `spec/` / `templates/` / `verify` were updated,
      and which were deliberately left alone

**Checks run**

```
bash bin/verify_selftest.sh          →
bash bin/verify_mutation_test.sh     →
bash adapters/capture/selftest.sh    →
bash autoupdate/selftest.sh          →
```

<!-- Pages under docs/ also need: ~/.claude/skills/design-review/dr-cli docs/<page>.html -->
