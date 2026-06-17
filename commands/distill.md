---
description: "Run Cangjie on the current dev session — mine transcript + git diff + pitfalls, layer L1-L4, reconcile against existing skills, write a reviewed proposal into inbox/. Trigger: 蒸馏这次 / distill this session / 把这次经验做成 skill."
---

# /distill

Execute `SKILL.md` (Phase 0 → 5) of the cangjie skill against the current session.

- **Inputs**: current session transcript, git range (ask if unclear), `journal/` entries.
- **Output**: a proposal diff written to `inbox/`, plus the two human-review
  checkpoints (Phase 2.5 = 挖得对吗/分得对吗, Phase 5 = 入不入库).
- **Does NOT** touch the live skill library — that is `/promote`, after you approve.
- **Self-contained**: spawns an independent subagent for the Phase 4 quality check
  (extraction-framework §8/§9). No external repo required.
