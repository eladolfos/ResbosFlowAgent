# Recipes

A recipe is one concrete calculation: what to run, with which inputs, how to check it, and how far it has been validated.
Skills are generic procedures; recipes are cases. Start a new one from `_TEMPLATE.md` (or ask the assistant: skill `add-recipe`).

| Recipe | Mode | Status |
|---|---|---|
| `collider-wpwmz0-legacy-chain.md` | collider, W+/W-/Z0 pp and ppbar, Legacy chain | partial (validated by the authors on their installation) |
| `fixedtarget-dy.md` | fixed target, E605/E866/E906 | partial (validated by the authors on their installation) |

Personal recipes go in `local/recipes/` (git-ignored). Recipes meant for everyone go here, through a pull request.

`status` values: `validated` (reproduces a stated reference within a stated tolerance), `partial` (validated somewhere other than your installation, or only some outputs),
`unvalidated` (no reference comparison yet). See `rules/unvalidated_recipes.md`.
