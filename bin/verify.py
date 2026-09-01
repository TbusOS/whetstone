#!/usr/bin/env python3
"""whetstone verify — evidence-discipline checks on a portable skill package.

`lint` checks the SELECTION MENU (name + description) — how a skill gets picked.
`verify` checks the CONTENT: does every piece of knowledge carry the provenance
the extraction framework demands, and is its confidence the level the mechanical
table actually allows?

references/extraction-framework.md states those rules in prose (§4 split,
§7 provenance + mechanical confidence table, §8 self-check, §9 blacklist,
§11 supersede) and spec/skill-package.md states the portability rules.
Prose rules rot: a rule that only an LLM enforces is one context window away
from not existing. This turns the mechanically decidable subset into a command.

Deliberately NOT decided here (stays human — Phase 4 review; see --explain):
  - is an L1 entry really exception-free
  - does an L2 lesson survive deleting every platform-specific value
  - was a contradiction preserved rather than averaged away
  - were this session's write-backs applied (needs the session, not the package)

Runtime-neutral, stdlib only. Exit 1 on ERROR (or on WARN with --strict), 2 on bad input.

  bin/verify.py <package-dir> [<package-dir> ...]
  bin/verify.py --src <skills-dir>          # every */SKILL.md beneath it
  bin/verify.py --json --strict
  bin/verify.py --explain                   # what each check is and what is not checked
"""
import os
import re
import sys
import json
import argparse

# --- tunables (explicit so the contract stays auditable, same spirit as lint.py) ---
WHY_CELL_LEN = 40          # chars in an L3 cell above which prose-in-params is suspected
                           # (CJK counts 1 char/glyph, so 60 was a whole paragraph)
RANK = {"low": 0, "med": 1, "medium": 1, "high": 2}   # medium parsed, but flagged: §7 says med
RANK_NAME = {0: "low", 1: "med", 2: "high"}

DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
VAGUE_DATE = re.compile(r"当前|最近|近期|上次|前几天|recently|currently", re.I)
CONF_VAL = re.compile(r"\b(high|med|medium|low)\b", re.I)
TESTED_OK = re.compile(r"实测[:：]?\s*通过\s*(\d{4}-\d{2}-\d{2})|tested[:：]?\s*pass\s*(\d{4}-\d{2}-\d{2})", re.I)
TESTED_NO = re.compile(r"未实测|未验证|not\s+tested", re.I)
BARE_COUNT = re.compile(r"^\s*\d+\s*(次|times?)?\s*$", re.I)
UNTRACEABLE = re.compile(r"前面说过|上面提过|之前提到|as\s+mentioned|see\s+above", re.I)
COMMITISH = re.compile(r"\b[0-9a-f]{7,40}\b|commit|会话|session|transcript|PR\s*#?\d+|issue\s*#?\d+", re.I)

FIELD_SOURCE = re.compile(r"来源|source")
FIELD_DATE = re.compile(r"日期|时间|date")
FIELD_REPRO = re.compile(r"复现")
FIELD_VERIFY = re.compile(r"验证")
FIELD_CONF = re.compile(r"置信")
FIELD_LAYER = re.compile(r"^\s*[-*]?\s*\**\s*(层|layer)\s*\**\s*[:：]\s*(L[1-4])", re.I)

CONCRETE = [
    (re.compile(r"0x[0-9a-fA-F]{3,}"), "hex address/value"),
    (re.compile(r"(?<!\d)\d{1,3}(?:\.\d{1,3}){3}(?!\d)"), "IP address"),
    (re.compile(r"(?<![\w.-])/(?:dev|proc|sys|opt|srv|etc)/[\w./-]+"), "absolute system path"),
    (re.compile(r"(?<![\w.-])v?\d+\.\d+\.\d+(?![\w.-])"), "pinned version"),
    (re.compile(r"(?<!\w)\d+\s*(?:KB|MB|GB|kHz|MHz|GHz|ms|us|bps|baud)(?!\w)", re.I), "measured quantity"),
]
USERPATH = re.compile(r"/home/[A-Za-z0-9_.-]+|/Users/[A-Za-z0-9_.-]+|[Cc]:\\Users\\")
RUNTIME_PATH = re.compile(r"~/\.claude|\.claude/skills|~/\.codex|~/\.cursor|~/\.gemini")
RUNTIME_NAME = re.compile(r"Claude Code|Codex|Cursor|Gemini CLI|GitHub Copilot", re.I)
EXEMPT_L3 = re.compile(r"<!--\s*l3-ok")
EXEMPT_RT = re.compile(r"<!--\s*runtime-ok")
# a block is a provenance RECORD only if it carries a field-shaped line; merely
# mentioning 来源/置信 in prose is not a record (that is V09b's job instead).
FIELD_LINE = re.compile(r"^\s*[-*]?\s*\**\s*(来源|溯源|source|provenance|置信度|复现记录|验证方式)\s*\**\s*[:：]")
INLINE_CONF = re.compile(r"置信\s*度?\s*[:：]?\s*(high|med|medium|low)", re.I)

# ---------------------------------------------------------------- parsing ---


