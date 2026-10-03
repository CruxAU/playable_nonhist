# NHMMAP modding notes

## How vanilla updates work

The `vanilla` branch holds pristine copies of every vanilla file NHMMAP overrides, one commit per game version (tagged `vanilla-<version>`). master has merged it, so git knows which lines are ours and which are Paradox's.

To update to a new game version:

```sh
tools/import_vanilla.sh "d:/Steam/steamapps/common/Hearts of Iron IV" <new_version>
git checkout -b update-<new_version> master
git merge vanilla          # resolve only the real conflicts
```

- **Conflict:** Paradox and NHMMAP changed the same lines. Keep both intents.
- **modify/delete conflict:** Paradox deleted or renamed a file we override. Move our edits to wherever the content went.
- After merging, run `tools/override_report.sh`. Delete any override that shows `0 0`, since it no longer changes anything.

## Rules

1. **Before you start overriding a new vanilla file**, commit it unchanged first, then run `import_vanilla.sh` for the *current* game version. Only then make your edits. Otherwise git has no base for that file and treats the whole file as ours.
   - Simplest way: copy the vanilla file in, commit, run `tools/import_vanilla.sh <game_dir> <current_version>-<n>` (any unused tag name), `git merge vanilla`, then edit.
2. **New objects go in NHMMAP-owned files**, not in vanilla copies: new events, decisions, ideas, game rules, AI plans, scripted triggers/effects, loc keys. Vanilla copies should only contain edits to existing vanilla objects.
   - Changed vanilla loc keys go in `localisation/english/replace/`.
   - Decisions can re-open an existing vanilla category in another file.
   - on_actions are additive: every file's `on_startup` runs, and `nonhist_*`/`formable_*` run after vanilla's `00_`–`16_`.
   - **Startup order matters for the balance system.** Per-country random blocks that use `game_weight_can_add_*` / `set_add_*_weight_*` (the warlords, the extra SPR blocks, all vanilla-modified countries) must stay in `00_on_actions.txt`, in roll order. Blocks that only set their own country's flags from game rules can go in `nonhist_playable_on_actions.txt` (the minors and AFA are there now).
   - **Exception: game rules stay in `00_game_rules.txt`.** The rules screen lists rules in load order within each group, so a country's NHMMAP rules (e.g. `FRA_ai_rhineland`) stay next to its vanilla rule.
   - Tools: `tools/extract_objects.py` (script objects) and `tools/extract_loc.py` (loc overrides) do the moving. Check with `tools/object_inventory.py compare git:HEAD . --layer git:vanilla`: only MOVED entries should appear.
3. **A vanilla object you edit must stay whole in the vanilla copy.** Even one added option, such as an extra `RULE_OPTION` in `FRA_ai_behavior`, means the whole rule stays in `00_game_rules.txt`. HoI4 can't append to an object from another file, and a second definition is a duplicate.
4. **Mark edits inside vanilla copies with `#NHMMAP`.** For blocks, use `#NHMMAP begin` / `#NHMMAP end`, so merge conflicts are easy to read.

## Tools

| Script | Purpose |
|---|---|
| `tools/import_vanilla.sh <game_dir> <version>` | Snapshot vanilla copies of all overridden files onto `vanilla` |
| `tools/override_report.sh` | Show how far each override diverges from vanilla |
| `tools/object_inventory.py` | Object-level dump/compare of any two versions (git refs or folders) |
| `tools/extract_objects.py`, `tools/extract_loc.py` | Move NHMMAP-only objects / loc keys out of vanilla copies |
| `tools/dup_scan.py <game_dir>` | IDs defined twice in vanilla + NHMMAP (e.g. a new vanilla file clashing with ours) |
| `tools/removed_refs.py <old_game_dir> <new_game_dir>` | NHMMAP references to things the update removed |
| `tools/rule_option_check.py <game_dir>` | `has_game_rule` checks against rules/options that don't exist |
| `tools/errorlog_summary.py [--baseline vanilla.log]` | Group error.log, NHMMAP-related first |

## Update checklist

1. `tools/import_vanilla.sh <game_dir> <version>`, then `git checkout -b update-<version>` and `git merge vanilla` (use `-c merge.conflictStyle=zdiff3` to see the base).
2. Resolve conflicts. If both sides made the same change, take vanilla. If NHMMAP rewrote the logic, keep NHMMAP and port vanilla's additions.
3. `tools/dup_scan.py`: watch for content vanilla added that we already had (it gets merged twice), and new vanilla files clashing with ours.
4. `tools/removed_refs.py` and `tools/rule_option_check.py`: compare against the previous version's output; only new entries are update breakage.
5. Check new on_actions files and DLC-reworked countries (new trees need NHMMAP plans guarded with `NOT = { has_dlc = ... }`).
6. Launch with `-debug`; `tools/errorlog_summary.py --baseline <vanilla error.log>`.
