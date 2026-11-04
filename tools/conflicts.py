#!/usr/bin/env python3
"""Inspect and resolve zdiff3 merge conflict hunks (from `git -c merge.conflictStyle=zdiff3 merge`).

Usage:
  tools/conflicts.py list                      all conflicted files with hunk counts
  tools/conflicts.py show FILE [N]             print hunk N (1-based) or all hunks: ours / base / theirs
  tools/conflicts.py resolve FILE N CHOICE     replace hunk N with CHOICE:
        ours | theirs | both (ours then theirs) | both-rev (theirs then ours)
        file:PATH   the contents of PATH (verbatim)
  Resolve hunks from the highest N down, or re-run `show` after each resolve: numbering shifts.
Keeps the file's line endings and BOM.
"""
import re
import subprocess
import sys

START, BASE, MID, END = "<<<<<<< ", "||||||| ", "=======", ">>>>>>> "


def load(path):
    raw = open(path, "rb").read().decode("utf-8")
    bom = raw.startswith("﻿")
    nl = "\r\n" if "\r\n" in raw else "\n"
    return raw.lstrip("﻿").replace("\r\n", "\n"), nl, bom


def save(path, text, nl, bom):
    open(path, "wb").write((("﻿" if bom else "") + text.replace("\n", nl)).encode("utf-8"))


def hunks(text):
    """[(start, end, ours, base, theirs)] as character offsets and line lists."""
    lines = text.split("\n")
    out, i, pos = [], 0, []
    offs = [0]
    for l in lines:
        offs.append(offs[-1] + len(l) + 1)
    while i < len(lines):
        if lines[i].startswith(START):
            s = i
            ours, base, theirs, part = [], [], [], "ours"
            i += 1
            while not lines[i].startswith(END):
                l = lines[i]
                if l.startswith(BASE) and part == "ours":
                    part = "base"
                elif l == MID or (l.startswith(MID) and l.strip() == MID):
                    part = "theirs"
                else:
                    {"ours": ours, "base": base, "theirs": theirs}[part].append(l)
                i += 1
            out.append((offs[s], offs[i + 1], ours, base, theirs))
        i += 1
    return out


def main():
    cmd = sys.argv[1]
    if cmd == "list":
        files = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], capture_output=True, text=True).stdout.split()
        for f in files:
            print(f"{len(hunks(load(f)[0])):3} {f}")
        return
    path = sys.argv[2]
    text, nl, bom = load(path)
    hs = hunks(text)
    if cmd == "show":
        sel = [int(sys.argv[3])] if len(sys.argv) > 3 else range(1, len(hs) + 1)
        for n in sel:
            _, _, o, b, t = hs[n - 1]
            print(f"===== {path} hunk {n}/{len(hs)}")
            for name, part in (("OURS (NHMMAP)", o), ("BASE", b), ("THEIRS (vanilla 1.19.4)", t)):
                print(f"--- {name} ({len(part)} lines)")
                print("\n".join(part))
        return
    if cmd == "resolve":
        n, choice = int(sys.argv[3]), sys.argv[4]
        s, e, o, b, t = hs[n - 1]
        if choice == "ours":
            new = o
        elif choice == "theirs":
            new = t
        elif choice == "both":
            new = o + t
        elif choice == "both-rev":
            new = t + o
        elif choice.startswith("file:"):
            new = open(choice[5:], encoding="utf-8").read().replace("\r\n", "\n").rstrip("\n").split("\n")
        else:
            raise SystemExit("bad choice")
        rep = "\n".join(new) + ("\n" if new else "")
        save(path, text[:s] + rep + text[e:], nl, bom)
        print(f"{path}: hunk {n} -> {choice} ({len(new)} lines); {len(hs) - 1} left")


if __name__ == "__main__":
    main()