def read(path):
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def parse_frontmatter(path):
    """YAML frontmatter -> dict. Folded/literal block scalars are joined."""
    lines = read(path).splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm = lines[1:i]
            break
    if fm is None:
        return {}
    out, i = {}, 0
    while i < len(fm):
        ln = fm[i]
        if ":" in ln and not ln.startswith((" ", "\t")):
            k, v = ln.split(":", 1)
            k, v = k.strip(), v.strip()
            if v in (">", "|", ">-", "|-", ">+", "|+"):
                blk, j = [], i + 1
                while j < len(fm) and (fm[j].startswith((" ", "\t")) or not fm[j].strip()):
                    blk.append(fm[j].strip())
                    j += 1
                out[k] = " ".join(x for x in blk if x)
                i = j
                continue
            out[k] = v.strip('"').strip("'")
        i += 1
    return out


def strip_fences(lines):
    """Return a list of (lineno, text, in_fence). Fenced code is illustrative;
    the concrete-value scan skips it, everything else still sees it."""
    out, fence = [], False
    for n, t in enumerate(lines, 1):
        if t.lstrip().startswith("```"):
            fence = not fence
            out.append((n, t, True))
            continue
        out.append((n, t, fence))
    return out


def split_repro(raw):
    """A 复现记录 value -> list of record lines. Accepts ';' / '；' separated
    (table cells) or already-split bullet lines."""
    parts = [p.strip() for p in re.split(r"[;；]", raw) if p.strip()]
    return [p for p in parts if p not in ("-", "—", "无", "none", "N/A", "n/a")]


def repro_key(line):
    """Unique key of a 复现记录 line = its platform/project field (§7).
    Line form: '<平台/项目> · <日期> · <指针>'. Returns (raw_key, normal_key)."""
    head = re.split(r"[·|]", line, maxsplit=1)[0].strip()
    head = re.sub(r"^[-*\s]+", "", head).strip("`*　 ")
    return head, re.sub(r"[\s_./\\-]+", "", head).lower()


def cell_fields(headers, cells):
    """Map a table row onto the five provenance fields by header keyword."""
    f = {"source": "", "date": "", "repro": "", "verify": "", "conf": "", "why": ""}
    for h, c in zip(headers, cells):
        if FIELD_CONF.search(h):
            f["conf"] = c
        elif FIELD_REPRO.search(h):
            f["repro"] = c
        elif FIELD_VERIFY.search(h):
            f["verify"] = c
            if DATE.search(c):
                f["date"] = f["date"] or c
        elif FIELD_SOURCE.search(h):
            f["source"] = c
            if DATE.search(c):
                f["date"] = f["date"] or c
        elif FIELD_DATE.search(h):
            f["date"] = c
        elif re.search(r"why", h, re.I):
            f["why"] = c
    return f


def parse_tables(path, text, layer):
    """Markdown tables carrying a 置信度 column -> one record per data row."""
    recs = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            headers = [c.strip() for c in ln.strip().strip("|").split("|")]
            if not any(FIELD_CONF.search(h) for h in headers):
                i += 1
                continue
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                if any(c for c in cells):
                    f = cell_fields(headers, cells)
                    recs.append({
                        "file": path, "line": j + 1, "layer": layer,
                        "title": (cells[0] or "(row)")[:48], "fields": f,
                        "raw": lines[j], "form": "table",
                        "cells": cells, "headers": headers,
                    })
                j += 1
            i = j
            continue
        i += 1
    return recs


