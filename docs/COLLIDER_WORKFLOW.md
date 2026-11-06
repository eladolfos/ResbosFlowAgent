# Collider workflow

How a collider campaign (W+, W-, Z0, A0, ZU/ZD in pp or ppbar) goes from one `.ini` to the `.root` event files: which code runs at each step, what it
reads and writes, and how `run_process.py` chains them. The fixed-target chain is a different one (`FIXED_TARGET_WORKFLOW.md`); how to launch campaigns, the
list of examples and the failure table are in `CAMPAIGNS.md`.

Status: the preparation of the collider examples works (`run_process.py` writes `dest` and `submit_all.sh`). One collider campaign has run from this repository
(E253, ZU + ZD, 8 TeV, Q = 35–82 GeV, 2026-10-13; a variant of `Examples/pp_8TeV_ZUZD_CT25NLO.ini` with `[grids] active` Q index 4–10, whose `.ini` is not committed here); the large 8 TeV campaigns used the older driver of
`ResbosLegacy_v.2026.1`. The Legacy `LTO=1` and `LTO=2` output shapes (15 header lines, 1 line per point) were read off `main.for`, not checked on a real output.

> **Warning (2026-10-14):** the CSS grid of `legacy` (`LTO=0`, the "Main data grid" of `resbos`) is exactly zero for qT ≥ 2Q (`res.for`, `if(QT_V .ge. 2.0*Q_V) fresum=0`), which
> inflates W321/NLO at pT_ll ≳ 2Q (E253 46–66 GeV: K = 7.7 against 2.4 for Yao at 150–900 GeV). For the resummed events use a W grid computed with ResBos2 in that slot:
> `COLLIDER_RESBOS2_W_WORKFLOW.md`.

## 1. The five codes

