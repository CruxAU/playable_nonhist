#!/usr/bin/env python3
"""Move NHMMAP-only objects out of vanilla override files into NHMMAP_<file>.

An object is NHMMAP-only when its key exists neither in the vanilla-branch copy
of the same file (the merge base) nor anywhere in the same folder of the
current game install. That second check keeps vanilla content added after the
baseline (e.g. 1.17.4 additions) in place.

Objects are cut with their exact text, including directly attached comment
lines. Referenced @constants and the add_namespace lines of moved events are
copied along.

Usage:
  tools/extract_objects.py <game_dir> <file> [<file> ...] [--dry-run]

Supported folders: ai_strategy_plans, ai_strategy, game_rules,
scripted_triggers, scripted_effects (top-level objects), decisions (decisions
inside categories; categories in decisions/categories), events (events).

Verify afterwards:
  tools/object_inventory.py compare git:HEAD . --layer git:vanilla
"""
import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from object_inventory import OPS, TOKEN_RE, objects_for  # noqa: E402

TOP_LEVEL = {"ai_strategy_plans", "ai_strategy", "game_rules", "scripted_triggers",
             "scripted_effects", "decisions/categories"}
EVENT_KEYS = {"country_event", "news_event", "state_event", "unit_leader_event",
              "operative_leader_event", "event"}
CONST_RE = re.compile(r"@[A-Za-z0-9_]+")


def tokens_with_pos(text):
    return [(m.group(0), m.start(), m.end()) for m in TOKEN_RE.finditer(text)
            if not m.group(0).startswith("#")]


def entries(toks, lo, hi):
    """Entries in toks[lo:hi]: (key, start, end, inner_lo, inner_hi)."""
    out = []
    i = lo
    while i < hi:
        t, s, _ = toks[i]
        if t in "{}":
            if t == "{":
                i = match(toks, i) + 1
            else:
                i += 1
            continue
        if i + 1 < hi and toks[i + 1][0] in OPS:
            j = i + 2
            if j < hi and toks[j][0] == "{":
                k = match(toks, j)
                out.append((t, s, toks[k][2], j + 1, k))
                i = k + 1
            else:
                out.append((t, s, toks[j][2] if j < hi else toks[i + 1][2], None, None))
                i = j + 1
            continue
        i += 1
    return out


def match(toks, i):
    depth = 0
    for j in range(i, len(toks)):
        if toks[j][0] == "{":
            depth += 1
        elif toks[j][0] == "}":
            depth -= 1
            if depth == 0:
                return j
    return len(toks) - 1


def line_span(text, start, end):
    """Widen [start, end) to whole lines, pulling in comment lines directly above."""
    ls = text.rfind("\n", 0, start) + 1
    while ls > 0:
        prev_start = text.rfind("\n", 0, ls - 1) + 1
        prev = text[prev_start:ls - 1].strip()
        if prev.startswith("#") and not prev.startswith("###"):
            ls = prev_start
        else:
            break
    le = text.find("\n", end)
    le = len(text) if le == -1 else le + 1
    rest = text[end:le].strip()
    if rest and not rest.startswith("#"):
        raise ValueError(f"trailing content after object at offset {end}: {rest!r}")
    return ls, le


def folder_of(path):
    parts = path.replace("\\", "/").split("/")
    if parts[0] == "events":
        return "events"
    sub = "/".join(parts[1:-1])
    return sub


def vanilla_keys(game_dir, path, kind_filter):
    """Keys defined in the merge-base copy of `path`'s folder and anywhere in that folder in game_dir."""
    keys = set()
    base_files = subprocess.run(["git", "ls-tree", "--name-only", f"vanilla:{os.path.dirname(path)}/"],
                                capture_output=True, text=True).stdout.split()
    for f in base_files:
        rel = os.path.dirname(path) + "/" + f
        base = subprocess.run(["git", "show", f"vanilla:{rel}"], capture_output=True)
        if base.returncode == 0:
            for kind, key, _ in objects_for(rel, base.stdout.decode("utf-8-sig", errors="replace")):
                if kind in kind_filter:
                    keys.add(key)
    folder = os.path.join(game_dir, os.path.dirname(path))
    for f in os.listdir(folder):
        full = os.path.join(folder, f)
        if f.endswith(".txt") and os.path.isfile(full):
            rel = os.path.dirname(path) + "/" + f
            with open(full, encoding="utf-8-sig", errors="replace") as fh:
                for kind, key, _ in objects_for(rel, fh.read()):
                    if kind in kind_filter:
                        keys.add(key)
    return keys