def parse_blocks(path, text, default_layer):
    """Non-table provenance records: a run of lines (bounded by a blank line or a
    heading) that mentions 来源 or 置信. Covers both the template's nested
    '溯源:' bullet list and the one-line '- **来源**:X · 日期 · 置信 high' form."""
    recs = []
    lines = text.splitlines()
    block, start, title = [], 0, ""
    cur_title = ""

    def flush():
        if not block:
            return
        body = "\n".join(block)
        if not any(FIELD_LINE.match(t) for t in block):
            return
        f = {"source": "", "date": "", "repro": "", "verify": "", "conf": "", "why": ""}
        repro_lines, layer = [], default_layer
        for off, t in enumerate(block):
            m = FIELD_LAYER.match(t)
            if m:
                layer = m.group(2).upper()
                continue
            val = t.split("：", 1)[-1] if "：" in t else (t.split(":", 1)[-1] if ":" in t else t)
            val = val.strip()
            # which field this line IS = what it leads with. A compact one-liner
            # ("- **来源**:X · 2026-05-13 · 置信 high") mentions several field
            # names; classifying by `search` would let 置信 swallow the 来源 line.
            lead = FIELD_LINE.match(t)
            key = lead.group(1) if lead else ""
            if key:
                if FIELD_REPRO.search(key):
                    tgt = "repro"
                elif FIELD_VERIFY.search(key):
                    tgt = "verify"
                elif FIELD_CONF.search(key):
                    tgt = "conf"
                elif FIELD_DATE.search(key):
                    tgt = "date"
                else:
                    tgt = "source"
                f[tgt] = f[tgt] or val
                if tgt != "repro":
                    continue
            if FIELD_REPRO.search(t):
                f["repro"] = f["repro"] or val
                repro_lines = split_repro(val)
                # deeper-indented bullets directly beneath count as record lines
                base = len(block[off]) - len(block[off].lstrip())
                for t2 in block[off + 1:]:
                    if not t2.strip():
                        break
                    ind = len(t2) - len(t2.lstrip())
                    if ind > base and t2.lstrip().startswith(("-", "*")):
                        repro_lines.append(t2.strip().lstrip("-* ").strip())
                    else:
                        break
            elif FIELD_VERIFY.search(t):
                f["verify"] = f["verify"] or val
            elif FIELD_CONF.search(t):
                f["conf"] = f["conf"] or val
            elif FIELD_SOURCE.search(t):
                f["source"] = f["source"] or val
            elif FIELD_DATE.search(t):
                f["date"] = f["date"] or val
        if not f["conf"]:
            m = re.search(r"置信\s*[度]?\s*[:：]?\s*(high|med|medium|low)", body, re.I)
            if m:
                f["conf"] = m.group(1)
        if not f["date"]:
            m = DATE.search(body)
            if m:
                f["date"] = m.group(0)
        recs.append({
            "file": path, "line": start, "layer": layer,
            "title": (title or "(block)")[:48], "fields": f,
            "repro_lines": repro_lines, "raw": body, "form": "block",
        })

    in_fence = False
    for n, t in enumerate(lines, 1):
        if t.lstrip().startswith("```"):
            in_fence = not in_fence
        if in_fence:
            continue
        if t.startswith("#"):
            flush()
            block, cur_title = [], t.lstrip("# ").strip()
            continue
        if not t.strip():
            flush()
            block = []
            continue
        if not block:
            start, title = n, cur_title
        block.append(t)
    flush()
    return recs


def layer_of_section(text, lineno):
    """Layer implied by the nearest preceding SKILL.md heading, e.g. '## 坑 (L2)'."""
    lines = text.splitlines()[:lineno]
    for t in reversed(lines):
        if t.startswith("#"):
            m = re.search(r"\bL([1-4])\b", t)
            return "L" + m.group(1) if m else ""
    return ""


# ----------------------------------------------------------------- checks ---


class Report:
    def __init__(self):
        self.items = []

    def add(self, sev, code, where, msg, fix=""):
        self.items.append({"sev": sev, "code": code, "where": where, "msg": msg, "fix": fix})

    def counts(self):
        return (sum(1 for i in self.items if i["sev"] == "E"),
                sum(1 for i in self.items if i["sev"] == "W"),
                sum(1 for i in self.items if i["sev"] == "I"))


def cap_for(layer, verified, distinct):
    """§7 mechanical confidence table, with the §7 L2 additional constraint.

    high : verified AND distinct >= 2
    med  : distinct >= 2, OR (verified once AND the entry is an L3 fact)
    low  : otherwise
    L1/L2 override: fewer than 2 distinct platforms/projects caps at low no matter
    what — 'verified once' rescues a value, never a method (§7)."""
    if layer in ("L1", "L2") and distinct < 2:
        return 0
    if verified and distinct >= 2:
        return 2
    if distinct >= 2:
        return 1
    if verified and layer == "L3":
        return 1
    return 0


