#!/usr/bin/env bash
# Snapshot pristine vanilla copies of every file NHMMAP overrides onto the
# `vanilla` branch, so game updates can be applied with `git merge vanilla`.
#
# Usage: tools/import_vanilla.sh <vanilla_game_dir> <version>
#   e.g. tools/import_vanilla.sh "d:/Steam/steamapps/common/Hearts of Iron IV" 1.19.3
#
# - The override set is taken from master: every master file whose path also
#   exists in <vanilla_game_dir>. Paths master no longer overrides are dropped
#   from `vanilla`, so deleting an override never causes a modify/delete conflict.
# - Each vanilla copy gets the same UTF-8 BOM state as master's copy, so BOM
#   differences don't show up as edits.
# - Commits "vanilla <version>" and tags it vanilla-<version>. Does not merge.
set -euo pipefail

GAME_DIR="${1:?usage: $0 <vanilla_game_dir> <version>}"
VERSION="${2:?usage: $0 <vanilla_game_dir> <version>}"
MOD_BRANCH="${MOD_BRANCH:-master}"
CONTENT_DIRS='^(common|events|localisation|interface|gfx|history|map|music|sound|portraits)/'

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"

[ -d "$GAME_DIR/common" ] || { echo "error: $GAME_DIR does not look like a HoI4 install" >&2; exit 1; }
if git rev-parse -q --verify "refs/tags/vanilla-$VERSION" >/dev/null; then
	echo "error: tag vanilla-$VERSION already exists" >&2; exit 1
fi

WT="$(mktemp -d)"
cleanup() { git worktree remove --force "$WT" >/dev/null 2>&1 || true; rm -rf "$WT"; }
trap cleanup EXIT

if git show-ref -q --verify refs/heads/vanilla; then
	git worktree add -q "$WT" vanilla
else
	git worktree add -q --detach "$WT"
	git -C "$WT" checkout -q --orphan vanilla
fi
git -C "$WT" rm -r -q --cached . >/dev/null 2>&1 || true
find "$WT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +

has_bom() { [ "$(head -c3 "$1" | od -An -tx1 | tr -d ' \n')" = "efbbbf" ]; }

count=0
while IFS= read -r path; do
	src="$GAME_DIR/$path"
	[ -f "$src" ] || continue
	dst="$WT/$path"
	mkdir -p "$(dirname "$dst")"
	mod_copy="$(mktemp)"
	git show "$MOD_BRANCH:$path" > "$mod_copy"
	if has_bom "$mod_copy" && ! has_bom "$src"; then
		{ printf '\xef\xbb\xbf'; cat "$src"; } > "$dst"
	elif ! has_bom "$mod_copy" && has_bom "$src"; then
		tail -c +4 "$src" > "$dst"
	else
		cp "$src" "$dst"
	fi
	rm -f "$mod_copy"
	count=$((count + 1))
done < <(git ls-tree -r --name-only "$MOD_BRANCH" | grep -E "$CONTENT_DIRS")

git show "$MOD_BRANCH:.gitattributes" > "$WT/.gitattributes"
git -C "$WT" add -A
git -C "$WT" commit -q -m "vanilla $VERSION

Pristine vanilla copies of the $count files NHMMAP overrides."
git tag "vanilla-$VERSION" vanilla
echo "vanilla-$VERSION: $count files"
echo "next: git checkout -b update-$VERSION $MOD_BRANCH && git merge vanilla"
