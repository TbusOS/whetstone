#!/usr/bin/env python3
"""whetstone decision — record what the human reviewer actually decided.

Every other artefact in this repo records what went INTO the library. None records
what the reviewer did to the proposal on the way in: accepted as proposed, moved to
another layer, downgraded the confidence, rejected outright. Those judgements are
the only free-of-charge labels this tool produces — each one says where the
framework's judgement and the reviewer's judgement diverged — and until now every
one of them was thrown away at the end of the session.

That matters because the framework itself has never evolved from its own history.
§7 (2026-08-24) and §14 (2026-09-04) both came from outside reading plus a human
call. Nothing here could have proposed them, because the raw material did not exist.

This command only RECORDS. It proposes no change, edits no rule, and decides
nothing. Analysis comes later, and only when there is enough to analyse.

It also records use-time conflicts (spec/use-time-conflicts.md): an agent, while
working, finds a library entry disagreeing with the code or with a fresh reading.
Both judgements are kept — the AI's (type / evidence / action / certainty) and the
human's final call — so `stats` can score the AI per group and say how that group
may be ASKED next time: in full, as a one-line summary, or in a batch at the end of
the task. No tier ever means "not asked". Nothing here edits an entry; a human yes
is still the only way an entry changes.

They are written in two steps, because the party being scored is the one writing
the record. Written in one line after the answer, the AI's "own" call could simply
be copied from the human's, and agreement would read 100% with nothing on screen
to say so. So `report` puts the AI's call on file first and prints a fingerprint
the conflict card must carry — the card cannot exist before the record does — and
`resolve` appends the answer afterwards. A report is never rewritten; a second
report of the same entry in the same source is flagged, and the FIRST call is the
one scored.

  bin/decision.py add --subject "..." --verdict amend --reason "..." [--tag ...]
  bin/decision.py report --entry skill/item --ai-type stale --ai-evidence seen \
                         --ai-action update --ai-certainty high \
                         --subject "..." --reason "why the AI thinks so" --source <session>
                                   step 1: the AI's call, BEFORE the human is asked
  bin/decision.py resolve --conflict-id C-YYYYMMDD-NN --verdict amend --final-type scope \
                          --reason "..."
                                   step 2: the human's answer
  bin/decision.py miss --entry skill/item --final-type wrong --verdict accept \
                       --subject "..." --reason "you found it; the AI used it silently"
  bin/decision.py exam --result pass|fail --reason "..."
                                   one sitting of the known-answer exam (spec §8)
  bin/decision.py stats            what the accumulated decisions point at
  bin/decision.py list [-n N]      the most recent records
  bin/decision.py alias --from X --to Y --reason "..."
                                   declare that two tags were the same thing
  bin/decision.py aliases          which tags are currently folded into which

Tags only accumulate signal when the same meaning keeps getting the same string.
Write it `priority-wrong` once and `priority-mistake` the next time and one signal
becomes two rows of one, forever short of the threshold, with nothing on screen to
say so. Two mechanisms answer that, and neither of them guesses at meaning:

  before  — `add` puts the existing vocabulary in front of you when you introduce a
            new tag, so reusing one is easier than inventing one.
  after   — `alias` folds two tags together at read time. The stored lines never
            change (§11: append, never overwrite) and `stats` prints every fold it
            applied, so a merge is always visible and always reversible.

Deliberately absent: any "did you mean X?" guess. Measured on this vocabulary, no
string-similarity threshold works — 0.72 misses priority-wrong/priority-mistake
(0.60) while 0.60 wrongly pairs missing-feature/missing-split (0.643); word order
(layer-wrong/wrong-layer, 0.455) and language (priority-wrong/排序判断错, 0.0)
defeat it outright. Similarity is used to ORDER the vocabulary shown, never to
judge — a wrong order costs a glance, a wrong merge costs the signal.

Records land in journal/review-decisions.jsonl — git-ignored, because they quote
your real library. stdlib only, runtime-neutral.
"""
import os
import sys
import re
import json
import argparse
import datetime
import difflib
import hashlib
import math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_FILE = os.path.join(REPO_DIR, "journal", "review-decisions.jsonl")

# A tag reaching this many DISTINCT sources stops looking like a one-off and starts
# looking like the framework being unclear. Distinct sources, never raw lines: one
# session rejecting five entries for the same reason is one signal, not five — the
# same trap §7 closed for 复现记录 by keying on platform/project.
#
# The 3 is a guess. It is exactly the kind of number this file exists to calibrate:
# in the framework's own L1-L4 terms a threshold is L3, and L3 is what evidence is
# allowed to change. Do not defend it — replace it once the records can.
SIGNAL_MIN = 3

VERDICTS = ("accept", "amend", "reject", "defer")
KINDS = ("entry", "framework")

# --- use-time conflicts (spec/use-time-conflicts.md) -------------------------------
CONFLICT_TYPES = ("stale", "scope", "wrong", "code-regress", "clash")
FINAL_TYPES = CONFLICT_TYPES + ("none",)      # none = it was never a conflict
EVIDENCE = ("seen", "inferred", "unseen")
AI_ACTIONS = ("update", "variant", "supersede", "keep", "ask")
CERTAINTY = ("high", "med", "low")
CONFLICT_ID = re.compile(r"^C-\d{8}-\d{2,}$")
# records that are events, not decisions: they carry no verdict of their own
EVENT_KINDS = ("exam", "conflict-report")

