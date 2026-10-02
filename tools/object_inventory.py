#!/usr/bin/env python3
"""Inventory of HoI4 script objects (focuses, events, decisions, ideas, rules,
AI plans, scripted triggers/effects, on_actions, loc keys, ...) with a hash of
each object's normalised content (comments and whitespace ignored).

Sources are a directory or a git ref written as git:<ref> (e.g. git:HEAD,
git:vanilla). Use "." for the working tree.

  dump    SOURCE                      print kind, key, hash, file
  compare A B [--layer SRC] [--only K] [--quiet-moved]
          Compare two sources. --layer SRC adds every file of SRC that is not
          present in A/B (models "override deleted -> vanilla shows through";
          use --layer git:vanilla). --only limits output to these kinds
          (comma-separated). Exit code 1 if anything other than moves differs.

Typical uses:
  # what NHMMAP removed/changed/added relative to vanilla
  tools/object_inventory.py compare git:vanilla git:HEAD
  # extraction refactor check: nothing may differ except file locations
  tools/object_inventory.py compare git:HEAD . --layer git:vanilla
"""
import argparse
import collections
import hashlib
import os
import re
import subprocess
import sys

sys.setrecursionlimit(20000)

CONTENT_DIRS = ("common/", "events/", "localisation/", "interface/", "history/")
EXTS = (".txt", ".yml", ".gfx")
OPS = {"=", "<", ">", "<=", ">=", "!=", "==", "?="}
TOKEN_RE = re.compile(r'"(?:\\.|[^"\\])*"|#[^\n]*|[{}]|[<>!?=]=|[<>=]|[^\s{}=<>!?#"]+|[!?]')
LOC_RE = re.compile(r'^\s*([^\s#:"]+):\d*\s*"(.*)"\s*(?:#.*)?$')
EVENT_KEYS = {"country_event", "news_event", "state_event", "unit_leader_event",
              "operative_leader_event", "event"}


# ---------------------------------------------------------------- parsing

def tokenize(text):
    return [t for t in TOKEN_RE.findall(text) if not t.startswith("#")]


def parse(tokens):
    """Return list of entries: (key, op, value) or (None, None, value).
    value is a str or a nested entry list. Stray '}' at top level is skipped."""
    pos = 0
    n = len(tokens)

    def block():
        nonlocal pos
        items = []
        while pos < n:
            t = tokens[pos]
            if t == "}":
                pos += 1
                return items
            if t == "{":
                pos += 1
                items.append((None, None, block()))
                continue
            if pos + 1 < n and tokens[pos + 1] in OPS:
                key, op = t, tokens[pos + 1]
                pos += 2
                if pos < n and tokens[pos] == "{":
                    pos += 1
                    items.append((key, op, block()))
                elif pos < n:
                    items.append((key, op, tokens[pos]))
                    pos += 1
                continue
            items.append((None, None, t))
            pos += 1
        return items

    top = []
    while pos < n:
        top.extend(block())
    return top


def canon(value):
    if isinstance(value, str):
        return value
    return "{" + " ".join(canon_entry(e) for e in value) + "}"


def canon_entry(entry):
    k, op, v = entry
    return canon(v) if k is None else f"{k}{op}{canon(v)}"


def digest(*parts):
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:12]


def get(entries, key):
    for k, _, v in entries:
        if k == key and isinstance(v, str):
            return v.strip('"')
    return None


# ---------------------------------------------------------------- object extraction

def objects_for(path, text):
    """Yield (kind, key, hash) for one file."""
    if path.endswith(".yml"):
        for line in text.splitlines():
            m = LOC_RE.match(line)
            if m:
                kind = "loc_replace" if "/replace/" in path else "loc"
                yield kind, m.group(1), digest(m.group(2))
        return

    entries = parse(tokenize(text))
    folder = path.split("/")
    sub = "/".join(folder[:-1])

    if path.endswith(".gfx"):
        for k, _, v in entries:
            if isinstance(v, list):
                for k2, _, v2 in v:
                    if isinstance(v2, list):
                        name = get(v2, "name")
                        yield f"gfx:{k2}", name or "?", digest(canon(v2))
        return

    if sub == "common/national_focus":
        for k, _, v in entries:
            if not isinstance(v, list):
                continue
            if k == "focus_tree":
                tid = get(v, "id") or "?"
                rest = []
                for e in v:
                    if e[0] in ("focus", "shared_focus") and isinstance(e[2], list):
                        yield "focus", get(e[2], "id") or "?", digest(canon(e[2]))
                    else:
                        rest.append(e)
                yield "focus_tree", tid, digest(canon(rest))
            elif k in ("shared_focus", "joint_focus", "focus"):
                yield "focus", get(v, "id") or "?", digest(canon(v))
            else:
                yield f"national_focus:{k}", k, digest(canon(v))
        return

    if folder[0] == "events":
        for k, _, v in entries:
            if k in EVENT_KEYS and isinstance(v, list):
                yield "event", get(v, "id") or "?", digest(k, canon(v))
            elif k == "add_namespace":
                yield "namespace", str(v), digest(str(v))
            else:
                yield "events:other", str(k), digest(canon_entry((k, "=", v)))
        return

    if sub == "common/decisions":
        for k, _, v in entries:
            if isinstance(v, list):
                for k2, op2, v2 in v:
                    yield "decision", str(k2), digest(k, canon_entry((k2, op2, v2)))
            else:
                yield "decisions:other", str(k), digest(str(v))
        return

    nested = {
        "common/ideas": ("ideas", 2, "idea"),
        "common/characters": ("characters", 1, "character"),
        "common/on_actions": ("on_actions", 1, "on_action"),
    }
    if sub in nested:
        container, depth, kind = nested[sub]
        for k, op, v in entries:
            if k == container and isinstance(v, list):
                if depth == 1:
                    for k2, op2, v2 in v:
                        yield kind, str(k2), digest(canon_entry((k2, op2, v2)))
                else:
                    for slot, _, slot_v in v:
                        if isinstance(slot_v, list):
                            for k3, op3, v3 in slot_v:
                                yield kind, str(k3), digest(str(slot), canon_entry((k3, op3, v3)))
            else:
                yield f"{sub[7:]}:other", str(k), digest(canon_entry((k, op, v)))
        return

    kind = sub[len("common/"):] if sub.startswith("common/") else sub
    for k, op, v in entries:
        yield kind, str(k), digest(canon_entry((k, op, v)))


