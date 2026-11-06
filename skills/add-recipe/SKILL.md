---
name: add-recipe
description: Create or modify a recipe (a concrete calculation setup) or a rule, in the user's local folder or the shared one. Use when the user wants a new set of rules, a new way of computing something, a variation of an existing campaign (new energy, process, PDF, grid, cuts) or to record what they learned.
---

# add-recipe

Goal: capture a calculation so it can be repeated: what to run, with which inputs, how to check it, and how far it has been validated.

Read first: `recipes/README.md`, `recipes/_TEMPLATE.md`, `rules/unvalidated_recipes.md`, `rules/determinism.md`.

## Where it goes
- Personal to the user: `local/recipes/<name>.md` (git-ignored; survives `git pull`).
- Meant to be shared: `recipes/<name>.md`, for a pull request. Ask the user which.

## Steps

1. **Ask what is different** from the closest existing recipe (`recipes/*.md`): energy, process, PDF, order, grid, cuts, dataset, or a different method.
2. **Decide whether it needs only inputs or also a change in the toolchain.**
   - Inputs only (different `.ini` values, template, grid): the recipe records the `.ini`, and the campaign skills do the rest.
   - New dataset, new boson, new step: this changes `run_process.py`, `scripts/` or `templates/`. Say so, list the files, and ask before editing; shared-toolchain edits affect every recipe.
3. **Copy `recipes/_TEMPLATE.md`** and fill every section from facts you have seen (the `.ini`, the command outputs). Leave a section as `TODO` rather than inventing it.
4. **Store the `.ini`** next to the recipe (`local/<name>.ini`, or `examples/<name>.ini` if shared). Check that it prepares without error: `python3 run_process.py <ini>` with a scratch `dest`.
5. **Set `status: unvalidated`** and write in "Validation" what would validate it (a reference file, a published number, an internal cross-check), with the tolerance.
6. **If the recipe implies a new invariant** (something that silently breaks results if violated), add a rule under `rules/` using the structure of the existing ones, and add it to `rules/README.md`.
   If a script can enforce it, say which script and whether it already does.
7. **Tell the user** what was created, its status, and the exact command to prepare the campaign.

## Adding a rule only
Use the rule structure: Rule / Why / Enforced by / If violated. Be explicit about who enforces it; a rule enforced by nobody should say so.

## Do not
- Do not mark a recipe `validated` without a reference comparison that you or the user actually ran.
- Do not copy numbers from memory into a recipe. Quote the file they came from.
