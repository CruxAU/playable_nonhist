#!/usr/bin/env python3
"""Find `has_game_rule = { rule = X option = Y }` checks (in vanilla files the mod
doesn't override, and in the mod itself) whose rule or option the effective game
rules don't define. Such checks are silently always false.

Usage: tools/rule_option_check.py <game_dir> [mod_dir=.]
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from object_inventory import read_source, tokenize, parse  # noqa: E402

PAT = re.compile(r"rule\s*=\s*([A-Za-z0-9_]+)\s+option\s*=\s*([A-Za-z0-9_]+)")


def rule_options(files):
    by_key, by_name = {}, {}
    for p, t in files.items():
        if not p.startswith("common/game_rules/"):
            continue
        for k, _, v in parse(tokenize(t)):
            if not isinstance(v, list):
                continue
            opts = set()
            name = None
            for k2, _, v2 in v:
                if k2 == "name" and isinstance(v2, str):
                    name = v2.strip('"')
                if k2 in ("option", "default") and isinstance(v2, list):
                    for k3, _, v3 in v2:
                        if k3 == "name" and isinstance(v3, str):
                            opts.add(v3.strip('"'))
            by_key[k.upper()] = opts
            if name:
                by_name[name.upper()] = opts
    return by_key, by_name


def main():
    game = sys.argv[1]
    mod_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    vanilla = {p: t for p, t in read_source(game).items() if p.startswith(("common/", "events/"))}
    mod = read_source(mod_dir)
    eff = dict(vanilla)
    eff.update(mod)
    by_key, by_name = rule_options(eff)
    missing = collections.defaultdict(set)
    for p, t in eff.items():
        if p.startswith("common/game_rules/"):
            continue
        code = re.sub(r"#[^\n]*", "", t)
        for rule, opt in PAT.findall(code):
            opts = by_key.get(rule.upper()) or by_name.get(rule.upper())
            if opts is None:
                missing[(rule, "<no such rule>")].add(p)
            elif opt not in opts:
                missing[(rule, opt)].add(p)
    for (rule, opt), ps in sorted(missing.items()):
        src = ", ".join(("NHMMAP:" if p in mod else "vanilla:") + p for p in sorted(ps))
        print(f"{rule}\t{opt}\t{src}")


if __name__ == "__main__":
    main()
