#!/usr/bin/env python3
"""Dissolve vanilla localisation overrides into NHMMAP-owned files.

For each overridden vanilla loc file:
  - keys vanilla doesn't have          -> localisation/<lang>/NHMMAP_<file>
  - vanilla keys with changed text     -> localisation/<lang>/replace/NHMMAP_replace_l_<lang>.yml
  - keys identical to vanilla (merge base or current game) -> dropped
then the override file is deleted.

Usage: tools/extract_loc.py <game_dir> <loc_file> [<loc_file> ...] [--dry-run]
"""
import argparse
import os
import re
import subprocess

LOC_RE = re.compile(r'^\s*([^\s#:"]+):\d*\s*"(.*)"\s*(?:#.*)?$')


def parse(text):
    out = {}
    for line in text.splitlines():
        m = LOC_RE.match(line)
        if m:
            out[m.group(1)] = (m.group(2), line.rstrip("\r"))
    return out


def game_loc(game_dir, lang):
    keys = {}
    root = os.path.join(game_dir, "localisation", lang)
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith(".yml"):
                with open(os.path.join(dirpath, f), encoding="utf-8-sig", errors="replace") as fh:
                    for k, (v, _) in parse(fh.read()).items():
                        keys[k] = v
    return keys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("game_dir")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    os.chdir(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                            text=True, check=True).stdout.strip())

    current = {}
    replace_lines = {}
    for path in args.files:
        path = path.replace("\\", "/")
        lang = path.split("/")[1]
        if lang not in current:
            current[lang] = game_loc(args.game_dir, lang)
        base = subprocess.run(["git", "show", f"vanilla:{path}"], capture_output=True)
        base_keys = parse(base.stdout.decode("utf-8-sig", errors="replace")) if base.returncode == 0 else {}
        with open(path, encoding="utf-8-sig") as fh:
            mod = parse(fh.read())

        new, changed, dropped = [], [], 0
        for k, (v, line) in mod.items():
            in_base, in_cur = k in base_keys, k in current[lang]
            if not in_base and not in_cur:
                new.append(line)
            elif (in_base and base_keys[k][0] == v) or (in_cur and current[lang][k] == v):
                dropped += 1
            else:
                changed.append(line)
        print(f"{path}: new={len(new)} changed={len(changed)} identical_dropped={dropped}")
        replace_lines.setdefault(lang, []).extend(changed)
        if args.dry_run:
            continue
        if new:
            target = os.path.join(os.path.dirname(path), "NHMMAP_" + os.path.basename(path))
            if os.path.exists(target):
                raise SystemExit(f"refusing to overwrite {target}")
            with open(target, "w", encoding="utf-8-sig", newline="\n") as fh:
                fh.write(f"l_{lang}:\n # NHMMAP-only keys extracted from vanilla override {path}\n")
                fh.write("\n".join(new) + "\n")
        os.remove(path)

    if args.dry_run:
        return
    for lang, lines in replace_lines.items():
        if not lines:
            continue
        target = f"localisation/{lang}/replace/NHMMAP_replace_l_{lang}.yml"
        os.makedirs(os.path.dirname(target), exist_ok=True)
        existing = ""
        if os.path.exists(target):
            with open(target, encoding="utf-8-sig") as fh:
                existing = fh.read()
        with open(target, "w", encoding="utf-8-sig", newline="\n") as fh:
            if not existing:
                fh.write(f"l_{lang}:\n # Vanilla keys whose text NHMMAP changes\n")
            else:
                fh.write(existing.rstrip("\n") + "\n")
            fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