def check_record(rec, rep, pkg):
    f = rec["fields"]
    where = f"{os.path.relpath(rec['file'], pkg)}:{rec['line']}"
    what = rec["title"]
    layer = rec["layer"] or "?"

    # V06 five provenance fields present
    missing = []
    if not f["source"]:
        missing.append("来源")
    if not f["date"] and not DATE.search(f["source"] or ""):
        missing.append("日期")
    if not (f["repro"] or rec.get("repro_lines")):
        missing.append("复现记录")
    if not f["conf"]:
        missing.append("置信度")
    if missing:
        rep.add("E", "V06", where, f"[{what}] provenance is missing: {', '.join(missing)}",
                "§7 — all five fields are required (验证方式 may be empty, but say 未实测 explicitly)")
    if not f["verify"]:
        rep.add("W", "V06b", where, f"[{what}] no 验证方式 field — confidence is capped at med",
                "§7 — write `<command / minimal repro> · 实测:通过 <YYYY-MM-DD>` or `· 未实测`")

    # V07 absolute date
    # the date field is judged on its own: a tested-on date elsewhere in the record
    # must not rescue a 提炼日期 that says "recently" (audit finding)
    own_date = f["date"] or (f["source"] if DATE.search(f["source"] or "") else "")
    if not DATE.search(own_date or ""):
        rep.add("E", "V07", where, f"[{what}] 日期 is not an absolute date (YYYY-MM-DD)",
                "§7 — never \"current\" / \"recently\"")
    if VAGUE_DATE.search(" ".join([f["date"], f["source"], f["verify"]])):
        rep.add("W", "V07b", where, f"[{what}] relative time word in a date field", "§7 — use an absolute date")

    # V08 traceable source
    if f["source"]:
        if UNTRACEABLE.search(f["source"]):
            rep.add("E", "V08", where, f"[{what}] 来源 is untraceable (\"as mentioned earlier\" style)",
                    "SKILL.md blacklist #7 — cite a commit hash or a transcript locator")
        elif not COMMITISH.search(f["source"]):
            rep.add("W", "V08b", where, f"[{what}] no commit / session marker in 来源", "§7 — add a commit hash or transcript locator")

    # V09 confidence value is one of the three
    declared = None
    if f["conf"]:
        m = CONF_VAL.search(f["conf"])
        if not m:
            rep.add("E", "V09", where, f"[{what}] unparseable 置信度: {f['conf'][:24]!r}", "§7 — only high / med / low")
        else:
            raw_lvl = m.group(1).lower()
            declared = RANK[raw_lvl]
            if raw_lvl == "medium":
                rep.add("W", "V09c", where, f"[{what}] 置信度 written as 'medium'",
                        "§7 — the three levels are spelled high / med / low")

    # V14 复现记录 is a list, not a bare count
    lines_ = rec.get("repro_lines")
    if lines_ is None:
        lines_ = split_repro(f["repro"])
    if f["repro"] and BARE_COUNT.match(f["repro"]):
        rep.add("E", "V14", where, f"[{what}] 复现记录 is a bare count \u300c{f['repro'].strip()}\u300d",
                "§7/§8 — must be a list; one line per platform/project · date · pointer")
        lines_ = []

    # V15 line shape. An unkeyable line is not a WARN you can shrug off: without the
    # separator there is no platform field, so V16 cannot tell two platforms from one
    # and the whole promotion gate is bypassed by deleting a dot (audit finding).
    # Such lines are therefore excluded from the count AND are an error for L1/L2.
    keyless = [ln for ln in lines_ if "\u00b7" not in ln and "|" not in ln]
    if keyless:
        sev = "E" if layer in ("L1", "L2") else "W"
        rep.add(sev, "V15", where,
                f"[{what}] 复现记录 line has no separator, so it carries no platform key: {keyless[0][:36]!r}",
                "§7 — `<platform/project> \u00b7 <date> \u00b7 <pointer>`; unkeyed lines do not count toward the gate")
    if layer in ("L1", "L2"):
        lines_ = [ln for ln in lines_ if ln not in keyless]

    # V16/V17 unique key = platform/project. For an L3 file the platform is the file
    # itself, so its lines are re-verification events — but byte-identical ones are
    # still one event, not two (audit finding).
    if layer == "L3":
        seen_l3, uniq = set(), []
        for ln in lines_:
            k = re.sub(r"[\s_./\\-]+", "", ln).lower()
            if k and k in seen_l3:
                rep.add("E", "V16", where, f"[{what}] 复现记录 repeats an identical line: {ln[:36]!r}",
                        "§7 — a duplicated line is one re-verification, not two")
                continue
            seen_l3.add(k)
            uniq.append(ln)
        lines_ = uniq
    distinct = len(lines_)
    if layer in ("L1", "L2") and lines_:
        seen_raw, seen_norm = {}, {}
        for ln in lines_:
            raw, norm = repro_key(ln)
            if not norm:
                continue
            if norm in seen_norm:
                if seen_raw.get(norm) == raw:
                    rep.add("E", "V16", where,
                            f"[{what}] 复现记录 has two lines for the same platform/project: {raw!r}",
                            "§7 — the line key is the platform/project; re-confirming on the same one refreshes the date, it does not add a line")
                else:
                    rep.add("W", "V17", where,
                            f"[{what}] same key spelled two ways: {seen_raw[norm]!r} vs {raw!r}",
                            "§7 — identical after normalising; spell it one way or it inflates the reproduction count")
            else:
                seen_norm[norm] = True
                seen_raw[norm] = raw
        distinct = len(seen_norm)

    # V10/V11/V12/V13 mechanical confidence table
    verified = bool(TESTED_OK.search(f["verify"] or ""))
    if f["verify"] and not verified and not TESTED_NO.search(f["verify"]):
        rep.add("W", "V13b", where, f"[{what}] 验证方式 says neither \u300c\u5b9e\u6d4b:\u901a\u8fc7 <date>\u300d nor \u300c\u672a\u5b9e\u6d4b\u300d",
                "§7 — the test result must be explicit or the table cannot be evaluated mechanically")
    if declared is not None:
        cap = cap_for(layer, verified, distinct)
        if declared > cap:
            why = []
            if not verified:
                why.append("验证方式 never passed a test")
            if distinct < 2:
                why.append(f"复现记录 has {distinct} line(s), needs 2")
            code = "V12" if (layer in ("L1", "L2") and distinct < 2) else "V10"
            extra = " (single-platform L1/L2 is capped at low — the §7 constraint outranks the table)" if code == "V12" else ""
            rep.add("E", code, where,
                    f"[{what}] {layer} claims 置信度 {RANK_NAME[declared]}, the table allows only {RANK_NAME[cap]}"
                    f" — {'; '.join(why)}{extra}",
                    "§7 table: tested-and-passed AND 复现记录 >=2 lines for high. A reviewer may downgrade, never upgrade past the conditions")
        elif declared < cap:
            rep.add("I", "V11", where,
                    f"[{what}] 置信度 {RANK_NAME[declared]} is below the allowed {RANK_NAME[cap]} — a reviewer downgrade, which is legal",
                    "")
    # V18 promotion available
    if layer == "L2" and distinct >= 2 and os.path.basename(rec["file"]) != "SKILL.md":
        rep.add("I", "V18", where, f"[{what}] reproduced on {distinct} distinct platforms/projects — eligible to move into the SKILL.md L2 body",
                "§7 L2 promotion rule")
    return distinct