# Every number below is a guess, exactly like SIGNAL_MIN: L3 in the framework's own
# terms, waiting for this file to calibrate it. Do not defend them.
DELTA = 0.1              # the lower bound holds with probability 1 - DELTA
TIER_SUMMARY = 0.90      # lower bound before a group may be asked as a one-line summary
TIER_BATCH = 0.95        # ... before it may be asked in a batch at the end of the task
GUESS_SHARE_MAX = 0.30   # above this share of inferred+unseen, no group is relaxed
ENTRY_REVIEW_MIN = 2     # distinct sources in conflict before an entry is marked for review
CALIB_MIN = 5            # per-certainty sample before the calibration comparison is voiced

# Starter tags. NOT a closed set: an unknown tag is written through and reported by
# `stats`, so the vocabulary grows on purpose rather than silently. Keep this list
# and spec/review-decisions.md in step.
KNOWN_TAGS = {
    "layer-wrong":    "分层判错(该 L2 的放了 L1,等等)",
    "conf-too-high":  "置信度标高了",
    "evidence-thin":  "证据不够(复现次数 / 验证方式)",
    "not-general":    "单平台的东西被当成了通用规律",
    "too-specific":   "具体值混进了正文,该降 L3",
    "too-abstract":   "抽得太干,步骤没法照着做",
    "missing-split":  "坑没拆成教训 + 事实两片",
    "duplicate":      "库里已经有了",
    "out-of-scope":   "不属于这个 skill",
    "stale":          "已经过期",
    "missing-feature":"框架整个缺这一类要求",
    "other":          "以上都不是(理由里写清)",
}

ABS_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def lower_bound(k, n, delta=DELTA):
    """One-sided exact (Clopper-Pearson) lower bound on a rate after k of n.

    Not k/n. After a handful of records the point estimate overstates what is known:
    Trust or Escalate (arXiv 2407.18370, Tab.2) set its thresholds from the sample
    rate and met its target only 47.5% of the time. At delta=0.1 the bound gives
    10/10 -> 0.794, 18/20 -> 0.755, 22/22 -> 0.901, 45/45 -> 0.950; the selftest pins
    those four, so a rewrite that drifts from them goes red.
    """
    if n <= 0 or k <= 0:
        return 0.0

    def tail(p):                      # P(X >= k), X ~ Binomial(n, p)
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))

    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if tail(mid) < delta:
            lo = mid
        else:
            hi = mid
    return lo


def fingerprint(rec):
    """Six hex digits over the AI's call exactly as first written.

    `report` prints it and the conflict card must carry it, so the card cannot exist
    before the record does: the call is on file before the human answers. It is
    recomputed on every read, so a report line edited afterwards stops matching and
    is not scored (§11: append, never overwrite).
    """
    fields = [rec.get(f) for f in ("conflict_id", "entry", "ai_type", "ai_evidence",
                                   "ai_action", "ai_certainty", "reported_at")]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode("utf-8")).hexdigest()[:6]


def next_conflict_id(recs, date):
    day = date.replace("-", "")
    nums = [int(r["conflict_id"].rsplit("-", 1)[1]) for r in recs
            if r.get("kind") == "conflict-report" and CONFLICT_ID.match(r.get("conflict_id", ""))
            and r["conflict_id"].startswith(f"C-{day}-")]
    return f"C-{day}-{(max(nums) + 1 if nums else 1):02d}"


def check_final(final_type, ai_type, verdict):
    """The human's type against the AI's. Returns an error or None."""
    if final_type and final_type not in FINAL_TYPES:
        return f"--final-type must be one of {'/'.join(FINAL_TYPES)}"
    final = final_type if final_type != ai_type else ""
    if final == "none" and verdict != "reject":
        return "--final-type none means there was no conflict; the verdict for that is reject"
    if final and final != "none" and verdict == "accept":
        return ("verdict accept means the AI's type stood; a changed type is amend "
                "(or reject, if the entry was kept)")
    return None


def append(path, rec):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load(path):
    """Read the log. A corrupt line is reported, never silently skipped — a counter
    that quietly drops records is worse than no counter."""
    out, bad = [], []
    if not os.path.isfile(path):
        return out, bad
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if not isinstance(rec, dict):
                    raise ValueError("not an object")
                out.append(rec)
            except (ValueError, TypeError) as e:
                bad.append((n, str(e)))
    return out, bad


def alias_map(recs):
    """from -> to, latest record wins.

    A record whose `from` equals its `to` cancels any earlier alias for that tag —
    that is §11 applied here: a later line overrides an earlier one and nothing
    already written is edited.
    """
    m = {}
    for r in recs:
        if r.get("kind") != "alias":
            continue
        f, t = r.get("from"), r.get("to")
        if not f or not t:
            continue
        if f == t:
            m.pop(f, None)
        else:
            m[f] = t
    return m


def canonical(tag, amap):
    """Follow the alias chain. Returns (canonical_tag, hit_cycle).

    On a cycle it refuses to fold and returns the tag untouched. Picking a winner
    inside a cycle would be arbitrary AND invisible; leaving the tags apart is
    wrong in the direction you can see — the counts stay split and `stats` says why.
    """
    seen = [tag]
    cur = tag
    while cur in amap:
        cur = amap[cur]
        if cur in seen:
            return tag, True
        seen.append(cur)
    return cur, False


def tags_in_use(recs):
    used = {}
    for r in recs:
        t = r.get("tag")
        if t:
            used[t] = used.get(t, 0) + 1
    return used


