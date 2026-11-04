#!/usr/bin/env python3
"""After `git merge vanilla`: find places where NHMMAP's and vanilla's edits sat close together but
didn't overlap, so git merged them silently. These are where a vanilla refactor can undo an NHMMAP
change without a conflict (e.g. vanilla swapping `any_other_country = { original_tag = SOV ... }` for
`any_other_country_with_original_tag_of = { target = { SOV } ... }` right next to a line NHMMAP edited).

Usage: tools/near_merges.py BASE_REF OURS_REF THEIRS_REF [WINDOW=4]
  e.g. tools/near_merges.py vanilla-1.19.3-3 master vanilla-1.19.4
Only files changed on both sides are checked. Prints each near-miss with both sides' changes.
"""
import difflib
import subprocess
import sys


def show(ref, path):
    r = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True)
    return r.stdout.decode("utf-8", "replace").replace("\r\n", "\n").lstrip("﻿").split("\n") if r.returncode == 0 else None


def changed(ref_a, ref_b):
    out = subprocess.run(["git", "diff", "--name-only", ref_a, ref_b], capture_output=True, text=True).stdout.split()
    return {p for p in out if p.startswith(("common/", "events/", "interface/", "history/"))}


def ranges(base, other):
    """[(base_start, base_end, other_lines)] for each changed region, in base line numbers."""
    sm = difflib.SequenceMatcher(None, base, other, autojunk=False)
    return [(i1, i2, other[j1:j2], base[i1:i2]) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]


def main():
    base_ref, ours_ref, theirs_ref = sys.argv[1:4]
    win = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    files = sorted(changed(base_ref, ours_ref) & changed(base_ref, theirs_ref))
    hits = 0
    for path in files:
        base, ours, theirs = show(base_ref, path), show(ours_ref, path), show(theirs_ref, path)
        if not (base and ours and theirs):
            continue
        ro, rt = ranges(base, ours), ranges(base, theirs)
        for os_, oe, olines, obase in ro:
            for ts, te, tlines, tbase in rt:
                overlap = os_ < te and ts < oe
                gap = max(ts - oe, os_ - te)
                if not overlap and gap <= win:
                    hits += 1
                    print(f"===== {path}: base lines {os_+1}-{oe} (NHMMAP) / {ts+1}-{te} (vanilla), gap {gap}")
                    print("  NHMMAP:  " + " | ".join(l.strip() for l in obase)[:150] + "  ->  " + " | ".join(l.strip() for l in olines)[:150])
                    print("  vanilla: " + " | ".join(l.strip() for l in tbase)[:150] + "  ->  " + " | ".join(l.strip() for l in tlines)[:150])
    print(f"\n{hits} near-misses in {len(files)} files changed on both sides")


if __name__ == "__main__":
    main()