# What counts as PACKAGE CONTENT: the markdown at the package root plus the three
# directories a package may ship. Portability rules apply to scripts/ and knowledge/
# too — restricting the scan to SKILL.md/pitfalls.md/params let a hardcoded
# ~/.claude inside scripts/ pass unnoticed (audit finding). They do NOT apply to a
# tool repository's own implementation: pointing this at a repo whose job is to
# adapt to runtimes would flag its adapters, which are runtime-specific by design.
PKG_DIRS = ("params", "knowledge", "scripts")
# repo furniture, not skill knowledge: a shipped package has none of these, and a
# repo that has them should not be judged on them
NOT_CONTENT = {"README.md", "CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE.md"}
TEXT_EXT = (".md", ".sh", ".py", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".conf")


def _walk(pkg, exts):
    out = []
    for fn in sorted(os.listdir(pkg)) if os.path.isdir(pkg) else []:
        if (fn.endswith(exts) and not fn.startswith(".") and fn not in NOT_CONTENT
                and os.path.isfile(os.path.join(pkg, fn))):
            out.append(fn)
    for sub in PKG_DIRS:
        d = os.path.join(pkg, sub)
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for fn in sorted(files):
                if fn.endswith(exts) and not fn.startswith("."):
                    out.append(os.path.relpath(os.path.join(root, fn), pkg))
    return sorted(out)


def _all_md(pkg):
    return _walk(pkg, (".md",))


def _all_text(pkg):
    return _walk(pkg, TEXT_EXT)


