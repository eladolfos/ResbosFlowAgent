---
name: new-collider-campaign
description: Prepare a collider (W/Z/gamma* in pp or ppbar) resummed-qT campaign with the Legacy-family chain (w_pert, w_asym, Legacy, get_yk_new, resbos) from the user's request, using their environment profile. Use when the user wants W+, W-, Z0, A0 or ZU/ZD at a collision energy, a PDF set, a Q/qT/y grid or event generation.
---

# new-collider-campaign

Goal: a prepared `dest/` and `dest/submit_all.sh` for one collider campaign, with the resolved inputs reviewed by the user. Submitting is a separate step.

Read first: `local/env.md` (if missing, run `discover-environment`), `rules/grid_lockstep.md`, `rules/q_le_ecm.md`, `rules/naming_and_paths.md`, `rules/determinism.md`,
`docs/COLLIDER_WORKFLOW.md`, section "New energy, process or dataset" of `docs/CAMPAIGNS.md`, and `recipes/collider-wpwmz0-legacy-chain.md`.

Remote mode (`local/remote.conf` exists): edit the `.ini` on the laptop, `python3 scripts/remote.py push`, and run every cluster command as `python3 scripts/remote.py run -- <command>` (table in `AGENTS.md`, setup in `docs/REMOTE.md`). Paths are cluster paths.

## Steps

1. **Pin the request**: process(es) (`W+`, `W-`, `Z0`, `A0`, `ZU`, `ZD`), beams (pp: `[legacy] ibeam = 1`; ppbar: `-1`), ECM in GeV, PDF set (must be installed; `rules/pdf_name_trap.md`),
   order (`NLO`; `NNLO` needs real `R_Ai` tables), what to compute (`resNLO`, `NLO`), Q/qT/y range, and whether events (`resbos`, `.root`) are wanted with which cuts.
2. **Choose the starting point.** The closest file in `examples/` and the template folder it names:
   `templates/7TeV_WpWm` (also used for 5.02 and 8 TeV), `13TeV_WpWm` (wider y grid), `Tevatron_WpWm` (ppbar).
   For resummed events, use the ResBos2 W grid (`[campaign] w_grid = resbos2`; `examples/pp_13TeV_Zgamma_CT25NLO_ResBos2W.ini`) because the Legacy CSS grid is exactly zero for qT >= 2Q
   (`docs/COLLIDER_RESBOS2_W_WORKFLOW.md`). That route needs ResBos2; say so if the profile has none.
3. **Write `local/<name>.ini`** (copy the example, edit):
   - `[paths] dest` to a new folder on the user's scratch space, `source` to the template folder (`../templates/...`), `scripts = ../scripts`.
   - `[campaign] name` short, `ecm`, `processes`, `pdf`, `order`, `compute`.
   - `[executables]` from `local/env.md` (`dir` or one key per code).
   - `[environment]` (`modules`, `lhapdf`, `hoppet`, `root_setup`) from `local/env.md`.
   - `[grids] active`: indices into `inp/*_grid.inp`. Q must stay <= ECM: list the grid with `cat templates/<t>/legacy/inp/q_grid.inp` and pick the Q index. For a lower energy, lower Q max.
   - `[shards]`: number of Q shards for `legacy`, `w_pert`, `w_asym`. `resbos` is never sharded (VEGAS). Check the user's queue limits first (`rules/cluster_etiquette.md`).
   - `[resbos]` and `[cuts.<name>]` for events.
4. **Prepare** (no submit): `python3 run_process.py local/<name>.ini`. Read the resolved inputs it prints to the user: executables, `.in` templates, grids, shard counts, Q range.
5. **Review and authorize**: run the `review-and-authorize` skill (path map, `.ini`, partition/account/walltimes, and the RESOURCES section: how many jobs, tasks and cores, how they chain; ask whether the user wants fewer, e.g. fewer `[shards]`, one boson or `compute = resNLO`). If the scheduler or modules differ from the
   author's, run `adapt-scheduler` first.
6. **Submit only after approval**: `python3 scripts/campaign_review.py submit local/<name>.ini`. Jobs are chained with `--dependency=afterok`. Never `--submit` or `sbatch` directly.
7. **Record**: note the campaign in `local/` (name, `dest`, date, job ids if the user gives them). Do not poll.
8. When the user says the campaign finished, run `validate-and-diagnose`.

## Adding a campaign for a new energy or process
Copy the nearest example, change `name`, `ecm`, `dest` and the Q cap. Several energies from one `.ini`: replace `[campaign] name/ecm` with an `[energies]` section
(`<label> = <ecm_GeV>, <file_prefix>` per line). Mark the result as an `unvalidated` recipe if it has no reference (`rules/unvalidated_recipes.md`).

## Do not
- Do not edit generated `.in` files; change the `.ini` and use `--reuse`.
- Do not hand-edit `templates/`.
- Do not submit before the approval of step 5 is recorded.