def get_id(text, toks, lo, hi):
    for key, s, e, ilo, _ in entries(toks, lo, hi):
        if key == "id" and ilo is None:
            return text[s:e].split("=", 1)[1].strip()
    return None


def plan(path, text, known):
    """Return (cuts, target_text_parts) where cuts are (start, end) spans to remove."""
    folder = folder_of(path)
    toks = tokens_with_pos(text)
    top = entries(toks, 0, len(toks))
    cuts, chunks = [], []

    if folder in TOP_LEVEL:
        for key, s, e, _, _ in top:
            if not key.startswith("@") and key not in known:
                cuts.append(line_span(text, s, e))
                chunks.append((None, cuts[-1]))
    elif folder == "decisions":
        for cat, _, _, ilo, ihi in top:
            if ilo is None:
                continue
            for key, s, e, _, _ in entries(toks, ilo, ihi):
                if key not in known:
                    cuts.append(line_span(text, s, e))
                    chunks.append((cat, cuts[-1]))
    elif folder == "events":
        for key, s, e, ilo, ihi in top:
            if key in EVENT_KEYS and ilo is not None:
                eid = get_id(text, toks, ilo, ihi)
                if eid and eid not in known:
                    cuts.append(line_span(text, s, e))
                    chunks.append((None, cuts[-1]))
    else:
        raise SystemExit(f"unsupported folder for {path}: {folder}")
    return top, cuts, chunks


def build_target(path, text, top, chunks):
    folder = folder_of(path)
    moved_text = "".join(text[a:b] for _, (a, b) in chunks)
    header = []
    for key, s, e, ilo, _ in top:
        if key.startswith("@") and ilo is None and key in set(CONST_RE.findall(moved_text)):
            header.append(text[s:e])
        if folder == "events" and key == "add_namespace":
            ns = text[s:e].split("=", 1)[1].strip()
            if re.search(rf"\bid\s*=\s*{re.escape(ns)}\.", moved_text):
                header.append(text[s:e])
    out = ["# NHMMAP-only objects extracted from vanilla override " + path + "\n"]
    if header:
        out.append("\n".join(header) + "\n")
    out.append("\n")
    if folder == "decisions":
        by_cat = {}
        for cat, (a, b) in chunks:
            by_cat.setdefault(cat, []).append(text[a:b])
        for cat, parts in by_cat.items():
            out.append(f"{cat} = {{\n\n" + "\n".join(p.rstrip("\n") + "\n" for p in parts) + "}\n\n")
    else:
        out.append("\n".join(text[a:b].rstrip("\n") + "\n" for _, (a, b) in chunks))
    return "".join(out)


def kinds_for(folder):
    if folder == "events":
        return {"event"}
    if folder == "decisions":
        return {"decision"}
    return {folder}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("game_dir")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    os.chdir(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                            text=True, check=True).stdout.strip())
    total = 0
    for path in args.files:
        path = path.replace("\\", "/")
        folder = folder_of(path)
        with open(path, encoding="utf-8", newline="") as fh:
            raw = fh.read()
        bom = raw.startswith("﻿")
        text = raw[1:] if bom else raw
        known = vanilla_keys(args.game_dir, path, kinds_for(folder))
        top, cuts, chunks = plan(path, text, known)
        if not cuts:
            continue
        total += len(cuts)
        target = os.path.join(os.path.dirname(path), "NHMMAP_" + os.path.basename(path))
        print(f"{path}: {len(cuts)} objects -> {target}")
        if args.dry_run:
            continue
        if os.path.exists(target):
            raise SystemExit(f"refusing to overwrite existing {target}")
        new_target = build_target(path, text, top, chunks)
        remaining = []
        pos = 0
        for a, b in sorted(cuts):
            remaining.append(text[pos:a])
            pos = b
        remaining.append(text[pos:])
        newline = "\r\n" if "\r\n" in text else "\n"
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(("﻿" if bom else "") + "".join(remaining))
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(("﻿" if bom else "") + new_target.replace("\r\n", "\n").replace("\n", newline))
    print(f"total: {total} objects")


if __name__ == "__main__":
    main()