def check_package(pkg, rep):
    name = os.path.basename(os.path.abspath(pkg))
    sk = os.path.join(pkg, "SKILL.md")

    # ---- V01..V05 structure ----
    if not os.path.isfile(sk):
        rep.add("E", "V01", name, "no SKILL.md — this is not a skill package", "spec/skill-package.md, directory layout")
        return
    fm = parse_frontmatter(sk)
    if not fm.get("name") or not fm.get("description"):
        rep.add("E", "V01", "SKILL.md", "frontmatter is missing name or description", "spec — the Agent Skills standard")
    fmname = fm.get("name", "")
    if fmname and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fmname):
        rep.add("E", "V02", "SKILL.md", f"name is not kebab-case: {fmname!r}", "§13 description contract")
    if fmname and fmname != name:
        rep.add("W", "V02b", "SKILL.md", f"frontmatter name ({fmname}) differs from the directory name ({name})",
                "spec — the directory name is the skill name; copying the directory must just work")

    text = read(sk)
    params_dir = os.path.join(pkg, "params")
    have_params = sorted(f for f in os.listdir(params_dir)) if os.path.isdir(params_dir) else []
    have_params = [f for f in have_params if f.endswith(".md")]

    # V03 pointers resolve
    for m in re.finditer(r"`?(params/[\w.-]+\.md|pitfalls\.md)`?", text):
        tgt = m.group(1)
        if "<" in tgt or ">" in tgt:
            continue
        if not os.path.isfile(os.path.join(pkg, tgt)):
            ln = text[:m.start()].count("\n") + 1
            rep.add("E", "V03", f"SKILL.md:{ln}", f"pointer resolves to nothing: {tgt}", "§10 where artefacts live")

    # V04 declared platforms vs params/ files
    declared_pf = set()
    m = re.search(r"已支持平台[^\n]*[:：]\s*([^\n]+)", text)
    if m:
        declared_pf = {p.strip().strip("`") for p in re.split(r"[、,，/|]", m.group(1)) if p.strip()}
    file_pf = {os.path.splitext(f)[0] for f in have_params if not f.startswith("_")}
    if declared_pf and file_pf:
        for p in file_pf - {d.lower() for d in declared_pf}:
            if p not in {d.lower() for d in declared_pf}:
                rep.add("W", "V04", "SKILL.md", f"params/{p}.md exists but is not listed under 已支持平台", "§10")

    # V05 self-contained: no build junk / OS junk shipped with the package.
    # Scripts are NOT flagged — the framework itself requires executable checks
    # ("a hard checklist without a runnable check is not codified"), so a package
    # carrying scripts/ is conforming, not broken. What actually breaks a shared
    # package is compiled artifacts, archives and editor/OS leftovers.
    JUNK = (".pyc", ".pyo", ".o", ".so", ".a", ".class", ".zip", ".tar", ".tgz",
            ".gz", ".bak", ".orig", ".rej", ".swp", ".swo")
    for root, dirs, files in os.walk(pkg):
        dirs[:] = [d for d in dirs if d not in (".git", "journal", "inbox", "__pycache__")]
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), pkg)
            if fn == ".DS_Store" or fn.endswith(JUNK):
                rep.add("W", "V05", rel, "build/OS junk shipped inside the package",
                        "spec — self-contained means copy-and-run, without compiled artefacts or editor leftovers")
    for rel_md in _all_md(pkg):
        t2 = read(os.path.join(pkg, rel_md))
        for m in re.finditer(r"\]\(\s*(\.\./[^)]+)\)", t2):
            ln = t2[:m.start()].count("\n") + 1
            rep.add("E", "V05b", f"{rel_md}:{ln}", f"link points outside the package: {m.group(1)}",
                    "spec — self-contained")

    # ---- V19..V22 layering discipline ----
    prov_lines = set()
    records = []
    body_recs = parse_blocks(sk, text, "")
    for r in body_recs:
        r["layer"] = r["layer"] or layer_of_section(text, r["line"]) or "L2"
        for k in range(r["line"], r["line"] + r["raw"].count("\n") + 1):
            prov_lines.add(k)
    records += body_recs
    records += parse_tables(sk, text, "L2")

    l3_section = False
    for n, t, in_fence in strip_fences(text.splitlines()):
        if t.startswith("#"):
            l3_section = bool(re.search(r"平台参数|params|\(L3\)", t, re.I))
        if in_fence or n in prov_lines or l3_section or EXEMPT_L3.search(t):
            continue
        if t.lstrip().startswith(">"):
            continue
        m = INLINE_CONF.search(t)
        if m:
            lvl = m.group(1).lower()
            sev = "E" if RANK[lvl] >= 2 else "W"
            rep.add(sev, "V09b", f"SKILL.md:{n}",
                    f"inline claim of 置信 {lvl} with no provenance record behind it",
                    "§7 — every entry carries 来源/日期/复现记录/验证方式; §9#8 confidence is not a feeling")
            continue
        for rx, what in CONCRETE:
            m = rx.search(t)
            if m:
                rep.add("W", "V19", f"SKILL.md:{n}", f"concrete value in the body ({what}): {m.group(0)!r}",
                        "§9#1 — push it down to params/ (L3); if it really is general, mark <!-- l3-ok: reason -->")
                break

    # pitfalls
    pf = os.path.join(pkg, "pitfalls.md")
    if os.path.isfile(pf):
        ptext = read(pf)
        pprov = set()
        for r in parse_blocks(pf, ptext, "L2"):
            for k in range(r["line"], r["line"] + r["raw"].count("\n") + 1):
                pprov.add(k)
        for n, t, in_fence in strip_fences(ptext.splitlines()):
            if in_fence or n in pprov or EXEMPT_L3.search(t) or t.lstrip().startswith(">"):
                continue
            for rx, whatv in CONCRETE:
                m = rx.search(t)
                if m:
                    rep.add("W", "V19", f"pitfalls.md:{n}", f"concrete value in the body ({whatv}): {m.group(0)!r}",
                            "§9#1 — push it down to params/ (L3); if it really is general, mark <!-- l3-ok: reason -->")
                    break
        records += parse_blocks(pf, ptext, "L2")
        records += parse_tables(pf, ptext, "L2")
        cur, buf = None, []
        sections = []
        for t in ptext.splitlines():
            if t.startswith("## "):
                if cur is not None:
                    sections.append((cur, "\n".join(buf)))
                cur, buf = t.lstrip("# ").strip(), []
            elif cur is not None:
                buf.append(t)
        if cur is not None:
            sections.append((cur, "\n".join(buf)))
        for title, body in sections:
            if not body.strip():
                continue
            # §7 "每条必带,缺了不收" is per ENTRY. A pitfall section is an entry, so a
            # section with no provenance line at all must fail here — otherwise the
            # sloppiest packages are exactly the ones the checker cannot see.
            if not any(FIELD_LINE.match(t) for t in body.splitlines()):
                rep.add("E", "V06d", f"pitfalls.md [{title[:32]}]",
                        "pitfall entry carries no provenance at all",
                        "§7 — every entry carries 来源/日期/复现记录/验证方式/置信度")
            m = re.search(r"涉及事实[^\n]*", body)
            if not m:
                rep.add("E", "V20", f"pitfalls.md [{title[:32]}]",
                        "pitfall has no 涉及事实 line — cannot tell whether it was split into L2 + L3",
                        "§4/§8 — a pitfall must be split; a method-only one says 涉及事实:无(纯方法层) explicitly")
                continue
            val = m.group(0)
            if re.search(r"无|none|纯方法", val):
                continue
            tgts = re.findall(r"params/[\w.-]+\.md", val)
            if not tgts:
                rep.add("E", "V20b", f"pitfalls.md [{title[:32]}]",
                        "涉及事实 neither points at params/ nor declares 无", "§4 — split into an L2 lesson and an L3 fact")
            for tg in tgts:
                if "<" in tg or not os.path.isfile(os.path.join(pkg, tg)):
                    rep.add("E", "V20c", f"pitfalls.md [{title[:32]}]", f"涉及事实 points at a missing file: {tg}", "§10")

    # params
    for fn in have_params:
        p = os.path.join(params_dir, fn)
        ptext = read(p)
        if fn.startswith("_"):
            continue
        recs = parse_tables(p, ptext, "L3")
        records += recs
        # a fact table without a 置信度 column is invisible to parse_tables — which
        # means an entire params file can be unchecked while reporting 0 findings
        plines = ptext.splitlines()
        for i in range(len(plines) - 1):
            if plines[i].strip().startswith("|") and re.match(r"^\s*\|[\s:|-]+\|\s*$", plines[i + 1]):
                hdrs = [c.strip() for c in plines[i].strip().strip("|").split("|")]
                if len(hdrs) >= 3 and not any(FIELD_CONF.search(h) for h in hdrs):
                    rep.add("E", "V06e", f"params/{fn}:{i + 1}",
                            "fact table has no 置信度 column — nothing in it can be checked",
                            "§7 — every L3 fact carries the five provenance fields")
        records += parse_blocks(p, ptext, "L3")
        for r in recs:
            for h, v in zip(r.get("headers", []), r.get("cells", [])):
                if re.search(r"why", h, re.I) or FIELD_REPRO.search(h):
                    continue  # the version-bound why column is a legitimate place for it
                if v and len(v) > WHY_CELL_LEN and re.search(r"因为|所以|为了|之所以|because", v):
                    rep.add("W", "V21", f"params/{fn}:{r['line']}",
                            f"a params cell reads like an explanation of WHY ({len(v)} chars)",
                            "§9#6 — why belongs in L2; a version-bound why goes in its own column")
                    break
        if "替代记录" not in ptext and "supersede" not in ptext.lower():
            rep.add("W", "V22", f"params/{fn}", "no 替代记录 section",
                    "§11 — a changed fact is appended and marked superseded, never silently overwritten")

    # ---- V23/V24 runtime neutrality ----
    for rel in _all_text(pkg):
        p = os.path.join(pkg, rel)
        for n, t, in_fence in strip_fences(read(p).splitlines()):
            if EXEMPT_RT.search(t):
                continue
            m = USERPATH.search(t)
            if m:
                rep.add("E", "V24", f"{rel}:{n}", f"absolute user path: {m.group(0)!r}", "spec — runtime-neutrality hard rule")
            m = RUNTIME_PATH.search(t)
            if m:
                rep.add("E", "V23", f"{rel}:{n}", f"runtime-specific install path: {m.group(0)!r}",
                        "spec — other runtimes refuse such a package; use a relative path")
            names = set(x.lower() for x in RUNTIME_NAME.findall(t))
            if len(names) == 1 and not in_fence:
                rep.add("W", "V23b", f"{rel}:{n}", f"names a single runtime: {list(names)[0]!r}",
                        "spec — avoid \"inside X\" phrasing; if the example is needed, mark <!-- runtime-ok: reason -->")

    # ---- provenance + confidence over every record ----
    for r in records:
        check_record(r, rep, pkg)
    if not records:
        rep.add("W", "V06c", name, "no provenance-bearing entry anywhere in the package",
                "§7 — a knowledge package without it is incomplete; a pure process skill (the distiller itself) has none by nature")