def show_vocabulary(new_tag, recs, limit=8):
    """Put the vocabulary in front of the writer at the one moment reuse is still
    free — before the new spelling exists.

    Ordered by string similarity so a likely match sits near the top. That is
    ORDERING, not judgement: the whole list prints either way, so a bad order costs
    a glance, whereas a "did you mean X?" that guesses wrong costs the signal. The
    measurements in the module docstring are why no such guess is offered.
    """
    used = tags_in_use(recs)
    known = set(KNOWN_TAGS) | set(used)
    if not known:
        return
    ranked = sorted(known,
                    key=lambda t: (-difflib.SequenceMatcher(None, new_tag, t).ratio(), t))
    print(f"  {new_tag!r} is not in the vocabulary yet. What is already there:")
    for t in ranked[:limit]:
        seen = f"   [{used[t]} record(s)]" if t in used else ""
        print(f"      {t:<17} {KNOWN_TAGS.get(t, '')}{seen}")
    if len(ranked) > limit:
        print(f"      … and {len(ranked) - limit} more — `decision tags` lists the vocabulary")
    print("  If one of those is the same thing, use it instead: a meaning split across")
    print("  two spellings never reaches the threshold, and nothing on screen says so.")
    print("  If it really is new, keep it — and once it recurs, add it to KNOWN_TAGS")
    print("  and spec/review-decisions.md. Already written both ways?")
    print("  `decision alias --from <old> --to <keep>` folds them at read time,")
    print("  without touching a single stored line.")