# ---------------------------------------------------------------- sources

def wanted(path):
    return path.startswith(CONTENT_DIRS) and path.endswith(EXTS)


def read_source(spec):
    """Return {path: text}."""
    files = {}
    if spec.startswith("git:"):
        ref = spec[4:]
        names = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref],
                               capture_output=True, check=True).stdout.decode("utf-8").splitlines()
        names = [p for p in names if wanted(p)]
        proc = subprocess.run(["git", "cat-file", "--batch"],
                              input="".join(f"{ref}:{p}\n" for p in names).encode("utf-8"),
                              capture_output=True, check=True)
        out, i = proc.stdout, 0
        for p in names:
            header_end = out.index(b"\n", i)
            size = int(out[i:header_end].split()[2])
            data = out[header_end + 1: header_end + 1 + size]
            i = header_end + 1 + size + 1
            files[p] = data.decode("utf-8-sig", errors="replace")
    else:
        for root, dirs, fnames in os.walk(spec):
            dirs[:] = [d for d in dirs if d not in (".git", "tools")]
            for f in fnames:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, spec).replace(os.sep, "/")
                if wanted(rel):
                    with open(full, encoding="utf-8-sig", errors="replace") as fh:
                        files[rel] = fh.read()
    return files


def inventory(files):
    inv = []
    for path in sorted(files):
        for kind, key, h in objects_for(path, files[path]):
            inv.append((kind, key, h, path))
    return inv


def load(spec, layer=None):
    files = read_source(spec)
    if layer:
        for p, t in layer.items():
            files.setdefault(p, t)
    return inventory(files)


# ---------------------------------------------------------------- commands

def cmd_dump(args):
    for kind, key, h, path in load(args.source):
        print(f"{kind}\t{key}\t{h}\t{path}")


def cmd_compare(args):
    layer = read_source(args.layer) if args.layer else None
    a, b = load(args.a, layer), load(args.b, layer)
    only = set(args.only.split(",")) if args.only else None

    def index(inv):
        d = collections.defaultdict(list)
        for kind, key, h, path in inv:
            if only is None or kind in only:
                d[(kind, key)].append((h, path))
        return d

    ia, ib = index(a), index(b)
    removed, added, changed, moved = [], [], [], []
    for ok in sorted(set(ia) | set(ib)):
        va, vb = ia.get(ok, []), ib.get(ok, [])
        if not vb:
            removed.append((ok, va))
        elif not va:
            added.append((ok, vb))
        elif collections.Counter(h for h, _ in va) != collections.Counter(h for h, _ in vb):
            changed.append((ok, va, vb))
        elif sorted(p for _, p in va) != sorted(p for _, p in vb):
            moved.append((ok, va, vb))

    def where(v):
        return ", ".join(sorted({p for _, p in v}))

    def section(title, rows, fmt):
        print(f"== {title}: {len(rows)}")
        for r in rows:
            print("  " + fmt(r))

    section("REMOVED (in A, not in B)", removed, lambda r: f"{r[0][0]}\t{r[0][1]}\t{where(r[1])}")
    section("ADDED (in B, not in A)", added, lambda r: f"{r[0][0]}\t{r[0][1]}\t{where(r[1])}")
    section("CHANGED", changed, lambda r: f"{r[0][0]}\t{r[0][1]}\t{where(r[1])} -> {where(r[2])}")
    if args.quiet_moved:
        print(f"== MOVED (same content, different file): {len(moved)}")
    else:
        section("MOVED (same content, different file)", moved,
                lambda r: f"{r[0][0]}\t{r[0][1]}\t{where(r[1])} -> {where(r[2])}")
    return 1 if (removed or added or changed) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("dump")
    d.add_argument("source")
    c = sp.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("--layer")
    c.add_argument("--only")
    c.add_argument("--quiet-moved", action="store_true")
    args = ap.parse_args()
    if args.cmd == "dump":
        cmd_dump(args)
        return 0
    return cmd_compare(args)


if __name__ == "__main__":
    sys.exit(main())
