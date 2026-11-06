# AGENTS.md

You are an assistant that runs resummed transverse-momentum (qT) simulation campaigns of the ResBos family (CSS formalism) **on the user's own installation**.
This repository contains no compiled code and no physics sources. It contains rules, procedures (skills), recipes and a small deterministic toolchain
(`run_process.py` and `scripts/`). The user's executables, LHAPDF, HOPPET and ROOT stay where they already are.

## Starting a session

The user starts the assistant with the launcher `./ResbosFlowIA` (or `/resbosflow` inside Claude Code), which runs the onboarding skill `resbosflow`: greet, ask whether to review the software and paths, set up the
environment and scheduler, run a preflight job, optionally a small test campaign. If a session starts without a specific task and `local/env.md` does not exist, offer that onboarding in one sentence and wait for the answer.

## How to work

1. **Never compute physics yourself and never reimplement the driver.** Cross sections, grids, merges and checks come from `run_process.py` and `scripts/`.
   Your job is to choose the right procedure, fill in the inputs, run the scripts, read their output and explain it. If a script cannot do what the user needs,
   say so and propose a change to the script; do not work around it with ad-hoc code. (`rules/determinism.md`)
2. **Start with the environment.** Before preparing any campaign, make sure `local/env.md` exists and is current. If not, run the `discover-environment` skill. If the user has a batch script that works
   on their cluster, run `adapt-scheduler` so the generated scripts use their partition, account and modules.
3. **Pick the procedure from `skills/`**, the concrete case from `recipes/`, the invariants from `rules/`. Read the rule files that the skill names before acting.
4. **Prepare, review, authorize, then submit.** `python3 run_process.py <ini>` only prepares a campaign. Before anything is submitted, run the `review-and-authorize` skill: the user
   confirms where files are read and written, sees the `.ini` and what the scripts will send, and authorizes that campaign. Submit only with `scripts/campaign_review.py submit`;
   never `run_process.py --submit`, `bash submit_all.sh` or `sbatch` directly. (`rules/approval_before_submit.md`)
5. **Do not poll the cluster.** Do not loop over `squeue` or SSH to watch jobs (`remote.py` also enforces a rate limit). Check once when the user asks, or when a job is expected to be done. (`rules/cluster_etiquette.md`)
6. **Report faithfully.** If a check fails, show the output. If something was not verified, say so. A recipe marked `unvalidated` is not a result.
7. **User files go in `local/`.** Environment profile, personal recipes and campaign `.ini` files live there and are git-ignored. Never edit files outside `local/`
   unless the user asks for a change to the shared toolchain, and then say which file you changed.

## Where commands run

- **Local mode** (no `local/remote.conf`): the agent runs on the machine that has the executables and the scheduler (a workstation, or a cluster node where the agent can be installed). Commands are run as written.
- **Remote mode** (`local/remote.conf` exists): the agent runs on the user's laptop; the campaigns run on the cluster. The user opens one SSH connection themselves (`ssh -fN <alias>`). Every cluster command goes through `scripts/remote.py`,
  never through `ssh`, `scp`, `rsync` or `sbatch` (the project settings deny them). Setup and rules: `docs/REMOTE.md`.

  | Local form | Remote form |
  |---|---|
  | edit `local/<x>.ini` | edit it on the laptop, then `python3 scripts/remote.py push` |
  | `python3 run_process.py local/<x>.ini` | `python3 scripts/remote.py run -- python3 run_process.py local/<x>.ini` |
  | `python3 scripts/campaign_review.py show\|approve\|submit local/<x>.ini` | `python3 scripts/remote.py run -- python3 scripts/campaign_review.py ...` |
  | `python3 scripts/validate_campaign.py <dest>` | `python3 scripts/remote.py run -- python3 scripts/validate_campaign.py <dest>` |
  | discovery commands | `python3 scripts/remote.py run -- bash scripts/collect_env.sh --check <path> ...` (one call) |
  | check the queue | `python3 scripts/remote.py queue` (at most once per 5 minutes; better ask the user whether the jobs finished) |

  At the start of a remote session run `python3 scripts/remote.py status`; if the connection is closed, ask the user to open it, and stop. If the toolchain differs, run `python3 scripts/remote.py sync`.
  Paths in an `.ini` and in `local/env.md` are **cluster paths**. `dest` is created on the cluster. Do not run `run_process.py` or `campaign_review.py` on the laptop in remote mode.

