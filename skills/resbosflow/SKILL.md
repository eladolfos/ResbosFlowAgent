---
name: resbosflow
description: Onboarding of ResbosFlowAgent - greet the user, offer to review their software and paths, set up the environment and scheduler, run a preflight job and then a small test campaign. Use at the start of a session started by the ResbosFlowAI launcher, when local/env.md does not exist, when the user types /resbosflow, or when they ask to get started, check the installation or run a test.
---

# resbosflow

Goal: take a user who has just downloaded this repository to a state where (1) their software and paths have been reviewed and written down, (2) a preflight job has passed on a compute node, and
(3) optionally a small test campaign has run. The user decides at every step; nothing is submitted without their explicit yes.

Read first: `AGENTS.md`, `rules/approval_before_submit.md`, `rules/cluster_etiquette.md`, `docs/LIMITATIONS.md`. Use the user's language.

## Step 0 - greet and ask

Read `docs/CAPABILITIES.md` first; the menu below must match it. Say, briefly:
- what this does: reviews their ResBos installation and paths, checks that jobs can start with their scheduler settings, then (if they want) runs a small test;
- **what it can compute** (show this menu, adapting the wording to their language, keeping the names in English):

  | | |
  |---|---|
  | Orders | `NLO` (fixed order), `resNLO` (CSS resummed, W321, matched to NLO), `LO` (fixed target); `NNLO` only if they provide `R_Ai` tables |
  | Collider (Drell-Yan type) | W+, W-, Z0, photon (A0), Z/gamma* (ZU + ZD); pp at 5.02, 7, 8, 13 TeV and ppbar at 1.8, 1.96 TeV (other energies on request); any installed LHAPDF set; (Q, qT, y) grids and Monte Carlo events (`.root`) |
  | Fixed-target Drell-Yan | E605 (p+Cu), E866 (pp and pd/pp), E906/SeaQuest (pd/pp): LO, NLO, resNLO per measured point and K-factors |
  | Not available | W432, the fixed-xF refinement, anything else (for example Higgs): say so, do not improvise |

  Mention the two caveats that matter to numbers: Z0 comes out ~2x too large (known, not fixed), and results are `unvalidated` until they reproduce a reference on the user's installation;
- what it will not do: build or install anything, or submit anything without their yes;
- one question: **"Do you want me to review your software and paths now?"** Offer to skip to a specific task if they already have an environment profile (`local/env.md`).

If `local/env.md` already exists, show its date and ask whether to re-review or use it.

## Step 1 - where do the jobs run, and how do we reach it

Do not ask for an SSH alias or any SSH detail yet. First find out the situation:

1. If `local/remote.conf` exists: remote mode is already chosen; `python3 scripts/remote.py status`. If the connection is closed, ask the user to open it (`ssh -fN <alias>` in their terminal, or rerun `ResbosFlowAI`) and stop until they say it is open.
2. Otherwise check `command -v sbatch`. If it exists, this assistant is running on a machine with the scheduler (for example the cluster itself): say so, confirm with the user, and use **local mode** (every command is run as written).
3. If `sbatch` does not exist, ask one question: do their jobs run (a) on a cluster they reach over SSH from this computer, (b) on this computer, or (c) they have no cluster yet and only want to look around?
   - (a): run the `setup-ssh` skill. It inspects what the computer already has, tests it with consent, and offers to configure only what is missing. It ends by writing `local/remote.conf`.
   - (b): local mode.
   - (c): explain what the tool needs (`docs/CAPABILITIES.md`) and stop after step 0, or continue with documentation only.
4. In remote mode, if the toolchain on the cluster is missing or different: `python3 scripts/remote.py sync`.

## Step 2 - what they have

Ask, one message, all at once:
0. What do they want to compute (collider or fixed target, which processes or dataset, which orders)? It decides which executables are needed (the table "What you must have installed" in `docs/CAPABILITIES.md`), so check only those.
1. Which ResBos codes do they have and where (folder of the five Legacy-family executables; ResBos2 `GetFixed` and its env script if they want fixed target)?
2. LHAPDF/HOPPET/ROOT prefixes if they are not on the default `PATH`, and the PDF set they want.
3. Where to write results (a scratch folder with room; see `docs/CAMPAIGNS.md` for sizes). **The user chooses `dest`.**
4. A batch script that works on their cluster, if they have one (`adapt-scheduler`), plus the partition's maximum walltime and the queue limit.

## Step 3 - review the software and paths

Run the `discover-environment` skill with their paths as `--check` arguments (one `collect_env.sh` call). Then:
- If they gave a batch script: run `adapt-scheduler`.
- Write `local/env.md` (facts only; "not verified" list).
- Write the first campaign `.ini` into `local/` from `examples/smoke_collider_Wp_13TeV.ini` (collider) or `examples/FT_e605_CT25NLO.ini` (fixed target) with their `dest`, `[executables]`, `[environment]`, `[scheduler]`, PDF. In remote mode `push` it.
- Show the result as a short table: what is found, what is missing, what is not verified. Do not hide failures. Stop here if something blocks them (no SLURM, no executables, PDF missing) and say what to fix.

## Step 4 - preflight job

1. `python3 scripts/preflight.py prepare local/<name>.ini`. It prints the script. Explain: it uses the same header and environment as the real jobs, runs no ResBos code, takes seconds, and checks executables,
   shared libraries, LHAPDF + the PDF set, ROOT, numpy (fixed target) and write access to the folder for `dest`.
2. Ask: "Submit this preflight job?" On an explicit yes: `python3 scripts/preflight.py submit local/<name>.ini --yes-i-reviewed`.
3. Ask the user to tell you when it has finished (at most one `remote.py queue` if they ask you to look). Then `python3 scripts/preflight.py result local/<name>.ini`.
4. Read the result to them. On FAIL, explain each FAIL line and what changes in the `.ini` or `local/env.md` would fix it; fix, `prepare` again, and ask again before resubmitting. Do not proceed to step 5 on a FAIL.
5. On PASS, add the date and job id to `local/env.md`.

## Step 5 - small test campaign (optional, ask)

Ask whether they want a small real campaign to test the whole chain. Explain honestly: `recipes/smoke-test-collider.md` is `unvalidated`; the authors have not run it, so its wall time is unknown and it may need adjusting.
If yes: continue with `new-collider-campaign` (the `.ini` from step 3 already is the smoke test), then `review-and-authorize` (which tells them how many jobs and cores it will use and lets them choose fewer), and after the jobs finish `validate-and-diagnose`. For fixed target use `recipes/fixedtarget-dy.md`.

## Step 6 - close

Summarize in five lines: what was reviewed, what passed, what was not verified, where the files are (`local/env.md`, the `.ini`, `dest`), and what to say next (for example "prepare W+ and W- at 8 TeV with my PDF").
If the test campaign ran and was compared against something, offer to update the recipe's validation section (`rules/unvalidated_recipes.md`).

## Do not
- Do not submit anything (preflight included) without an explicit yes in this conversation.
- Do not choose paths, partitions or accounts for the user.
- Do not poll. Ask the user whether jobs have finished.
- Do not mark anything verified that was not checked by a command whose output you showed.
