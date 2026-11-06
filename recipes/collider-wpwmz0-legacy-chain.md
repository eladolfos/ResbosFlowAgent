---
name: collider-wpwmz0-legacy-chain
status: partial
mode: collider
owner: ResbosFlow authors
created: 2026-11-06
---

# Collider W+, W-, Z0 with the Legacy chain

## Purpose
Resummed (CSS, W321) and fixed-order (NLO) predictions on a (Q, qT, y) grid for W+, W-, Z0 in pp or ppbar, and optionally Monte Carlo events (`.root` ntuples) from `resbos_root`.

## Inputs
- Process: `W+, W-, Z0` (also `A0`, `ZU`, `ZD`; Z/gamma* = ZU + ZD).
- Beams and energy: pp at 5.02, 7, 8, 13 TeV; ppbar at 1.8, 1.96 TeV (`[legacy] ibeam = 1` for pp, `-1` for ppbar).
- PDF set: any LHAPDF set installed (the authors used CT25NLO).
- Order and pieces: `order = NLO`; `compute = resNLO, NLO`.
- Grids: `templates/7TeV_WpWm` (5.02/7/8 TeV), `templates/13TeV_WpWm` (wider y), `templates/Tevatron_WpWm`. `[grids] active` selects index ranges; Q must stay <= ECM.
- Campaign `.ini`: `examples/pp_13TeV_WpWmZ0_CT25NLO.ini` (Legacy W grid); `examples/pp_13TeV_Zgamma_CT25NLO_ResBos2W.ini` (W grid from ResBos2, for resummed events).

## Requirements
The five Legacy-family executables (`w_pert`, `w_asym`, Legacy `main`, `get_yk_new`, `resbos_root`), LHAPDF, HOPPET and (for `resbos`) ROOT; SLURM and an environment-modules setup (`docs/LIMITATIONS.md`).
The ResBos2 W-grid route also needs ResBos2.

## Commands
```bash
cp examples/pp_13TeV_WpWmZ0_CT25NLO.ini local/        # edit dest, [executables], [environment]
python3 run_process.py local/pp_13TeV_WpWmZ0_CT25NLO.ini
python3 scripts/campaign_review.py show local/pp_13TeV_WpWmZ0_CT25NLO.ini      # review paths and scripts, then authorize (skill review-and-authorize)
python3 scripts/campaign_review.py submit local/pp_13TeV_WpWmZ0_CT25NLO.ini    # only after the approval is recorded
python3 scripts/validate_campaign.py <dest>
```

## Expected outputs
Per boson: merged `.out` grids for `w_pert`, `w_asym`, `legacy` (LTO 3: three rows per point; others one) and `get_yk_new`; per `resbos` run a `.root` ntuple and a log containing `TOTAL CROSS SECTION`.
Chain details: `docs/COLLIDER_WORKFLOW.md`.

## Validation
- Reference: the authors' production campaigns on their cluster (E253 Q 35-82 GeV and a ResBos2-W set, October 2026) and their analysis tables.
- Compared on: the authors' installation only. Not yet run from this repository on any other installation.
- What would validate it on a new installation: a small campaign (one boson, one energy, short Q range) compared against the authors' outputs with identical PDF, grids and inputs, stating HOPPET and LHAPDF versions.

## Known issues
- Legacy CSS grid is exactly zero for qT >= 2Q; use the ResBos2 W grid for resummed events (`docs/COLLIDER_RESBOS2_W_WORKFLOW.md`).
- Z0 cross sections are a flat factor ~2 too large at every energy (W is fine); not fixed, do not divide silently.
- `NNLO` needs real `R_Ai` tables. `Z0` and `A0` at NNLO are not wired.
- The `LTO=1` and `LTO=2` output shapes were read from source, not verified on a real output.
- Details and the rest: `docs/LIMITATIONS.md`.

## History
2026-11-06: created from the ResbosFlow repository (commit 0f6e46c).
