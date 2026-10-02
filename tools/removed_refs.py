#!/usr/bin/env python3
"""Find NHMMAP references to things the game update removed.

Collects every object key (focus, idea, event, decision, character, scripted
trigger/effect, AI plan, loc key, ...) defined in the OLD game version that is
no longer defined anywhere in the NEW effective game (new vanilla + NHMMAP).
Then reports every place an NHMMAP file still uses one of those names outside
comments.

Usage: tools/removed_refs.py <old_game_dir> <new_game_dir> [mod_dir=.]
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from object_inventory import effective_loc, inventory, read_source  # noqa: E402

SKIP_KINDS = {"namespace", "events:other", "decisions:other", "national_focus:search_filter_prios"}
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")


def keys(files):
    """(kind, key) pairs, so a focus that is gone still counts as gone even if its loc key remains."""
    return {(kind, key) for kind, key, _, _ in effective_loc(inventory(files))
            if kind not in SKIP_KINDS and kind != "loc"}


def scoped(files):
    return {p: t for p, t in files.items() if p.startswith(("common/", "events/", "localisation/english/"))}


def main():
    old_dir, new_dir = sys.argv[1], sys.argv[2]
    mod_dir = sys.argv[3] if len(sys.argv) > 3 else "."
    sys.stderr.write("reading...\n")
    old = scoped(read_source(old_dir))
    new = scoped(read_source(new_dir))
    mod = read_source(mod_dir)
    effective = dict(new)
    effective.update(mod)
    gone = keys(old) - keys(effective)
    kinds_of = collections.defaultdict(set)
    for kind, key in gone:
        kinds_of[key].add(kind)
    removed = {k for k in kinds_of if len(k) > 3 and "_" in k}  # skip generic words
    sys.stderr.write(f"{len(removed)} names defined in old version are gone\n")
    hits = collections.defaultdict(list)
    for path, text in mod.items():
        if path.endswith(".yml"):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            code = line.split("#", 1)[0]
            for w in WORD.findall(code):
                if w in removed:
                    hits[w].append(f"{path}:{n}")
    for w in sorted(hits):
        locs = hits[w]
        print(f"{w}\t{'/'.join(sorted(kinds_of[w]))}\t{len(locs)}\t{', '.join(locs[:6])}{' ...' if len(locs) > 6 else ''}")
    sys.stderr.write(f"{len(hits)} removed names still referenced by NHMMAP\n")


if __name__ == "__main__":
    main()
