---
name: fixedtarget-dy
status: partial
mode: fixedtarget
owner: ResbosFlow authors
created: 2026-11-06
---

# Fixed-target Drell-Yan: LO, NLO and resNLO (W321) at measured points

## Purpose
Theory predictions at every measured (y, Q) point of E605, E866 (pp/xF, f ratio) or E906 (SeaQuest), and a final table with LO, NLO, W321 and K-factors.

## Inputs
- Dataset: `e605`, `e866ppxf`, `e866f`, `e906aF` (ECM, beam, neutron fraction and Jacobian are in `FT_DATASETS` in `run_process.py`; tables in `templates/FixTargetTables/`).
- PDF set: any LHAPDF set (the authors used CT25NLO).
- `compute = LO, NLO, resNLO`.
- Campaign `.ini`: `examples/FT_e605_CT25NLO.ini`.

## Requirements
Legacy `main` built without the `Type_V = 'A0'` normalisation override, ResBos2 `GetFixed` with its environment script, ROOT, and python3 with numpy for the final job; SLURM and modules (`docs/LIMITATIONS.md`).

## Commands
```bash
cp examples/FT_e605_CT25NLO.ini local/        # edit dest, [executables], [fixedtarget]
python3 run_process.py local/FT_e605_CT25NLO.ini
python3 scripts/campaign_review.py show local/FT_e605_CT25NLO.ini      # review paths and scripts, then authorize (skill review-and-authorize)
python3 scripts/campaign_review.py submit local/FT_e605_CT25NLO.ini    # only after the approval is recorded
```

## Expected outputs
Legacy tasks per table row (`LTO` -1, 3, 1), merged files with the row counts in `rules/legacy_output_by_lto.md`, the `GetFixed` table per target,
and `results/<name>_LO_NLO_W321.txt`. Workflow: `docs/FIXED_TARGET_WORKFLOW.md`.

## Validation
- Reference: the authors' fixed-target tables (reproduced on their installation on 2026-10-21 with `legacy_ft` and the `getnlo` macro) and Yao's files.
- With HOPPET 1.2.0 and Yao's PDF and binaries, LO and W321 were bit-identical to his files and NLO agreed within about 0.1 %. With HOPPET 1.3.0-devel, ResBos2 W321 differs from his by 0.13 % rms (max 0.8 %).
- Compared on: the authors' installation only. Not yet run from this repository elsewhere.

## Known issues
- Fixed-xF refinement (y(qT) < y0) and W432 are not automated.
- `GetFixed` exit code is 1 on success; the driver judges by row count.
- Only tested with fakes in the first version of the driver; run a new installation carefully, one dataset first.

## History
2026-11-06: created from the ResbosFlow repository (commit 0f6e46c).