EXPLAIN = """whetstone verify — the full check list (34 codes)

Rules live in references/extraction-framework.md and spec/skill-package.md.
This is the mechanically decidable subset of them, made executable.
E = error (exit 1) · W = warning (exit 1 only with --strict) · I = info

STRUCTURE & PACKAGE INTEGRITY
  V01   SKILL.md exists; frontmatter has name + description                     E
  V02   name is kebab-case                                                      E
  V02b  frontmatter name matches the directory name                             W
  V03   params/*.md and pitfalls.md pointers in the body resolve                E
  V04   every params/ platform is listed under 已支持平台                        W
  V05   no build/OS junk shipped (.pyc / .DS_Store / archives / editor .bak)    W
  V05b  no link points outside the package                                      E

PROVENANCE — five fields per entry (§7)
  V06   来源 / 日期 / 复现记录 / 置信度 are all present                           E
  V06b  验证方式 absent — legal, but caps confidence at med                      W
  V06c  the package carries no provenance-bearing entry at all                   W
  V06d  a pitfalls.md entry carries no provenance at all                         E
  V06e  a params fact table has no 置信度 column (its rows are uncheckable)       E
  V07   dates are absolute YYYY-MM-DD, not "current" / "recently"               E
  V07b  a relative time word appears inside a date field                        W
  V08   来源 is traceable — no "as mentioned earlier"                            E
  V08b  来源 shows a commit hash or session/transcript marker                     W
  V09   置信度 is one of high / med / low                                        E
  V09c  置信度 spelled "medium" instead of "med"                                  W
  V09b  an inline 置信 claim with no provenance record behind it                  E if high, else W

MECHANICAL CONFIDENCE TABLE (§7)
  V10   declared level exceeds what the table allows                            E
  V11   declared level is below the cap — a reviewer downgrade, which is legal   I
  V12   L1/L2 seen on one platform is capped at low, verified or not            E
  V13b  验证方式 states neither 实测:通过 <date> nor 未实测                        W
        (the table: high = tested-and-passed AND >=2 reproduction lines;
         med = >=2 lines, OR verified once and only for an L3 fact; else low.
         A reviewer may downgrade any entry and may never upgrade past the
         conditions — hence V10/V12 are errors and V11 is only info.)

REPRODUCTION RECORDS (§7)
  V14   复现记录 is a list, not a bare count like "3 次"                          E
  V15   each line reads <platform/project> · <date> · <pointer>. Without the
        separator a line has no platform key, so it cannot count toward the
        gate and is excluded from it                          E for L1/L2, else W
  V16   two lines for the same platform/project — inflating the count.
        In an L3 file two byte-identical lines are one event, not two          E
  V17   same key spelled two ways (would slip past V16)                         W
  V18   >=2 distinct platforms reached — eligible for promotion into L2         I

LAYERING DISCIPLINE (§4 / §9)
  V19   no concrete value (hex / IP / system path / pinned version / quantity)
        in the SKILL.md body                                                    W
  V20   every pitfall declares 涉及事实 — proof it was split into L2 + L3         E
  V20b  涉及事实 points at params/ or explicitly declares 无                      E
  V20c  the params/ file 涉及事实 points at exists                                E
  V21   no paragraph of WHY inside a params cell                                W
  V22   params/ has a 替代记录 section (§11: append, never overwrite)             W

RUNTIME NEUTRALITY (spec/skill-package.md)
  scope: package content only — markdown at the package root (excluding README /
  CLAUDE / AGENTS / CONTRIBUTING / CHANGELOG, which are repo furniture) plus
  params/, knowledge/ and scripts/. A tool repository's own implementation is not
  package content and is not scanned.
  V23   no runtime-specific install path (~/.claude, .claude/skills, ...)       E
  V23b  no phrasing that binds the package to a single named runtime            W
  V24   no absolute user path (/home/x/, /Users/x/, C:\\Users\\)                  E

INLINE EXEMPTIONS
  <!-- l3-ok: reason -->       suppress V19 on that line
  <!-- runtime-ok: reason -->  suppress V23/V23b/V24 on that line

DELIBERATELY NOT DECIDED — these stay with the human reviewer (Phase 4).
Mechanising a judgement that is not mechanical only manufactures false positives:
  · is an L1 entry really exception-free (§8)
  · does an L2 lesson survive deleting every platform-specific value (§8)
  · was a contradiction preserved rather than averaged away (§6)
  · were this session's reproduction write-backs applied (§8) — needs the
    session, which is not in the package
  · when in doubt, was the entry placed lower rather than higher (§3) — only the
    outcome is visible, never the reasoning
Redaction is also out of scope: run tech-writing-gate and your own sensitive-term
list before publishing, rather than maintaining a second word list here.
"""


