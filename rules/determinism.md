# Determinism

## Rule
Anything that produces a number, a grid, a merged file or a pass/fail verdict comes from `run_process.py` or `scripts/`. The assistant selects, parameterises,
runs and explains; it does not calculate, merge, reformat or "fix up" outputs itself.

## Why
The same campaign must give the same files whoever runs it. A model re-deriving the merge or the grid each time introduces small, silent differences that cannot be
traced afterwards.

## Allowed
- Writing or editing a campaign `.ini` in `local/`.
- Writing the environment profile `local/env.md`.
- Running any script in `scripts/` and the driver, and reading their output and logs.
- Writing new recipes and rules (`local/`, `recipes/`, `rules/`).

## Not allowed without the user asking explicitly
- Editing generated `.in` files by hand (they are rewritten by the driver; re-run it with `--reuse` instead).
- Editing files inside `templates/`, `run_process.py` or `scripts/` to make one campaign work. If the shared toolchain needs a change, say what and why, make it as a
  separate change, and tell the user it affects every campaign.
- Post-processing outputs (rescaling, dropping rows, "correcting" a factor) to make a comparison look right. If a result looks wrong, report it and find the cause.
  The repository documents one known case: `docs/LIMITATIONS.md`, "Z0 normalisation".

## Enforced by
Nothing automatic. This is a behaviour rule.
