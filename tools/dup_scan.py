#!/usr/bin/env python3
"""Find IDs defined more than once in the effective game (vanilla + NHMMAP).

The effective file set is every vanilla file, with files the mod ships at the
same path replaced by the mod's copy, plus the mod's own files. Duplicates that
vanilla already has on its own are reported separately (not our problem).

Usage: tools/dup_scan.py <game_dir> [mod_dir=.]
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from object_inventory import effective_loc, inventory, read_source  # noqa: E402

KINDS = {"focus", "focus_tree", "event", "decision", "decisions/categories", "idea", "character",
         "scripted_triggers", "scripted_effects", "ai_strategy", "ai_strategy_plans", "game_rules",
         "loc"}


def index(inv):
    d = collections.defaultdict(list)
    for kind, key, h, path in inv:
        if kind in KINDS:
            d[(kind, key)].append(path)
    return d


def main():
    game = sys.argv[1]
    mod = sys.argv[2] if len(sys.argv) > 2 else "."
    sys.stderr.write("reading vanilla...\n")
    vanilla = {p: t for p, t in read_source(game).items()
               if p.startswith(("common/", "events/", "localisation/english/"))}
    modfiles = read_source(mod)
    effective = dict(vanilla)
    effective.update(modfiles)
    sys.stderr.write("indexing...\n")
    van_dups = {k for k, v in index(effective_loc(inventory(vanilla))).items() if len(v) > 1}
    eff = index(effective_loc(inventory(effective)))
    rows = []
    for (kind, key), paths in sorted(eff.items()):
        if len(paths) > 1 and (kind, key) not in van_dups and any(p in modfiles for p in paths):
            rows.append((kind, key, paths))
    for kind, key, paths in rows:
        tag = ["NHMMAP:" + p if p in modfiles else "vanilla:" + p for p in paths]
        print(f"{kind}\t{key}\t{' | '.join(tag)}")
    sys.stderr.write(f"{len(rows)} duplicates involving NHMMAP files\n")


if __name__ == "__main__":
    main()
