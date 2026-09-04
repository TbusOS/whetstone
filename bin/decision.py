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

    amap = alias_map(recs)
    by_verdict, by_tag_sources, by_kind = {}, {}, {}
    folded, looped, n_alias = {}, set(), 0
    for r in recs:
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

    n_dec = len(recs) - n_alias
    extra = f" (+{n_alias} alias rule(s))" if n_alias else ""
    rel = os.path.relpath(args.file, REPO_DIR)
    where = args.file if rel.startswith("..") else rel   # outside the repo: show it plainly
    print(f"whetstone decision — {n_dec} decision(s){extra} in {where}")
    print()
    print("by verdict: " + " · ".join(f"{k} {v}" for k, v in sorted(by_verdict.items())))
    print("by kind:    " + " · ".join(f"{k} {v}" for k, v in sorted(by_kind.items())))

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