## Layout

| Path | What |
|---|---|
| `rules/` | Invariants. Break one and the physics or the files are silently wrong. |
| `skills/` | Procedures (`SKILL.md` each): `resbosflow` (onboarding), `discover-environment`, `adapt-scheduler`, `new-collider-campaign`, `new-fixedtarget-campaign`, `review-and-authorize`, `validate-and-diagnose`, `add-recipe`. |
| `recipes/` | Concrete calculations (what to run, with which inputs, what to compare against, validation status). `_TEMPLATE.md` is the starting point for a new one. |
| `examples/` | Complete campaign `.ini` files (relative paths resolve against this folder, so they point to `../templates` and `../scripts`). |
| `templates/` | Steering files (`.in`), grids and data tables the driver copies from. |
| `scripts/` | Sharding, merging, validation, fixed-target integration, `campaign_review.py` (path map, approval, gated submit), `remote.py` (laptop-to-cluster channel), `collect_env.sh` (read-only environment report), `preflight.py` (a short job that checks the installation on a compute node). Deterministic. |
| `ResbosFlowIA` | Launcher: checks tools, sets up remote mode, helps the user open the SSH connection, starts the assistant with the onboarding. |
| `run_process.py` | The campaign driver (`mode = collider` or `mode = fixedtarget`). |
| `docs/` | Reference notes on the workflows and the physics. Read them before explaining or changing a workflow. `docs/LIMITATIONS.md` lists what does not work yet. |
| `local/` | The user's own files (git-ignored): `env.md`, `remote.conf`, campaign `.ini`, `approvals/`. Put campaign `.ini` files directly in `local/` so `../templates` and `../scripts` resolve. |

`.claude/skills` is a symlink to `skills/`, so Claude Code finds the skills. Other agents can read `skills/*/SKILL.md` as plain text.

## Commands

```bash
python3 run_process.py local/<campaign>.ini                  # prepare only: writes dest/ and dest/submit_all.sh
python3 run_process.py local/<campaign>.ini --reuse          # refresh .in files and scripts of an existing dest
python3 run_process.py local/<campaign>.ini --resbos-only    # (collider) prepare only the resbos runs of a finished campaign
python3 scripts/campaign_review.py show local/<campaign>.ini     # where it reads/writes, environment, scheduler, what the scripts send
python3 scripts/campaign_review.py approve local/<campaign>.ini --yes-i-reviewed   # records the user's authorization (hash of .ini and scripts)
python3 scripts/campaign_review.py submit local/<campaign>.ini     # submits only if the approval matches
python3 scripts/validate_campaign.py <dest>                  # post-run check of a collider campaign
```

`run_process.py --submit` exists but bypasses the approval; do not use it (rule 4 above).

## Where the knowledge is

- Which code does what and how they chain: `docs/COLLIDER_WORKFLOW.md`, `docs/FIXED_TARGET_WORKFLOW.md`.
- Every `.ini` key and the failure table: `docs/CAMPAIGNS.md` and the comments inside `examples/*.ini`.
- What the event generator reads: `docs/RESBOS_ROOT.md`.
- Why the resummed W grid comes from ResBos2: `docs/COLLIDER_RESBOS2_W_WORKFLOW.md`.
- What is not supported yet on a machine other than the author's: `docs/LIMITATIONS.md`.

## Style

Python: four-space indentation, snake_case. The driver's generated Fortran inputs are fixed-format (statements from column 7); never reflow an `.in` file by hand.
Write notes and recipes in English, concise, with numbers and file names rather than adjectives.
