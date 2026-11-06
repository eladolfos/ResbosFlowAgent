---
name: validate-and-diagnose
description: Check a finished or failed campaign - run validate_campaign.py, read logs, explain the cause of a failure and say what to do. Use when the user says a campaign finished, a job failed, outputs look wrong, or asks whether results are trustworthy.
---

# validate-and-diagnose

Goal: an honest verdict on a campaign (what passed, what failed, what was not checked) and the smallest next action.

Read first: the "Common failures" table in `docs/CAMPAIGNS.md`, `rules/legacy_output_by_lto.md`, `rules/provenance.md`, `rules/unvalidated_recipes.md`.

Remote mode (`local/remote.conf` exists): edit the `.ini` on the laptop, `python3 scripts/remote.py push`, and run every cluster command as `python3 scripts/remote.py run -- <command>` (table in `AGENTS.md`, setup in `docs/REMOTE.md`). Paths are cluster paths.

## Collider

1. `python3 scripts/validate_campaign.py <dest>` (in remote mode through `remote.py run --`; writes `dest/validation_summary.txt`; exit status 1 if any ERROR). It checks:
   each `resbos` log has a finite `TOTAL CROSS SECTION`, reached exit code 0 and has no NaN; each piece produced a `.root` of plausible size (stubs ~60 KB, real ~1 GB);
   merged grids contain no NaN/Inf; and, when present, resNLO agrees with nloasy + nlodsi within `--cross-tol`.
2. Read the output to the user as three lists: OK, WARN, ERROR. Quote ERROR lines verbatim.
3. For each ERROR, open the named log or grid (remote mode: `remote.py run -- tail -n 200 <log>` or `head`, or `remote.py pull <file>` for small files; never `.root`) and find the first real error line (not the last line of the job). Typical causes:
   - Abort in `PERTURB`: a Q point above ECM (`rules/q_le_ecm.md`).
   - `get_yk_new` triplet mismatch: grids differ between codes (`rules/grid_lockstep.md`).
   - Missing library or module: the job environment differs from `local/env.md`; compare with `dest/provenance_runtime.log`.
   - Walltime hit on a shard: more shards for that code (`[shards]`), then `--reuse`.
   - Tiny `.root` (stub): the `resbos` job did not generate events.
4. Resubmitting only the event runs of a finished campaign: `python3 run_process.py local/<ini> --resbos-only` (prepare only), then `review-and-authorize`; the changed scripts need a new approval.

## Fixed target

1. Count rows: LO 1 per point; LTO=1 one per qT; LTO=3 three per qT; `GetFixed` output is judged by its row count, not by its exit code.
2. Look at `results/` for the final table. Compare with a reference if available and report differences with the tolerance used.
3. Known: with HOPPET 1.3.0-devel the ResBos2 W321 differs from a HOPPET 1.2.0 build by 0.13 % rms (max 0.8 %). Report the user's HOPPET version when comparing.

## Always
- Say what was **not** checked. For instance `validate_campaign.py` does not compare to a physics reference.
- If a number looks off, do not "correct" it. Known open issue: Z0 cross sections from the chain are a flat factor ~2 too large at every energy (W is fine); see `docs/LIMITATIONS.md`.
- If results are good and a reference exists, offer to update the recipe's `status` and validation section (`rules/unvalidated_recipes.md`).
- Do not poll for job completion; ask the user whether the jobs have finished.
