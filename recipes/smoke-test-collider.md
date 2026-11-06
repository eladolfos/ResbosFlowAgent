---
name: smoke-test-collider
status: unvalidated
mode: collider
owner: ResbosFlow authors
created: 2026-11-06
---

# Smoke test: small W+ campaign at 13 TeV

## Purpose
Run the whole collider chain once, small, on a new installation: `w_pert`, `w_asym`, Legacy (`_Y`, `_main`), `get_yk_new` and `resbos`, with the user's scheduler settings and libraries.
It tests that the chain runs and its files have the right shape. It is **not** a physics result.

## Inputs
- Process and energy: W+, pp 13 TeV (`[legacy] ibeam = 1`), `order = NLO`, `compute = resNLO`.
- Grid: template `13TeV_WpWm`, full qT (153) and y (155) grids, Q indices 10-12 (82, 85, 87 GeV): 3 x 153 x 155 = 71,145 points.
- Shards: `legacy = 10` (two passes, `_Y` and `_main`), `w_pert = 2`, `w_asym = 2`. 24 array tasks in total.
- Events: one `resbos` run, `nocuts`, VEGAS `1,5,3000,5,3000` (a few 10^4 events).
- Campaign `.ini`: `examples/smoke_collider_Wp_13TeV.ini`.

## Requirements
The five Legacy-family executables, LHAPDF with the PDF set, HOPPET, ROOT, SLURM. Pass `scripts/preflight.py` first.

## Commands
```bash
cp examples/smoke_collider_Wp_13TeV.ini local/         # set dest, [executables], [environment], [scheduler], pdf
python3 scripts/preflight.py prepare local/smoke_collider_Wp_13TeV.ini   # then submit / result, see skill resbosflow
python3 run_process.py local/smoke_collider_Wp_13TeV.ini
python3 scripts/campaign_review.py show local/smoke_collider_Wp_13TeV.ini --full    # then approve, submit (skill review-and-authorize)
python3 scripts/validate_campaign.py <dest>
```

## Expected outputs
Merged grids for `w_pert`, `w_asym`, `legacy` (`_Y`: three rows per point, `_main`: one) and `get_yk_new`; one `.root` ntuple and a `resbos` log with a finite `TOTAL CROSS SECTION`.
`validate_campaign.py` should report no ERROR.

## Validation
- Reference: none. The authors have not run this exact configuration.
- What validates it: a run on the authors' HPCC with the wall time recorded here, then, on a new installation, `validate_campaign.py` without ERROR and a cross section in the same ballpark as the corresponding Q slice of
  the production W+ 13 TeV campaign, with identical PDF and grids.
- What it does not validate: the physics. A passing smoke test says the chain is wired; it does not say the numbers are right.

## Known issues
- Wall time and disk use unknown (the 12 h and 24 h job walltimes in the generated scripts are the driver's defaults, not measurements).
- With the tiny VEGAS run the cross section has a large statistical error; do not compare it to a reference at the percent level.
- Behaviour of `resbos` on only three Q points of the grid has not been checked; if it fails there, report the log, do not widen the grid silently.
- The general limitations of the toolchain apply: `docs/LIMITATIONS.md` (for example Z0 is not in this test).

## History
2026-11-06: created.
