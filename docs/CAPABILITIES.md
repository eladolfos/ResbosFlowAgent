# What it can compute

Everything below goes through `run_process.py` (`mode = collider` or `mode = fixedtarget`). If a request is not in this list, the assistant says so; it does not improvise a calculation.
Statuses refer to the authors' own runs; on a new installation nothing is verified until the preflight job and a test campaign have passed (`docs/LIMITATIONS.md`).

## Orders and pieces

| Name | What it is | Where |
|---|---|---|
| `LO` | Born cross section, evaluated at qT = 0 and not integrated (Legacy `LTO=-1`) | fixed target |
| `NLO` | Fixed order O(alpha_s). Collider: the slicing `LTO=1` + `LTO=2` + `LTO=3` pieces, events in `<name>_NLO.root`. Fixed target: Legacy `LTO=3` and `LTO=1` integrated in qT | collider, fixed target |
| `resNLO` | The CSS resummed spectrum matched to fixed order at large qT ("W321", NNLL resummation matched to NLO). Collider: the `resNLO` pieces and `<name>_resNLO.root`. Fixed target: ResBos2 `GetFixed` | collider, fixed target |
| `NNLO` | Only with real `R_Ai` tables supplied by the user (`[get_yk_new] r_ai_<tag>`). `Z0` and `A0` at NNLO are not wired | collider, on request |
| K-factors | NLO/LO and W321/LO per point, from the fixed-target final table | fixed target |

Not available: W432 and the fixed-xF refinement (y(qT) < y0) are not automated; nothing beyond the orders above.

## Collider: W, Z and photon production (Drell-Yan type) in pp and ppbar

| Item | Supported |
|---|---|
| Processes (`processes`) | `W+`, `W-`, `Z0` (pure Z), `A0` (photon), `ZU` and `ZD` (Z/gamma* split into u-type and d-type quarks; Z/gamma* = ZU + ZD) |
| Beams | pp (`ibeam = 1`) and ppbar (`ibeam = -1`) |
| Energies with ready-made templates | pp 5.02, 7, 8 and 13 TeV; ppbar 1.8 and 1.96 TeV. Another energy: change `ecm` and the Q cap (Q must stay <= ECM) |
| PDFs | any LHAPDF set that is installed |
| Grids | rectangular (Q, qT, y), selected with `[grids] active`; custom grids from a data table with `[grids] generate` |
| Events | Monte Carlo (VEGAS) `.root` ntuples from `resbos` with decay leptons, cuts and spin correlations, one run per `[cuts.<name>]` |
| Chain per boson | `w_pert`, `w_asym`, Legacy (several `LTO`), `get_yk_new`, `resbos`; sharded along Q |
| Resummed W grid | Legacy by default; from ResBos2 with `[campaign] w_grid = resbos2` (needed for events at qT >= 2Q) |

Known issues that affect the numbers: `Z0` cross sections come out a flat factor ~2 too large (W is fine; not fixed); the Legacy CSS grid is zero for qT >= 2Q.

## Fixed-target Drell-Yan: E605, E866, E906 (SeaQuest)

One job per measured point; LO, NLO and resNLO at every point, then a final table with K-factors.

| `dataset` | Experiment | Collision | Observable |
|---|---|---|---|
| `e605` | E605 (E201) | p + Cu, 800 GeV (38.8 GeV per nucleon) | Q^3 d2sigma/(dQ dy), 119 (y, Q) points |
| `e866ppxf` | E866 pp (E204) | p + p, 800 GeV | Q^3 d2sigma/(dQ dx_F), 184 (x_F, Q) points |
| `e866f` | E866 pd/pp (E203) | p + p and p + d, 800 GeV | ratio sigma_pd / 2 sigma_pp |
| `e906aF` | SeaQuest (E206) | p + p and p + d, 120 GeV | ratio sigma_pd / 2 sigma_pp |

The qT integral is done inside the calculation; (y or x_F) and Q are taken at the central value of each point. Details and the physics: `docs/FIXED_TARGET_WORKFLOW.md`.

## What you must have installed for each

| You want | You need |
|---|---|
| Collider NLO and/or resNLO grids and events | the five Legacy-family executables (`w_pert`, `w_asym`, Legacy `main`, `get_yk_new`, `resbos_root`), LHAPDF, HOPPET, ROOT, SLURM |
| Collider with the ResBos2 W grid | the above, plus ResBos2 |
| Fixed-target LO, NLO, resNLO | a Legacy `main` built without the `Type_V = 'A0'` normalisation override, ResBos2 `GetFixed` and its environment script, LHAPDF, HOPPET, ROOT, python3 with numpy |

## Status of the recipes

`recipes/collider-wpwmz0-legacy-chain.md` and `recipes/fixedtarget-dy.md`: `partial` (reproduced by the authors on their installation). `recipes/smoke-test-collider.md`: `unvalidated` (never run).
A new energy, process combination or PDF is a new recipe, `unvalidated` until it reproduces a reference (`rules/unvalidated_recipes.md`).
