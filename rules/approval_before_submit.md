# Approval before submit

## Rule
A campaign is submitted only after the user has seen where it reads and writes, has seen the `.ini` and what the generated scripts will send, and has explicitly authorized that
campaign. Submission goes through `scripts/campaign_review.py submit`, which checks the recorded authorization.

## Why
Submitting consumes the user's allocation and queue slots, writes into their scratch space and is hard to undo once jobs have started. The `.ini` of a colleague, or an example, may still carry the
original author's paths, partition and library locations. The user must be the one who confirms them.

## What counts as authorization
- An explicit yes, after the review summary, to a question that names the campaign and the destination folder; or the user running `scripts/campaign_review.py approve ... --yes-i-reviewed` themselves.
- It is recorded in `local/approvals/<ini name>.json` with the sha256 of the `.ini` and of the prepared scripts in `dest/`.
- It is void when either changes, and it covers one submission of one campaign.

## For the assistant
- Do not call `run_process.py --submit`, `bash dest/submit_all.sh` or `sbatch` directly. Use `campaign_review.py submit`.
- Do not treat general permissions ("do whatever is needed", "go ahead with the plan") or silence as authorization.
- If `submit` refuses, tell the user why and go back to the review; do not look for another way in.

## Enforced by
`scripts/campaign_review.py submit` refuses without a matching approval and refuses a second submission. It cannot stop a person or an assistant who runs `sbatch` by hand: it guards against accidents and drift, not against bypass.
