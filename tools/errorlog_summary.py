#!/usr/bin/env python3
"""Group HoI4 error.log lines so NHMMAP problems stand out.

Usage:
  tools/errorlog_summary.py [error.log] [--baseline vanilla_error.log]

Default log: Documents/Paradox Interactive/Hearts of Iron IV/logs/error.log.
Errors are grouped by message with numbers and quoted values blanked out. Groups
that mention a file NHMMAP ships are listed first. With --baseline (an
error.log from a vanilla run), groups that also appear in vanilla are hidden.
"""
import argparse
import collections
import os
import re
import subprocess

LINE = re.compile(r"^(?:\[[^\]]*\])+: (.*)$")


def template(msg):
    msg = re.sub(r'"[^"]*"', '"…"', msg)
    msg = re.sub(r"'[^']*'", "'…'", msg)
    return re.sub(r"\d+", "N", msg)


def load(path):
    groups = collections.defaultdict(list)
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = LINE.match(line.rstrip("\r\n"))
            if m:
                groups[template(m.group(1))].append(m.group(1))
    return groups


def main():
    default = os.path.join(os.path.expanduser("~"), "Documents", "Paradox Interactive",
                           "Hearts of Iron IV", "logs", "error.log")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", nargs="?", default=default)
    ap.add_argument("--baseline")
    args = ap.parse_args()
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    mod_files = set(subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True).stdout.split())
    groups = load(args.log)
    base = set(load(args.baseline)) if args.baseline else set()
    rows = []
    for t, msgs in groups.items():
        if t in base:
            continue
        ours = any(f in m for m in msgs[:50] for f in mod_files if "/" in f)
        rows.append((not ours, -len(msgs), t, msgs))
    rows.sort()
    for not_ours, neg, t, msgs in rows:
        tag = "NHMMAP" if not not_ours else "other "
        print(f"[{tag}] x{-neg}: {msgs[0][:220]}")
    print(f"\n{len(rows)} error groups ({sum(1 for r in rows if not r[0])} mention NHMMAP files)"
          + (f", {len(groups) - len(rows)} hidden as also in vanilla baseline" if base else ""))


if __name__ == "__main__":
    main()
