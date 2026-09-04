---
description: "Promote an approved whetstone proposal from inbox/ into the live skill library. Human gate already passed in /distill. Trigger: 入库 / promote proposal / 把提案合进 skill 库."
---

# /promote

Apply an approved `inbox/` proposal to the live skill library.

1. Show the proposal diff one last time.
2. Apply: add new skills / merge L2 / supersede facts —
   **append + mark, NEVER silent overwrite** (especially safety / irreversible facts).
3. Apply reproduction write-backs (§7): for each approved 印证 item, append a line to the
   target entry's 复现记录 — or just refresh the date if that platform/project already has a line.
   If the union now reaches 2 distinct platform/project lines, re-judge per the §7 table
   (L2 promotion / confidence bump).
4. Update `params/<platform>.md` tables.
5. Keep the original provenance (the `journal/` entry for /distill proposals; the
   来源成员 · commit markers for whetstone-curator fetch proposals).
6. Record the review decisions — one `whetstone decision add` per proposal item, for the
   rejected and amended ones as much as the accepted ones. A rejection you do not record
   is one the next distillation will propose again, word for word, and you will spend the
   same judgement twice. Format and limits: `spec/review-decisions.md`.

🔴 Only run after you approved the proposal — in `/distill` Phase 5, or in a
whetstone-curator fetch report (same shape, same gate).