All of them live in `codes/` (copies of `ResbosLegacy_v.2026.1`), are built by `setup.sb` (`ONLY=resbos_legacy`) into `bin/<code>/<exe>`, and use the Legacy toolchain
(GCC 13.2 + gfortran + the user's LHAPDF, HOPPET 1.3.0-devel and, for `resbos`, ROOT).

| Step | Code (`codes/`) | Executable | Language | What it computes | Reads | Writes |
|---|---|---|---|---|---|---|
| 1 | `w_pert` | `w_pert` | Fortran 77 | Fixed-order perturbative `dσ/dy/dqT²` (Arnold–Reno) at first and second order in αs, in pb/GeV² (the `L0` and `A3` pieces `get_yk_new` reads). PDFs through `lhapdf.cpp` | `w_pert.in` + `inp/{q,qt,y}_grid.inp` | one row per (Q,qT,y): `Q qT y` + perturbative columns (3 header lines) |
| 2 | `w_asym` | `w_asym` | Fortran 77 | The same cross section expanded at small qT (asymptotic, CSS/Arnold–Kauffman, to O(αs²)): the `L0` and `A3` pieces for beam 1 and for the sum of both beams | `w_asym.in` + the same grids | one row per point (3 header lines) |
| 3 | `legacy` | `main` | Fortran 77 + `lhapdf.cpp` | CSS resummed cross section (resummed piece + Y piece + non-perturbative Sudakov), selected by `LTO` in the `.in`: `0` full CSS grid, `3` Y piece (3 rows per point), `1` ΔΣ, `2` asymptotic | `legacy.in` + the same grids | 15 header lines, then 1 row per point (`LTO=3`: 3) |
| 4 | `get_yk_new` | `get_yk_new` | Fortran 77 | Builds the Y/`ykR` grid that `resbos` uses for the high-qT region from the Legacy Y piece (`LTO=3`): at `order = NLO` it copies Singular and Pert from the Y piece and turns the angular columns into ratios `r_i`; `w_pert.out` and `w_asym.out` are read only to check the grids match (their values are used at `NNLO`). Knows `W+ W- ZU ZD A0` | `w_pert.out w_asym.out legacy_Y.out R_Ai.txt` + job name, boson, order, PDF | `Yk` grid: 3 rows per point (the 17-header, `iYGrid=2` format) |
| 5 | `resbos` | `resbos_root` | Fortran 77 + C/C++ (`froot.c`, `angular.cc`) | Monte Carlo (VEGAS) event generator with decay leptons, cuts and spin correlations; samples the Legacy/Yk grids | `resbos.in` + "Main data grid" + "Y piece grid" | `<job>.root` ntuple, log with `TOTAL CROSS SECTION` |

The five codes share no executable code: `EvlPac02b/PrzPac02b/QcdPac02b/UtlPac02b/EwkPac02b.for`, `CT14Pdf.f` and `lhapdf.cpp` are separate, almost byte-identical copies in
`legacy`, `w_pert` and `w_asym` (see `CLAUDE.md`, "Duplicated sources"). They only talk through **text grid files** on the same (Q, qT, y) mesh.

## 2. How they combine

Per boson (W+ and W- share nothing; each `processes` entry is a full chain):

```
                  inp/{q,qt,y}_grid.inp   (identical for w_pert, w_asym, legacy; md5-checked)
                          |
   +----------------------+-----------------------------+
   v                      v                             v
w_pert  -> .out      w_asym  -> .out           legacy LTO=3 (Y piece) -> .out
   \                      |                             /
    +---------------------+----------+-----------------+
                                     v
                                get_yk_new  (+ R_Ai table; all ones at NLO)
                                     v
                                 Yk grid (3 rows/point)
                                     |
   legacy LTO=0 (CSS main grid) -----+--->  resbos_root  ->  <name>_<tag>_<run>_resNLO.root

   legacy LTO=2 (asymptotic) + legacy LTO=3 (Y piece) ---->  resbos_root (nloasy)  --\
                                                                                        hadd -> <name>_<tag>_<run>_NLO.root
   legacy LTO=1 (ΔΣ), no Y piece ("-") ------------------->  resbos_root (nlodsi)  --/
```

`[campaign] compute` chooses what is built. `legacy_Y` (`LTO=3`) is shared, so it runs once even with `compute = resNLO, NLO`.

### 2.1 resNLO: the resummed, matched cross section

* `legacy` `LTO=0` gives the CSS-resummed `dσ/dQ dy dqT` (the *Main data grid* of `resbos`).
* `legacy` `LTO=3` gives the Y piece (fixed order minus the asymptotic expansion) in the form `get_yk_new` needs.
* `get_yk_new` takes the Legacy Y piece and writes the `Yk` grid (at `order = NLO`: Singular and Pert unchanged, angular columns as ratios `r_i`; at `NNLO`: Singular/Pert replaced by `w_asym`/`w_pert` and real `R_Ai`); `w_pert`/`w_asym` are checked for the same (Q, qT, y) points at NLO. `resbos` reads it as the
  *Y piece grid* with `iYGrid=2`. The result is the resummed spectrum matched to fixed order at large qT ("W321" in Yao's naming).
* `R_Ai` (angular coefficients of the decay, from the FCFM code) is an input of `get_yk_new` only. At `order = NLO` it is unused, so the driver makes an all-ones
  table (`make_dummy_rai.py`, rectangular, from the `w_pert` output). At `order = NNLO` the driver demands a real one (`[get_yk_new] r_ai_<tag>`).
* Output: `<name>_<tag>_<run>_resNLO.root`.

### 2.2 NLO: fixed order by phase-space slicing

`resbos` is run twice and the two ntuples are added with ROOT's `hadd`:

| Run | Main grid | Y grid | Covers |
|---|---|---|---|
| `…_nloasy` | `legacy` `LTO=2` (asymptotic) | `legacy` `LTO=3` (Y piece, raw 10-column format, forced `iYGrid=1`) | qT > qT_Sep (real emission, since asymptotic + Y = fixed order 2→3) |
| `…_nlodsi` | `legacy` `LTO=1` (ΔΣ) | none (`-`) | qT < qT_Sep (singular, regulated 2→2 piece) |

The dependence on the artificial qT_Sep cancels between the two files. Output: `<name>_<tag>_<run>_NLO.root`. `validate_campaign.py` warns when `resNLO` and
`nloasy + nlodsi` cross sections disagree by more than `--cross-tol`.

### 2.3 Why Legacy runs up to four times per boson

The four Legacy passes differ only in the `LTO` field of otherwise identical `.in` files (`LTO_BY_STAGE` in `run_process.py`):

| Stage name | Job file (`legacy/`) | `LTO` | Needed by |
|---|---|---|---|
| `legacy_Y` | `<name>_legacy_<tag>_Y` | 3 | `get_yk_new`, `nloasy` (shared) |
| `legacy_main` | `<name>_legacy_<tag>_main` | 0 | `resbos` resNLO |
| `legacy_dsi` | `<name>_legacy_<tag>_dsi` | 1 | `nlodsi` |
| `legacy_asy` | `<name>_legacy_<tag>_asy` | 2 | `nloasy` |

`legacy_dsi` hard-stops in Legacy unless `IFLAG_C3 = 1`; the driver sets it only if the template's scale choice is numerically the canonical one, else it refuses.

## 3. What `run_process.py` does (collider mode)

1. **Prepare** (`build()`): checks the template has all five code folders, the three grids are md5-identical, the active Q range is below ECM, and the executables exist; then
   copies only what a run needs into `dest/{w_pert,w_asym,legacy,get_yk_new,resbos}` (executables from `[executables] dir`, the `inp/` grids, `make_dummy_rai.py`).
2. **Rewrite the `.in` files** (`patch_stage()`), starting from the template's W+ file: ECM, `iBeam`, `lha_<pdf>`, `JWTYPE`/`Type_V` of the boson (Z0, A0, ZU, ZD use `JWTYPE=2`, `JZ_TYPE`
   chooses ZU/ZD/general couplings), `LTO` per stage, the active qT/y/Q ranges (found by their `> comment` marker, not line number), `[legacy]` overrides, and for `resbos`
   the VEGAS settings, seed, luminosity, output format and `[cuts.<run>]`.
3. **Shard** `w_pert`, `w_asym` and each Legacy pass **along Q only** (`[shards]`; `make_shards.py`, `run_*_array.sb`, `submit_*_array.sh`): Q is the outermost loop in the codes, so shard outputs
   concatenate back in serial order. `merge_shards.py` merges and checks the row count (3 header lines for `w_pert`/`w_asym`, 15 for Legacy; 1 row per point, 3 for `LTO=3`).
   A merge job runs only if every shard exits 0 (`afterok`).
4. **Chain** the stages in `dest/submit_all.sh` with `--dependency=afterok`:
   `w_pert`, `w_asym`, Legacy passes (parallel arrays) → `get_yk_new` (after `w_pert`, `w_asym`, `legacy_Y`) → `resbos` resNLO (after `get_yk_new`, `legacy_main`);
   `nloasy` after `legacy_asy` and `legacy_Y`, `nlodsi` after `legacy_dsi` → `hadd` after both. Finally `analysis.sb` (validation).
   `resbos` is **never sharded** (VEGAS MC, one serial job per cut set in `[resbos] runs`). `get_yk_new` and `resbos` stage their inputs themselves at job start (`[paths] stage_outputs = link|copy`).
5. **Reuse** (`--reuse`): a stage whose merged output already passes the row-count check is not resubmitted, and downstream dependencies only name jobs actually queued.
   `--resbos-only` rewrites and submits just the resNLO `resbos` runs of a finished campaign (new cut sets).
6. **Record** `campaign.ini`, `PROVENANCE.txt/json`, `timing.log` (per-stage durations) and, after the run, `validation_summary.txt`.

## 4. Files in `dest/`

```
dest/
  w_pert/      <name>_w_pert_<tag>.{in,out}      + _shards/    run/merge scripts
  w_asym/      <name>_w_asym_<tag>.{in,out}      + _shards/
  legacy/      <name>_legacy_<tag>_{Y,main,dsi,asy}.{in,out}  + _shards/
  get_yk_new/  <name>_Yk_<tag>_<order>.out       <name>_dummy_R_Ai_<tag>.txt
  resbos/      <name>_<tag>_<run>_{resNLO,nloasy,nlodsi}.in   Resbos_grids/   resbos_output_*.log   run_*.sb
  <name>_<tag>_<run>_resNLO.root   <name>_<tag>_<run>_{nloasy,nlodsi}.root   <name>_<tag>_<run>_NLO.root
  submit_all.sh  analysis.sb  timing.log  validation_summary.txt  campaign.ini  PROVENANCE.*
```

`tag` is `Wp`, `Wm`, `Z0`, `A0`, `ZU` or `ZD`; `run` is a `[resbos] runs` name (`nocuts` in the production set).

## 5. Constraints to keep in mind

* **Grid lockstep.** `w_pert`, `w_asym` and Legacy must run on identical (Q, qT, y) grids; `get_yk_new` aborts if a triplet differs by more than 1e-8, and `resbos` checks the row
  count (`NQ×Ny×NqT` must equal the rows, so the grid must be a full rectangle).
* **Q ≤ ECM.** `PERTURB` aborts the whole shard otherwise; choose `[grids] active` accordingly.
* **Job names** under ~95 characters (Fortran `character*100`).
* **Z0** at `order = NLO` works end to end, but the cross sections from the chain are a flat factor ~2 too large (open issue; W is fine).
* **Resources** (reference, ATLAS 8 TeV W±, 80×153×143 grid): `w_pert` ~3 h, Legacy ~16 h serial per full grid (hence 20 shards), `get_yk_new` 12 h / 16 G requested,
  `resbos` ~4 min per 25 M events (12 h / 8 G requested).

## 6. Where to look in the code

| Topic | Place |
|---|---|
| Stage table, `LTO` per stage, boson tags | `STAGES`, `LTO_BY_STAGE`, `PROCS` at the top of `run_process.py` |
| `.in` rewriting | `patch_stage()`, `write_resbos_run()` |
| Job scripts | `yk_script()`, `resbos_script()`, `hadd_script()`, shard scripts in `scripts/` |
| Dependency chain | `build()` (the `sub` list that becomes `submit_all.sh`) |
| Post-run checks | `scripts/validate_campaign.py`, `analysis.sb` |
| Per-code details | `codes/<code>/README.md`, `codes/{w_pert,get_yk_new,resbos}/CLAUDE.md` |
| Older long-form description (previous driver) | `RESBOS_LEGACY_README.md`, sections 3.1–3.3 |