def main():
    ap = argparse.ArgumentParser(description="whetstone verify — evidence discipline in a skill package")
    ap.add_argument("pkgs", nargs="*", help="skill package dir(s)")
    ap.add_argument("--src", help="a skills library dir; verify every */SKILL.md under it")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    ap.add_argument("--brief", action="store_true", help="findings only, without the rule-reference line")
    ap.add_argument("--explain", action="store_true", help="print the check list and what is NOT checked")
    args = ap.parse_args()

    if args.explain:
        print(EXPLAIN)
        return 0

    targets = list(args.pkgs)
    if args.src:
        if not os.path.isdir(args.src):
            print(f"src not found: {args.src}", file=sys.stderr)
            return 2
        targets += [os.path.join(args.src, d) for d in sorted(os.listdir(args.src))
                    if os.path.isfile(os.path.join(args.src, d, "SKILL.md"))]
    if not targets:
        print("nothing to verify — give a package dir or --src <skills-dir>", file=sys.stderr)
        return 2

    all_out, tE, tW, tI = [], 0, 0, 0
    for pkg in targets:
        if not os.path.isdir(pkg):
            print(f"not a directory: {pkg}", file=sys.stderr)
            return 2
        rep = Report()
        check_package(pkg, rep)
        e, w, i = rep.counts()
        tE, tW, tI = tE + e, tW + w, tI + i
        all_out.append({"package": os.path.basename(os.path.abspath(pkg)),
                        "path": pkg, "errors": e, "warnings": w, "infos": i,
                        "items": rep.items})

    if args.json:
        print(json.dumps({"packages": all_out, "errors": tE, "warnings": tW, "infos": tI},
                         ensure_ascii=False, indent=2))
    else:
        for p in all_out:
            print(f"whetstone verify — {p['path']}")
            for sev, label in (("E", "ERROR"), ("W", "WARN"), ("I", "INFO")):
                grp = [x for x in p["items"] if x["sev"] == sev]
                if not grp:
                    continue
                print(f"\n{label} ({len(grp)})")
                for x in grp:
                    mark = {"E": "✗", "W": "!", "I": "i"}[sev]
                    print(f"  {mark} {x['where']}  [{x['code']}] {x['msg']}")
                    if x["fix"] and not args.brief:
                        print(f"      → {x['fix']}")
            print(f"\nsummary: {p['errors']} error(s), {p['warnings']} warning(s), {p['infos']} info\n")
        if len(all_out) > 1:
            print(f"total: {tE} error(s), {tW} warning(s), {tI} info across {len(all_out)} package(s)")

    if tE:
        return 1
    if tW and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
