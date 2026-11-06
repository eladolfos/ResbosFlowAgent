---
name: <short-kebab-case-name>
status: unvalidated          # validated | partial | unvalidated  (rules/unvalidated_recipes.md)
mode: collider               # collider | fixedtarget
owner: <who maintains it>
created: <YYYY-MM-DD>
---

# <Title>

## Purpose
One or two sentences: what is computed and why.

## Inputs
- Process / dataset:
- Beams and energy:
- PDF set (and the LHAPDF install it comes from):
- Order and pieces (`order`, `compute`):
- Grids / table (`[grids] active`, table file):
- Cuts (if events):
- Campaign `.ini`: `<path>`

## Requirements
Executables and libraries it needs (from `local/env.md`): which codes, which versions matter, ROOT/numpy needed for the final job.

## Commands
```bash
python3 run_process.py <path-to-ini>             # prepare
python3 scripts/campaign_review.py show <path-to-ini>      # review paths and scripts, then authorize (skill review-and-authorize)
python3 scripts/campaign_review.py submit <path-to-ini>    # only after the approval is recorded
python3 scripts/validate_campaign.py <dest>      # collider, after the run
```

## Expected outputs
Files, their shapes (rows, header lines), and where they land.

## Validation
- Reference: <file, publication or cross-check>
- Tolerance:
- Compared on: <date>, software versions: <ResBos build, LHAPDF, HOPPET, ROOT>
- Result: <numbers>
- What would validate it, if still open:

## Known issues
Anything that is wrong or unverified, with numbers.

## History
Date, who, what changed.
