# Unvalidated recipes are not results

## Rule
Every recipe carries a `status` in its header: `validated`, `partial` or `unvalidated`. A recipe written by the assistant, or by a user without a reference to compare
against, is `unvalidated` until it reproduces something known.

## What counts as validation
- Agreement with a reference output (a file, a published number, or the `data/regression` style files of the original project) within a stated tolerance, same PDF, same inputs.
- Or a documented independent cross-check (for example resNLO against nloasy + nlodsi, which `validate_campaign.py` checks).

## For the assistant
- When creating a recipe (skill `add-recipe`), set `status: unvalidated` and fill "Validation" with what would validate it.
- When reporting numbers from an unvalidated recipe, say so in the same sentence.
- When a validation succeeds, record the reference, the tolerance and the date, and the software versions; then change the status.
- Never change `status` to `validated` on your own judgment that the numbers "look right".

## Enforced by
Nothing automatic.