def cmd_alias(args):
    """Declare that two tags were the same thing. Read-time only, by design."""
    if not args.frm or not args.to:
        print("--from and --to are both required", file=sys.stderr)
        return 2
    if not args.reason.strip():
        print("--reason is required: folding two tags is a judgement, and the next "
              "person to read stats deserves to see what it was", file=sys.stderr)
        return 2
    date = args.date or datetime.date.today().isoformat()
    if not ABS_DATE.match(date):
        print(f"date must be absolute YYYY-MM-DD, got {date!r}", file=sys.stderr)
        return 2

    recs, _ = load(args.file)
    amap = alias_map(recs)
    if args.frm == args.to:
        if args.frm not in amap:
            print(f"{args.frm!r} is not folded into anything — nothing to cancel",
                  file=sys.stderr)
            return 2
    else:
        probe = dict(amap)
        probe[args.frm] = args.to
        _, cyc = canonical(args.frm, probe)
        if cyc:
            print(f"refused: {args.frm!r} -> {args.to!r} closes a loop with the aliases "
                  f"already recorded. Cancel one of them first "
                  f"(`alias --from X --to X`).", file=sys.stderr)
            return 2

    rec = {"date": date, "kind": "alias", "from": args.frm, "to": args.to,
           "reason": args.reason.strip()}
    if args.source:
        rec["source"] = args.source
    os.makedirs(os.path.dirname(args.file), exist_ok=True)
    with open(args.file, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    if args.frm == args.to:
        print(f"alias cancelled: {args.frm!r} now stands on its own again")
    else:
        print(f"alias recorded: {args.frm!r} -> {args.to!r}")
        print("  Stored lines are unchanged; stats folds the counts and prints the fold.")
    return 0


def cmd_aliases(args):
    recs, bad = load(args.file)
    for n, err in bad:
        print(f"  ! line {n} is not valid JSON ({err}) — not counted", file=sys.stderr)
    amap = alias_map(recs)
    if not amap:
        print("no aliases in effect — every tag counts as itself")
        return 0
    print("aliases in effect (applied when reading, never to the stored lines):")
    for f in sorted(amap):
        canon, cyc = canonical(f, amap)
        note = "  ← LOOP: not folded, counts stay split" if cyc else ""
        print(f"  {f}  ->  {amap[f]}" + (f"  (resolves to {canon})" if canon != amap[f] else "") + note)
    return 0


def cmd_add(args):
    if args.verdict not in VERDICTS:
        print(f"verdict must be one of {'/'.join(VERDICTS)}", file=sys.stderr)
        return 2
    if args.kind == "conflict":
        # the one-line form would let the scored party write its own call after
        # hearing the answer — so it does not exist
        print("use-time conflicts are recorded in two steps: `decision report` (the AI's "
              "call, before asking) then `decision resolve` (the answer). A conflict the "
              "AI did not report is `decision miss`.", file=sys.stderr)
        return 2
    if args.kind not in KINDS:
        print(f"kind must be one of {'/'.join(KINDS)}", file=sys.stderr)
        return 2
    date = args.date or datetime.date.today().isoformat()
    if not ABS_DATE.match(date):
        # §7's rule, applied to this file: a relative date cannot be compared later,
        # which is the only thing this log is for.
        print(f"date must be absolute YYYY-MM-DD, got {date!r}", file=sys.stderr)
        return 2
    if not args.reason.strip():
        print("--reason is required and cannot be blank: the tag says WHICH bucket, "
              "the reason says what actually happened", file=sys.stderr)
        return 2

    prior, _ = load(args.file)
    rec = {"date": date, "kind": args.kind, "source": args.source,
           "subject": args.subject, "verdict": args.verdict, "reason": args.reason.strip()}
    for key, val in (("skill", args.skill), ("action", args.action),
                     ("layer", args.layer), ("conf", args.conf),
                     ("final_layer", args.final_layer), ("final_conf", args.final_conf),
                     ("section", args.section), ("tag", args.tag)):
        if val:
            rec[key] = val

    os.makedirs(os.path.dirname(args.file), exist_ok=True)
    with open(args.file, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"recorded: [{rec['verdict']}] {rec['subject']}")
    if args.tag:
        # read the log as it was BEFORE this line, so the tag just written does not
        # count as prior use of itself
        canon, cyc = canonical(args.tag, alias_map(prior))
        if cyc:
            print(f"  note: {args.tag!r} sits in an alias loop, so it is not folded. "
                  f"`decision aliases` shows the loop.")
        elif canon != args.tag:
            print(f"  note: {args.tag!r} is folded into {canon!r} by an alias record — "
                  f"stats counts it there. The line is stored exactly as you typed it.")
        elif args.tag not in KNOWN_TAGS and args.tag not in tags_in_use(prior):
            show_vocabulary(args.tag, prior)
    return 0


def cmd_list(args):
    recs, bad = load(args.file)
    for n, err in bad:
        print(f"  ! line {n} is not valid JSON ({err}) — not counted", file=sys.stderr)
    if not recs:
        print(f"no records yet in {args.file}")
        return 0
    for r in recs[-args.n:]:
        if r.get("kind") == "alias":
            arrow = "cancelled" if r.get("from") == r.get("to") else f"-> {r.get('to')}"
            print(f"{r.get('date', '?')}  [alias]  {r.get('from')} {arrow}")
            print(f"            {r.get('reason', '')}")
            continue
        if r.get("kind") == "exam":
            print(f"{r.get('date', '?')}  [exam {r.get('result', '?')}]")
            print(f"            {r.get('reason', '')}")
            continue
        if r.get("kind") == "conflict-report":
            flags = "".join(f"  [{f}]" for f in ("safety", "blocking") if r.get(f))
            print(f"{r.get('date', '?')}  [report]  {r.get('conflict_id', '?')} · "
                  f"{r.get('fingerprint', '?')}  {r.get('entry', '?')}  {r.get('ai_type', '?')} "
                  f"({r.get('ai_evidence', '?')}, {r.get('ai_certainty', '?')}){flags}")
            print(f"            AI: {r.get('ai_reason', '')}")
            continue
        if r.get("kind") == "conflict-resolve":
            final = r.get("final_type") or "type stood"
            print(f"{r.get('date', '?')}  [{r.get('verdict', '?')}]  {r.get('conflict_id', '?')}"
                  f"  → {final}")
            print(f"            {r.get('reason', '')}")
            continue
        if r.get("kind") == "conflict-miss":
            print(f"{r.get('date', '?')}  [{r.get('verdict', '?')}]  MISSED  "
                  f"{r.get('entry', '?')} — you found it: {r.get('final_type', '?')}")
            print(f"            {r.get('reason', '')}")
            continue
        tag = f" #{r['tag']}" if r.get("tag") else ""
        moved = ""
        if r.get("final_layer") and r.get("final_layer") != r.get("layer"):
            moved = f"  {r.get('layer', '?')}→{r['final_layer']}"
        if r.get("final_conf") and r.get("final_conf") != r.get("conf"):
            moved += f"  {r.get('conf', '?')}→{r['final_conf']}"
        print(f"{r.get('date', '?')}  [{r.get('verdict', '?')}]{tag}{moved}  "
              f"{r.get('subject', '')}")
        print(f"            {r.get('reason', '')}")
    return 0


def cmd_exam(args):
    """Record one sitting of the known-answer exam (spec §8 ②).

    The exam itself — a few conflicts whose answers are known, including a
    code-regress trap and a case whose right answer is "cannot tell" — lives outside
    this tool. Only the result is kept here, because `stats` relaxes no group until
    the latest sitting is a pass.
    """
    if args.result not in ("pass", "fail"):
        print("--result must be pass or fail", file=sys.stderr)
        return 2
    if not args.reason.strip():
        print("--reason is required: which questions, which model, what was got wrong",
              file=sys.stderr)
        return 2
    date = args.date or datetime.date.today().isoformat()
    if not ABS_DATE.match(date):
        print(f"date must be absolute YYYY-MM-DD, got {date!r}", file=sys.stderr)
        return 2
    rec = {"date": date, "kind": "exam", "result": args.result, "reason": args.reason.strip()}
    if args.source:
        rec["source"] = args.source
    os.makedirs(os.path.dirname(args.file), exist_ok=True)
    with open(args.file, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"recorded: exam {args.result}")
    if args.result == "fail":
        print("  every group is back on full confirmation until a later sitting passes")
    return 0


def cmd_report(args):
    """Step 1 of 2: the AI's own call, written BEFORE the human is asked.

    Prints the conflict id and a fingerprint; the conflict card shown to the human
    must carry both (spec §5). A call once written is never rewritten.
    """
    for flag, val, allowed in (("--ai-type", args.ai_type, CONFLICT_TYPES),
                               ("--ai-evidence", args.ai_evidence, EVIDENCE),
                               ("--ai-action", args.ai_action, AI_ACTIONS),
                               ("--ai-certainty", args.ai_certainty, CERTAINTY)):
        if val not in allowed:
            print(f"{flag} must be one of {'/'.join(allowed)}", file=sys.stderr)
            return 2
    if not args.entry.strip():
        print("--entry is required (<skill>/<item>)", file=sys.stderr)
        return 2
    if not args.reason.strip():
        print("--reason is required: the card says why the AI thinks so, and so must the "
              "record", file=sys.stderr)
        return 2
    now = datetime.datetime.now()
    date = now.date().isoformat()
    recs, _ = load(args.file)
    cid = args.conflict_id or next_conflict_id(recs, date)
    if not CONFLICT_ID.match(cid):
        print(f"--conflict-id must look like C-YYYYMMDD-NN, got {cid!r}", file=sys.stderr)
        return 2
    if any(r.get("kind") == "conflict-report" and r.get("conflict_id") == cid for r in recs):
        print(f"refused: {cid} is already on record. A call, once written, is not "
              f"rewritten — if the situation changed, report it as a new conflict.",
              file=sys.stderr)
        return 2
    rec = {"date": date, "kind": "conflict-report", "conflict_id": cid,
           "reported_at": now.isoformat(timespec="seconds"), "entry": args.entry.strip(),
           "ai_type": args.ai_type, "ai_evidence": args.ai_evidence,
           "ai_action": args.ai_action, "ai_certainty": args.ai_certainty,
           "subject": args.subject, "ai_reason": args.reason.strip(),
           "blocking": bool(args.blocking), "safety": bool(args.safety)}
    for key, val in (("entry_source", args.entry_source), ("source", args.source)):
        if val:
            rec[key] = val
    rec["fingerprint"] = fingerprint(rec)
    append(args.file, rec)
    print(f"reported {cid} · fingerprint {rec['fingerprint']}")
    print("  Put this line in the conflict card BEFORE asking. Record the answer with")
    print(f"  `decision resolve --conflict-id {cid} --verdict ... --reason ...`.")
    return 0


def cmd_resolve(args):
    """Step 2 of 2: the human's answer to a report already on file."""
    if args.verdict not in VERDICTS:
        print(f"verdict must be one of {'/'.join(VERDICTS)}", file=sys.stderr)
        return 2
    if not args.reason.strip():
        print("--reason is required: what the human decided, and why", file=sys.stderr)
        return 2
    date = args.date or datetime.date.today().isoformat()
    if not ABS_DATE.match(date):
        print(f"date must be absolute YYYY-MM-DD, got {date!r}", file=sys.stderr)
        return 2
    recs, _ = load(args.file)
    rep = next((r for r in recs if r.get("kind") == "conflict-report"
                and r.get("conflict_id") == args.conflict_id), None)
    if rep is None:
        print(f"refused: no report {args.conflict_id!r} on file. The AI's call is recorded "
              f"before the answer — `decision report` first.", file=sys.stderr)
        return 2
    err = check_final(args.final_type, rep.get("ai_type"), args.verdict)
    if err:
        print(err, file=sys.stderr)
        return 2
    same = bool(args.final_type) and args.final_type == rep.get("ai_type")
    earlier = any(r.get("kind") == "conflict-resolve" and r.get("conflict_id") == args.conflict_id
                  for r in recs)
    rec = {"date": date, "kind": "conflict-resolve", "conflict_id": args.conflict_id,
           "resolved_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "verdict": args.verdict, "reason": args.reason.strip()}
    if args.final_type and not same:            # spec §7: same as the AI's -> not stored
        rec["final_type"] = args.final_type
    if args.source:
        rec["source"] = args.source
    append(args.file, rec)
    print(f"resolved {args.conflict_id}: [{args.verdict}] "
          f"{rec.get('final_type', 'type stood')}")
    if same:
        print("  note: --final-type equals the AI's type, so it is not stored (spec §7)")
    if earlier:
        print(f"  note: this overrides the earlier answer to {args.conflict_id} — the latest "
              f"answer counts, the earlier line stays (§11)")
    return 0


def cmd_miss(args):
    """A conflict the AI met and did not report — found by the human, recorded by the AI.

    It carries no AI call because there was none; its type says which group it sends
    back to full confirmation (spec §9).
    """
    if args.final_type not in CONFLICT_TYPES:
        print(f"--final-type must be one of {'/'.join(CONFLICT_TYPES)} — a miss that was "
              f"not a conflict is not a miss", file=sys.stderr)
        return 2
    if args.verdict not in VERDICTS:
        print(f"verdict must be one of {'/'.join(VERDICTS)}", file=sys.stderr)
        return 2
    if not args.entry.strip():
        print("--entry is required (<skill>/<item>)", file=sys.stderr)
        return 2
    if not args.reason.strip():
        print("--reason is required: how it was found", file=sys.stderr)
        return 2
    date = args.date or datetime.date.today().isoformat()
    if not ABS_DATE.match(date):
        print(f"date must be absolute YYYY-MM-DD, got {date!r}", file=sys.stderr)
        return 2
    rec = {"date": date, "kind": "conflict-miss", "entry": args.entry.strip(),
           "final_type": args.final_type, "verdict": args.verdict, "subject": args.subject,
           "reason": args.reason.strip(), "safety": bool(args.safety)}
    if args.source:
        rec["source"] = args.source
    append(args.file, rec)
    print(f"recorded a MISS on {rec['entry']}: {args.final_type} goes back to full "
          f"confirmation (spec §9)")
    return 0


def conflict_items(recs):
    """Join each report with its answer. Returns (items, misses, problems).

    One item per (entry, source). If an entry was reported more than once in one
    source, the FIRST call is the one scored, against the LATEST answer given to any
    of those reports — otherwise a second report written after the answer came in
    would be a way to agree with the human in hindsight.

    Each answer's type is read against its OWN report: "type stood" means that
    report's ai_type, which is not necessarily the first call's.
    """
    problems, reports, report_pos, bad_ids = [], [], {}, set()
    for i, r in enumerate(recs):
        if r.get("kind") != "conflict-report":
            continue
        cid = r.get("conflict_id")
        if cid in report_pos:
            problems.append(f"{cid} is reported twice — only the first line counts")
            continue
        report_pos[cid] = i
        if r.get("fingerprint") != fingerprint(r):
            bad_ids.add(cid)
            problems.append(f"{cid} no longer matches its fingerprint — edited after it was "
                            f"written, so it is not scored (§11)")
            continue
        reports.append((i, r))
    by_id = {r.get("conflict_id"): r for _, r in reports}
    answers = {}
    for i, r in enumerate(recs):
        if r.get("kind") != "conflict-resolve":
            continue
        cid = r.get("conflict_id")
        if cid in bad_ids:
            continue
        if cid not in report_pos or i < report_pos[cid]:
            problems.append(f"an answer to {cid} has no report before it — ignored")
            continue
        answers[cid] = (i, r)                      # the latest answer counts

    groups = {}
    for i, r in reports:
        key = (r.get("entry", "?"), r.get("source") or "__no-source__")
        groups.setdefault(key, []).append((i, r))
    items, rereported = [], 0
    for key, g in groups.items():
        first_i, first = g[0]
        if len(g) > 1:
            rereported += 1
        best = None
        for _, r in g:
            a = answers.get(r.get("conflict_id"))
            if a and (best is None or a[0] > best[0]):
                best = a
        verdict = final = None
        if best:
            ans = best[1]
            verdict = ans.get("verdict")
            final = ans.get("final_type") or by_id[ans.get("conflict_id")].get("ai_type")
        items.append({"pos": first_i, "ai": first, "verdict": verdict, "final": final,
                      "key": key, "id": first.get("conflict_id")})
    items.sort(key=lambda x: x["pos"])
    if rereported:
        problems.append(f"{rereported} entr{'y was' if rereported == 1 else 'ies were'} reported "
                        f"more than once within one source — only the first call is scored")

    misses, seen = [], set()
    for i, r in enumerate(recs):
        if r.get("kind") != "conflict-miss":
            continue
        key = (r.get("entry", "?"), r.get("source") or "__no-source__")
        if key not in seen:
            seen.add(key)
            misses.append((i, r))
    return items, misses, problems


def conflict_section(recs):
    """Spec §8-§9: score the AI's conflict calls and say how each group may be asked.

    "Since the last miss" means the reports written after that miss, so file
    positions are used rather than dates — one day holds many records.
    """
    items, missed, problems = conflict_items(recs)
    if not items and not missed and not problems:
        return
    pending = [x for x in items if x["verdict"] is None]
    print()
    print(f"use-time conflicts — {len(items)} reported by the AI ({len(pending)} awaiting "
          f"your answer), {len(missed)} missed and found by you")
    for p in problems:
        print(f"  ! {p}")

    # Two gates keep a busy-looking loop from relaxing anything (spec §8).
    relax_ok = True
    guesses = sum(1 for x in items if x["ai"].get("ai_evidence") in ("inferred", "unseen"))
    share = guesses / len(items) if items else 0.0
    if share > GUESS_SHARE_MAX:
        relax_ok = False
        print(f"  ! {share:.0%} of reported conflicts rest on inference or on nothing seen "
              f"(> {GUESS_SHARE_MAX:.0%}): no group is relaxed while that holds (spec §8 ①)")
    exams = [r for r in recs if r.get("kind") == "exam"]
    if not exams:
        relax_ok = False
        print("  ! no exam sitting recorded: until one passes, every group stays on full "
              "confirmation (spec §8 ②)")
    elif exams[-1].get("result") != "pass":
        relax_ok = False
        print(f"  ! the last exam sitting ({exams[-1].get('date', '?')}) did not pass: "
              f"every group is back on full confirmation (spec §8 ②)")

    last_miss = {}
    for i, r in missed:
        last_miss[r.get("final_type")] = i

    def judged(x):
        return x["verdict"] is not None and x["verdict"] != "defer" and x["final"] != "none"

    def right(x):
        return x["final"] == x["ai"].get("ai_type")

    groups = {}
    for x in items:
        groups.setdefault((x["ai"].get("ai_type", "?"), x["ai"].get("ai_evidence", "?")),
                          []).append(x)
    if groups:
        print()
        print(f"  {'group':<25} {'judged':>6}  {'type-right':>10}  {'basis':<7} "
              f"{'lower-bound':>11}  {'false-alarm':>11}  ask as")
    for (typ, ev), g in sorted(groups.items()):
        all_j = [x for x in g if judged(x)]
        cut = last_miss.get(typ, -1)
        basis = [x for x in g if x["pos"] > cut and judged(x)]
        k = sum(1 for x in basis if right(x))
        lb = lower_bound(k, len(basis))
        alarms = sum(1 for x in g if x["final"] == "none")
        if ev != "seen":
            tier = "full (nothing seen to show)"
        elif not relax_ok:
            tier = "full (gate above)"
        elif lb >= TIER_BATCH:
            tier = "batch"
        elif lb >= TIER_SUMMARY:
            tier = "summary"
        else:
            tier = "full"
        since = "  (basis: after the last miss)" if cut >= 0 else ""
        print(f"  {typ + ' × ' + ev:<25} {len(all_j):>6}  "
              f"{sum(1 for x in all_j if right(x)):>10}  {f'{k}/{len(basis)}':<7} "
              f"{lb:>11.3f}  {alarms:>11}  {tier}{since}")
    if groups:
        print(f"  summary needs a lower bound ≥ {TIER_SUMMARY:.2f}, batch ≥ {TIER_BATCH:.2f} "
              f"(exact binomial, δ={DELTA}); only 'seen' groups qualify.")
        print("  A tier changes how you are asked, never whether.")
    if any(x["ai"].get("safety") for x in items) or any(r.get("safety") for _, r in missed):
        print("  Safety entries are always asked in full and re-measured first, whatever "
              "their group shows (spec §9).")
    if pending:
        shown = ", ".join(x["id"] for x in pending[:5])
        more = f" and {len(pending) - 5} more" if len(pending) > 5 else ""
        print(f"  awaiting your answer (not scored yet): {shown}{more}")

    if missed:
        by = {}
        for _, r in missed:
            by[r.get("final_type", "?")] = by.get(r.get("final_type", "?"), 0) + 1
        real = sum(1 for x in items if judged(x)) + len(missed)
        print()
        print("  missed: " + " · ".join(f"{t} {n}" for t, n in sorted(by.items())) +
              f" — at least {len(missed) / real:.0%} of the real conflicts were found by you, "
              f"not reported (the true share can only be higher)")

    cal = {}
    for x in items:
        if judged(x):
            c = cal.setdefault(x["ai"].get("ai_certainty", "?"), [0, 0])
            c[0] += 1
            c[1] += 1 if right(x) else 0
    if cal:
        print()
        print("  calibration, type-right by the AI's own certainty: " + " · ".join(
            f"{c} {cal[c][1]}/{cal[c][0]}" for c in CERTAINTY if c in cal))
        hi, lo = cal.get("high"), cal.get("low")
        if (hi and lo and hi[0] >= CALIB_MIN and lo[0] >= CALIB_MIN
                and hi[1] / hi[0] <= lo[1] / lo[0]):
            print("  ! 'high' does no better than 'low': the AI's certainty is not a signal "
                  "yet — do not lean on it")

    per_entry = {}
    for x in items:
        if judged(x):
            per_entry.setdefault(x["key"][0], set()).add(x["key"][1])
    for _, r in missed:
        per_entry.setdefault(r.get("entry", "?"), set()).add(r.get("source") or "__no-source__")
    marked = sorted(e for e, s in per_entry.items() if len(s) >= ENTRY_REVIEW_MIN)
    if marked:
        print()
        print(f"  in conflict in ≥ {ENTRY_REVIEW_MIN} distinct sources — mark for review "
              f"at the next distillation:")
        for e in marked:
            print(f"    {e}  ({len(per_entry[e])} sources)")

    moves = {}
    for x in items:
        if x["verdict"] not in (None, "defer") and not right(x):
            moves.setdefault((x["ai"].get("ai_type", "?"), x["final"]), set()).add(
                x["key"][1])
    hot = sorted((m, len(s)) for m, s in moves.items() if len(s) >= SIGNAL_MIN)
    if hot:
        print()
        for (a, b), n in hot:
            print(f"  the AI calls it {a}, you call it {b}: {n} distinct sources — a prompt "
                  f"to look at the §3 decision table, not a finding.")
        print("  Any change to that table is itself a kind=framework proposal you confirm.")


def cmd_stats(args):
    recs, bad = load(args.file)
    for n, err in bad:
        print(f"  ! line {n} is not valid JSON ({err}) — not counted", file=sys.stderr)
    if not recs:
        print(f"no records yet in {args.file}")
        print("nothing to analyse — which is the expected state until distillation "
              "has run a few times.")
        return 0

    amap = alias_map(recs)
    by_verdict, by_tag_sources, by_kind = {}, {}, {}
    folded, looped, n_alias, events = {}, set(), 0, {}
    for r in recs:
        if r.get("kind") in EVENT_KINDS:
            events[r["kind"]] = events.get(r["kind"], 0) + 1
            continue                      # an exam sitting or an AI's report is not a decision
        if r.get("kind") == "alias":
            n_alias += 1
            continue                      # an alias is a rule, not a decision
        by_verdict[r.get("verdict", "?")] = by_verdict.get(r.get("verdict", "?"), 0) + 1
        by_kind[r.get("kind", "?")] = by_kind.get(r.get("kind", "?"), 0) + 1
        tag = r.get("tag")
        if tag:
            canon, cyc = canonical(tag, amap)
            if cyc:
                looped.add(tag)
            elif canon != tag:
                folded.setdefault(canon, set()).add(tag)
            # No source means independence cannot be shown — so it is not granted.
            # Every sourceless record collapses into one bucket. Counting them as
            # distinct would reopen the exact back door this rule exists to close:
            # ten unattributed lines could clear the threshold on their own.
            by_tag_sources.setdefault(canon, set()).add(r.get("source") or "__no-source__")

    n_dec = len(recs) - n_alias - sum(events.values())
    extra = f" (+{n_alias} alias rule(s))" if n_alias else ""
    if events.get("conflict-report"):
        extra += f" (+{events['conflict-report']} AI conflict report(s))"
    if events.get("exam"):
        extra += f" (+{events['exam']} exam sitting(s))"
    rel = os.path.relpath(args.file, REPO_DIR)
    where = args.file if rel.startswith("..") else rel   # outside the repo: show it plainly
    print(f"whetstone decision — {n_dec} decision(s){extra} in {where}")
    print()
    print("by verdict: " + " · ".join(f"{k} {v}" for k, v in sorted(by_verdict.items())))
    print("by kind:    " + " · ".join(f"{k} {v}" for k, v in sorted(by_kind.items())))

    conflict_section(recs)

    if not by_tag_sources:
        print("\nno tagged records yet — tags are what makes a pattern visible.")
        return 0

    if folded:
        print("\nfolded by alias (every stored line is exactly as it was written):")
        for canon in sorted(folded):
            print(f"  {canon}  ←  " + ", ".join(sorted(folded[canon])))
    if looped:
        print("\n  ! these tags sit in an alias loop, so they were NOT folded and their "
              "counts stay split: " + ", ".join(sorted(looped)))
        print("    `decision aliases` shows the loop; cancel one leg with "
              "`alias --from X --to X`.")

    print(f"\nby tag (counting DISTINCT sources, not lines — one session arguing the "
          f"same point five times is one signal):")
    nosrc = sum(1 for r in recs if r.get("kind") != "alias" and r.get("tag")
                and not r.get("source"))
    if nosrc:
        print(f"  ({nosrc} tagged record(s) carry no source — they count as one between "
              f"them, since nothing shows they are independent)")
    rows = sorted(by_tag_sources.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    flagged = []
    for tag, sources in rows:
        n = len(sources)
        mark = "  ← reached the threshold" if n >= SIGNAL_MIN else ""
        new = "" if tag in KNOWN_TAGS else "  (undocumented)"
        print(f"  {n:>3}  {tag}{new}{mark}")
        if n >= SIGNAL_MIN:
            flagged.append((tag, n))

    print()
    if flagged:
        for tag, n in flagged:
            doc = "" if tag in KNOWN_TAGS else \
                "  It is also still undocumented — a tag this load-bearing belongs in " \
                "KNOWN_TAGS and spec/review-decisions.md."
            print(f"{tag}: {n} distinct sources — worth asking whether the framework "
                  f"itself is unclear here, not just these entries.{doc}")
        print()
        print(f"That is a prompt to look, not a finding. A framework change still needs")
        print(f"the same thing every knowledge entry needs: name what breaks without it,")
        print(f"and append rather than overwrite (§11). The threshold {SIGNAL_MIN} is a")
        print(f"guess awaiting calibration from this very file.")
    else:
        print(f"nothing has reached {SIGNAL_MIN} distinct sources yet. Keep recording.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="whetstone decision — record review decisions")
    ap.add_argument("--file", default=os.environ.get("WHETSTONE_DECISIONS", DEFAULT_FILE))
    sub = ap.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="append one decision")
    a.add_argument("--subject", required=True, help="what was proposed, in a few words")
    a.add_argument("--verdict", required=True, help="/".join(VERDICTS))
    a.add_argument("--reason", required=True, help="one line, free text — why you decided that")
    a.add_argument("--kind", default="entry", help="/".join(KINDS))
    a.add_argument("--source", default="", help="commit hash / session pointer (§7 traceability)")
    a.add_argument("--skill", default="", help="target skill name")
    a.add_argument("--action", default="", help="add / supersede / write-back / conflict")
    a.add_argument("--layer", default="", help="proposed layer")
    a.add_argument("--conf", default="", help="proposed confidence")
    a.add_argument("--final-layer", dest="final_layer", default="", help="layer after your edit")
    a.add_argument("--final-conf", dest="final_conf", default="", help="confidence after your edit")
    a.add_argument("--section", default="", help="framework section, for kind=framework")
    a.add_argument("--tag", default="", help="optional bucket; unknown tags are kept and reported")
    a.add_argument("--date", default="", help="YYYY-MM-DD (default: today)")
    a.set_defaults(func=cmd_add)

    rp = sub.add_parser("report", help="step 1: the AI's call on a conflict, before asking")
    rp.add_argument("--entry", required=True, help="<skill>/<item> the conflict is about")
    rp.add_argument("--ai-type", dest="ai_type", required=True, help="/".join(CONFLICT_TYPES))
    rp.add_argument("--ai-evidence", dest="ai_evidence", required=True, help="/".join(EVIDENCE))
    rp.add_argument("--ai-action", dest="ai_action", required=True, help="/".join(AI_ACTIONS))
    rp.add_argument("--ai-certainty", dest="ai_certainty", required=True,
                    help="/".join(CERTAINTY) + " — the AI's certainty in its own call")
    rp.add_argument("--subject", required=True, help="what the conflict is about, in a few words")
    rp.add_argument("--reason", required=True, help="why the AI thinks so (stored as ai_reason)")
    rp.add_argument("--conflict-id", dest="conflict_id", default="",
                    help="C-YYYYMMDD-NN (default: the next free number today)")
    rp.add_argument("--entry-source", dest="entry_source", default="",
                    help="the entry's own source commit")
    rp.add_argument("--source", default="", help="this session / commit; one conflict per entry per source")
    rp.add_argument("--blocking", action="store_true", help="it stops the next step")
    rp.add_argument("--safety", action="store_true", help="a safety-relevant entry (spec §9)")
    rp.set_defaults(func=cmd_report)

    rs = sub.add_parser("resolve", help="step 2: the human's answer to a report on file")
    rs.add_argument("--conflict-id", dest="conflict_id", required=True)
    rs.add_argument("--verdict", required=True, help="/".join(VERDICTS))
    rs.add_argument("--reason", required=True, help="what the human decided, and why")
    rs.add_argument("--final-type", dest="final_type", default="",
                    help="the human's type when it differs; none = it was not a conflict")
    rs.add_argument("--source", default="")
    rs.add_argument("--date", default="")
    rs.set_defaults(func=cmd_resolve)

    ms = sub.add_parser("miss", help="a conflict the AI used without reporting — you found it")
    ms.add_argument("--entry", required=True)
    ms.add_argument("--final-type", dest="final_type", required=True, help="/".join(CONFLICT_TYPES))
    ms.add_argument("--verdict", required=True, help="/".join(VERDICTS))
    ms.add_argument("--subject", required=True)
    ms.add_argument("--reason", required=True, help="how it was found")
    ms.add_argument("--source", default="")
    ms.add_argument("--safety", action="store_true")
    ms.add_argument("--date", default="")
    ms.set_defaults(func=cmd_miss)

    e = sub.add_parser("exam", help="record one sitting of the known-answer exam")
    e.add_argument("--result", required=True, help="pass / fail")
    e.add_argument("--reason", required=True, help="which questions, which model, what went wrong")
    e.add_argument("--source", default="")
    e.add_argument("--date", default="")
    e.set_defaults(func=cmd_exam)

    s = sub.add_parser("stats", help="what the records point at")
    s.set_defaults(func=cmd_stats)

    l = sub.add_parser("list", help="most recent records")
    l.add_argument("-n", type=int, default=20)
    l.set_defaults(func=cmd_list)

    al = sub.add_parser("alias", help="declare that two tags were the same thing")
    al.add_argument("--from", dest="frm", required=True, help="the spelling to fold away")
    al.add_argument("--to", required=True,
                    help="the spelling to keep; pass the same value as --from to cancel")
    al.add_argument("--reason", required=True, help="one line — why they are the same")
    al.add_argument("--source", default="")
    al.add_argument("--date", default="")
    al.set_defaults(func=cmd_alias)

    als = sub.add_parser("aliases", help="which tags are folded into which")
    als.set_defaults(func=cmd_aliases)

    t = sub.add_parser("tags", help="the starter tag vocabulary")
    t.set_defaults(func=lambda args: ([print(f"  {k:<16} {v}") for k, v in
                                       sorted(KNOWN_TAGS.items())] and 0) or 0)

    args = ap.parse_args()
    if not getattr(args, "func", None):
        ap.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
