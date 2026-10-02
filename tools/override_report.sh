#!/usr/bin/env bash
# List every vanilla override with how far it diverges from vanilla.
# Usage: tools/override_report.sh [mod_ref=HEAD] [vanilla_ref=vanilla]
# Output columns: added  removed  path   (sorted by total change, biggest first)
# Overrides with 0/0 are pure vanilla copies and can be deleted.
set -euo pipefail
MOD_REF="${1:-HEAD}"
VAN_REF="${2:-vanilla}"
cd "$(git rev-parse --show-toplevel)"

git ls-tree -r --name-only "$VAN_REF" | grep -v '^\.gitattributes$' | while IFS= read -r path; do
	git cat-file -e "$MOD_REF:$path" 2>/dev/null || continue
	stat="$(git diff --numstat --ignore-cr-at-eol "$VAN_REF" "$MOD_REF" -- "$path")"
	if [ -z "$stat" ]; then
		printf '0\t0\t%s\n' "$path"
	else
		printf '%s\n' "$stat"
	fi
done | sort -t$'\t' -k1,1n -k2,2n | awk -F'\t' '{print $1+$2 "\t" $0}' | sort -rn | cut -f2-
