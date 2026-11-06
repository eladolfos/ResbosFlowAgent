# Cluster etiquette

## Rule
1. Prepare, show, then submit. Preparing a campaign (no `--submit`) is free; submitting consumes allocation and queue slots.
2. Do not poll. No `watch squeue`, no loops of SSH calls, no sleeping scripts. Repeated connections can get an account banned by the cluster's security tools.
   Check once when asked, or when a job's expected finish time has passed.
3. Respect queue limits. The author's cluster allows 1000 queued tasks per user and array tasks count, so large campaigns are submitted one dataset at a time.
   Ask the user for the limits of their site and write them in `local/env.md`.
4. Use the walltime and partition of the user's site, not the author's: set `[scheduler]` in the `.ini` (skill `adapt-scheduler`); without it the driver uses the author's partition (`docs/LIMITATIONS.md`).

## Enforced by
In remote mode: `scripts/remote.py` (rate limit, queue interval, allow list, no connection of its own) and `.claude/settings.json` (denies direct `ssh`/`scp`/`rsync`/`sbatch`). Otherwise nothing automatic.

## If an SSH connection is needed
Use remote mode (`docs/REMOTE.md`): the user opens one persistent connection (ControlMaster) and `scripts/remote.py` reuses it, never opening a connection of its own, with a rate limit (default 20 calls/minute) and
one `queue` check per 5 minutes. Do not call `ssh`, `scp`, `rsync` or `sbatch` yourself (the project settings deny them). If the connection is closed, ask the user to open it and stop; do not retry in a loop.
