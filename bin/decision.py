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

  bin/decision.py add --subject "..." --verdict amend --reason "..." [--tag ...]
  bin/decision.py stats            what the accumulated decisions point at
  bin/decision.py list [-n N]      the most recent records

Records land in journal/review-decisions.jsonl — git-ignored, because they quote
your real library. stdlib only, runtime-neutral.
"""
import os
import sys
import re
import json
import argparse
import datetime

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


def cmd_add(args):
    if args.verdict not in VERDICTS:
        print(f"verdict must be one of {'/'.join(VERDICTS)}", file=sys.stderr)
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
    if args.tag and args.tag not in KNOWN_TAGS:
        print(f"  note: {args.tag!r} is a new tag. If it turns out to recur, add it to "
              f"KNOWN_TAGS and spec/review-decisions.md so it stays greppable.")
    return 0


def cmd_list(args):
    recs, bad = load(args.file)
    for n, err in bad:
        print(f"  ! line {n} is not valid JSON ({err}) — not counted", file=sys.stderr)
    if not recs:
        print(f"no records yet in {args.file}")
        return 0
    for r in recs[-args.n:]:
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


def cmd_stats(args):
    recs, bad = load(args.file)
    for n, err in bad:
        print(f"  ! line {n} is not valid JSON ({err}) — not counted", file=sys.stderr)
    if not recs:
        print(f"no records yet in {args.file}")
        print("nothing to analyse — which is the expected state until distillation "
              "has run a few times.")
        return 0

    by_verdict, by_tag_sources, by_kind = {}, {}, {}
    for r in recs:
        by_verdict[r.get("verdict", "?")] = by_verdict.get(r.get("verdict", "?"), 0) + 1
        by_kind[r.get("kind", "?")] = by_kind.get(r.get("kind", "?"), 0) + 1
        tag = r.get("tag")
        if tag:
            # No source means independence cannot be shown — so it is not granted.
            # Every sourceless record collapses into one bucket. Counting them as
            # distinct would reopen the exact back door this rule exists to close:
            # ten unattributed lines could clear the threshold on their own.
            by_tag_sources.setdefault(tag, set()).add(r.get("source") or "__no-source__")

    print(f"whetstone decision — {len(recs)} record(s) in {os.path.relpath(args.file, REPO_DIR)}")
    print()
    print("by verdict: " + " · ".join(f"{k} {v}" for k, v in sorted(by_verdict.items())))
    print("by kind:    " + " · ".join(f"{k} {v}" for k, v in sorted(by_kind.items())))

    if not by_tag_sources:
        print("\nno tagged records yet — tags are what makes a pattern visible.")
        return 0

    print(f"\nby tag (counting DISTINCT sources, not lines — one session arguing the "
          f"same point five times is one signal):")
    nosrc = sum(1 for r in recs if r.get("tag") and not r.get("source"))
    if nosrc:
        print(f"  ({nosrc} tagged record(s) carry no source — they count as one between "
              f"them, since nothing shows they are independent)")
    rows = sorted(by_tag_sources.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    flagged = []
    for tag, sources in rows:
        n = len(sources)
        mark = "  ← reached the threshold" if n >= SIGNAL_MIN else ""
        new = "" if tag in KNOWN_TAGS else "  (new tag)"
        print(f"  {n:>3}  {tag}{new}{mark}")
        if n >= SIGNAL_MIN:
            flagged.append((tag, n))

    print()
    if flagged:
        for tag, n in flagged:
            print(f"{tag}: {n} distinct sources — worth asking whether the framework "
                  f"itself is unclear here, not just these entries.")
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

    s = sub.add_parser("stats", help="what the records point at")
    s.set_defaults(func=cmd_stats)

    l = sub.add_parser("list", help="most recent records")
    l.add_argument("-n", type=int, default=20)
    l.set_defaults(func=cmd_list)

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
