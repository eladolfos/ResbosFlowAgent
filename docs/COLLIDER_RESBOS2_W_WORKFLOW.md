# Collider workflow with the ResBos2 W grid

How to compute the resummed (W321 = `resNLO`) collider events with the **main (W) grid from ResBos2** and everything else from the Legacy chain of
`COLLIDER_WORKFLOW.md`; why it is needed, how to run and validate it, what was obtained for E253 and what is not covered. It is Yao's collider recipe
(his `Overall/samplefile/run.sh` has `isResBos2=1 isLegacy=0`), reproduced here.

What is marked how:

* **Verified** — run on the HPCC on 2026-10-13/14 (ZU and ZD, pp 8 TeV, CT25NLO, 40 < Q < 200 GeV).
* *(inferred)* — read in the code or in Yao's scripts, not run.
* **Not covered** — see section 7.

## 1. Why: the Legacy W grid is zero for qT ≥ 2Q

(How `resbos_root` reads the grids and matches W, Y and Pert — the step where this matters — is in `RESBOS_ROOT.md`, sections 5 and 5.4.)

`codes/legacy/res.for` (~line 2102, comment "CBY, May,2019") has

```fortran
      if(QT_V .ge. 2.0*Q_V) then
        fresum=0.0
        return
      endif
```

so the CSS grid (`legacy` with `LTO=0`, `<name>_legacy_<tag>_main.out`, the "Main data grid" of `resbos`) is exactly zero for qT ≥ ~2Q at every Q and y (checked in the
grids of the E253 Q 35–82 GeV campaign, ZU). The same line is in every copy of Legacy found (including Yao's `pku_resbos/SourceCode/legacy_final_version/res.for`), so it does not come from the
uncommitted edits mentioned in `CLAUDE.md`. Beyond 2Q the Y piece (Pert − Singular, with Singular < 0 there) is still added, but the W that should cancel the subtraction is missing, so
Y is inflated: at Q = 50 GeV, qT = 100 GeV it is 2.7 times Pert. The visible effect is W321/NLO that grows too much at pT_ll ≳ 2Q (E253, 46 < M < 66 GeV: K = 3.2 in 105–150 GeV and 7.7 in
150–900 GeV, against 1.21 and 2.41 for Yao). Rapidity observables hardly notice it (E246, E250: K changes by < 1 %). The W of ResBos2 does not have the cut; it continues smoothly (≈ the
asymptotic piece) and the NLO and W321 then agree with Yao. *(Inferred: this is why Yao takes the W from ResBos2.)*

## 2. Which code makes each piece

| Piece | Code | File |
|---|---|---|
| W (CSS, A,B,C = 3,2,1) | **ResBos2** `resbos`, `XSec = Resummation` | `Grids/ResBos_GridFile_0.out` (columns Q, Qt, y, Resum0, Resum1) → "Main data grid" |
| Perturbative O(αs²), asymptotic | `w_pert`, `w_asym` | unchanged |
| Y piece | `legacy` `LTO=3` | unchanged |
| Y + K-factors | `get_yk_new` (`order = NLO`, all-ones `R_Ai`) | `Yk_<tag>_NLO.out` → "Y piece grid", unchanged |
| Events | `resbos` (`resbos_root`) | `<job>.root`, `h10` tree |
| NLO | `resbos` with the `dsi` + `asy` grids, summed | unchanged; the NLO never used the CSS grid |

The `legacy` `LTO=0` stage (the CSS grid) is not needed for the resNLO any more; the `LTO=3` stage is. Yao's scripts kept are the W432 setting (A,B,C = 4,3,2, `get_yk_new` `NNLO` with real `R_Ai`, `WConfig=2`);
W321 is the same chain with 3,2,1 and `order = NLO` *(inferred from the naming; no W321 script of his was kept)*.

## 3. Requirements

* A finished Legacy campaign from `run_process.py` for the same boson, energy and PDF (e.g. `Examples/pp_8TeV_ZUZD_CT25NLO.ini`): its `legacy/inp/q_grid.inp`, the header of
  `legacy/<name>_legacy_<tag>_main.out`, `get_yk_new/<name>_Yk_<tag>_NLO.out`, `resbos/<name>_<tag>_<run>.in` and `resbos/resbos_root`.
* ResBos2 built by `setup.sb` (`ONLY=resbos2`): `bin/resbos2/bin/resbos`; environment `source bin/resbos2/env_getfixed.sh` (GCC/13.2.0 + OpenSSL/1.1, ROOT, LHAPDF, BAT,
  HOPPET1). The same PDF set (CT25NLO) in both LHAPDF installs. HOPPET: this repository runs ResBos2 and Legacy on 1.3.0-devel (`LOG.md` 1f/1g), as in the runs below.
* The grids below were made with a copy of ResBos2 patched only in `Total`/`YPiece`/`WmA` (section 8); the patch does not touch `Resummation.cc`, so the stock binary should give the
  same W *(not rerun with it)*.

## 4. Procedure

### 4.1 Q nodes
Use the nodes of the campaign's `legacy/inp/q_grid.inp` that cover the mass range of the events (`QMn`, `QMx` of the `resbos` `.in`) **plus two nodes of margin on each side** (the
interpolation is 4th order). For 40 < Q < 200 GeV: 30, 35, 40, 50, 60, 65, 70, 82, 85, 87, 89, 90, 91.1882, 92, 93, 95, 97, 100, 110, 130, 160, 200, 250, 300.

### 4.2 ResBos2 W grids (one task per boson and Q)

Parameters that must be the ones of the Legacy header (lines 4–13 of `legacy_<tag>_main.out`: `INONPERT`, `C1/B0 C2 C3/B0`, `KinCorr`, `iscale`, `bmax g1 g2 g3 Q0`):

| `resbos.config` key | Value | Legacy header |
|---|---|---|
| `XSec`, `Process` | `Resummation`, `ZU` / `ZD` | `TYPE_V` |
| `AOrder BOrder COrder HOrder` | 3 2 1 2 | W321 |
| `NonPert`, `bMax`, `Q0`, `g` | `BLNY`, 0.5, 1.6, `0.21, 0.68, -0.126` | `INONPERT=5`, `bmax,g1,g2,g3,Q0in` |
| `C1 C2 C3` | 1 1 1 | `C1/B0 C2 C3/B0` (ResBos2 multiplies C1 and C3 by B0) |
| `KinematicCorrection`, `scale` | `true`, `MT` | `KinCorr=1`, `iscale=1` |
| `PertOrder AsymOrder DeltaSigmaOrder` | 1 1 2 | as Yao's W321 `fixedtarget.config` |
| `PDF`, `iSet`, `ECM`, `beam` | `CT25NLO`, 0, 8000, `pp` | |
| `qMin = qMax` | the Q node of the task | one Q per task, as Yao |
| `qtMin`, `qtMax` | 0, **1500** | see 6 (600 loses the events above ~543 GeV) |
| `yMin`, `yMax` | −6, 6 | |
| `itmax1/2`, `ncall1/2` | 1, 200 | only the grid is used, not the integral |
| `nThreads` | 4 | |

The other keys (EW inputs, quark masses, cuts open) are those of Yao's `Overall/ResBos2/00resbos.config`. Every task needs its own `Grids/` and `ConvGrids/` in the working directory.
Array of 2 bosons × 24 nodes, 4 CPU / 8 GB, ~6 min per task:

```bash
#SBATCH --array=0-47 --cpus-per-task=4 --mem=8G --time=02:00:00
source bin/resbos2/env_getfixed.sh
QS=(30 35 40 50 60 65 70 82 85 87 89 90 91.1882 92 93 95 97 100 110 130 160 200 250 300)
i=$SLURM_ARRAY_TASK_ID; B=$([ $i -lt 24 ] && echo ZU || echo ZD); Q=${QS[$((i%24))]}
d=$B/Q$Q; mkdir -p $d/Grids $d/ConvGrids; cp base_w.config $d/resbos.config
sed -i "s/^Process = .*/Process = $B/; s/^qMin = .*/qMin = $Q/; s/^qMax = .*/qMax = $Q/; s/^nThreads = .*/nThreads = 4/" $d/resbos.config
cd $d && resbos -i resbos.config -o out
```

Each grid has 15 header lines and `nQT × nY` rows, `nQT = int(10·ln(qtMax/0.1) + 3)`, `nY = 121`: 99 × 121 = 11 979 rows for `qtMax = 1500`.

### 4.3 Validate before going on
Ratio ResBos2 / Legacy of `L0` and `A3` at the same (Q, y, qT), by log-interpolation in qT. Found: **1.00 ± 0.02 for 5 GeV < qT < 2Q**, 0.84–0.94 below 2 GeV, 1.03–1.06 at 5 GeV, no global factor
(Q = 35, 50, 82 GeV; y = 0, 2, −3; ZU and ZD). A global factor ≠ 1 means a parameter of 4.2 differs from the Legacy header. Above 2Q Legacy is 0 and ResBos2 continues: that is the point.

### 4.4 Build the main grid for `resbos_root`
Rules read in `resbos_root.f` (`iHeadLen`, `PreReadIn`, `ReadIn`): 15 header lines, the last one starting with **two spaces and `Q,qT,y`**; data columns `Q qT y L0 A3` (the number of columns
is detected, Legacy also has `ASY L0, ASY A3`, unused); a full rectangular grid, Q slowest, then y, qT fastest (at most 200 qT, 300 y, 100 Q). So: the Legacy header, then the ResBos2 rows
(without their header) in increasing Q.

```python
hdr = open('legacy/<name>_legacy_ZU_main.out').readlines()[:15]
assert hdr[14].startswith('  Q,qT,y')
hdr[14] = '  Q,qT,y, CSS L0, CSS A3  (ResBos2 Resummation grid, W321, reheadered with the Legacy header)\n'
with open('Resbos_grids/<name>_r2W_ZU_main.out', 'w') as out:
    out.writelines(hdr)
    for q in QS:                                           # increasing Q
        rows = open(f'ZU/Q{q}/Grids/ResBos_GridFile_0.out').readlines()[15:]
        assert len(rows) == 99 * 121 and abs(float(rows[0].split()[0]) - float(q)) < 1e-4
        out.writelines(rows)
```

### 4.5 Events
Same `.in` as the campaign's resNLO run with only the "Main data grid" line changed to the new file (the Y grid line keeps `Yk_<tag>_NLO.out`); one serial job per boson
(`srun ./resbos_root <job>`, 1 CPU, 8 GB, modules `GCC/13.2.0 OpenMPI/4.1.6-GCC-13.2.0 powertools` + ROOT, LHAPDF, HOPPET1), ~6 min for 30 M events (`1,30,30000,300,100000`). Run each boson in its own
directory (`Matched.out` and the other scratch files are written in the working directory). Chain the steps with `--dependency=afterok:… --kill-on-invalid-dep=yes`.

### 4.6 Analysis
The ROOT files are 1–2 GB; analyse on the HPCC (`root -b -q` macro with `module load GCC/13.2.0 OpenSSL/1.1`; PyROOT and `uproot` are not available there) and copy only the tables. In Python
use float64 for the weights (see 6).

## 5. Results (E253, ATLAS 8 TeV Z/γ*, ZU + ZD, pT_l > 20 GeV, |η_l| < 2.4, |y_ll| < 2.4; K = W321/NLO)

| Window (GeV) | pT_ll (GeV) | Legacy W | ResBos2 W | Yao |
|---|---|---|---|---|
| 46–66 | 45–105 / 105–150 / 150–900 | 1.23 / **3.16** / **7.74** | 1.21 / 1.17 / 2.43 | 1.22 / 1.21 / 2.41 |
| 66–116 | 150–300 / 300–550 / 550–900 | 1.04 / 1.12 / 1.20 | 1.01 / 1.04 / 1.12 | 1.00 / 1.02 / 1.08 |
| 116–150 | 45–105 / 105–150 / 150–900 | 1.42 / 1.13 / 0.98 | 1.42 / 1.11 / 1.00 | 1.41 / 0.97 / 1.06 |

With the ResBos2 W the K-factors are within 1–3 % of Yao's in the three windows (bin-level differences of 3–6 % are within the statistics, except 66–116 above 550 GeV where ours is +3–6 %, with the NLO
~3 % lower relative to W321; not investigated). Cross sections are 4–8 % below Yao's (NLO ours/Yao 0.925, 0.963, 0.940 and W321 0.919, 0.967, 0.952 in the three windows; attributed to the PDF set, CT25NLO against his;
not rerun with his). E246 (Z, y_B) and E250 (Z, y_B; W±, asymmetry) change by ≤ 0.2 % and ≤ 0.8 % in K. Full numbers and the CSVs: analysis project, `LOG.md` section 30 and `R2W_test/`.

## 6. Pitfalls found

1. `qtMax` too small: with 600 GeV `resbos_root` loses the events above the second-to-last node (542.9 GeV); the 66–116 bins 550–650 and 650–900 GeV came out 1.6e-4 and 0 pb instead of 2.4e-3 and 1.2e-3. Use `qtMax` ≥ 1500 for pT_ll up to 900 GeV.
2. `Grids/` and `ConvGrids/` missing in the ResBos2 working directory (`Unable to open file: …_Conv_C1.out`).
3. Fewer than 4 Q nodes in a ResBos2 grid (`Polint: Error in interpolation routine`).
4. `root` without `OpenSSL/1.1` fails within seconds.
5. A header whose last line does not start with `  Q,qT,y` is not found by `resbos_root`.
6. Parameters different from the Legacy header (4.2); Yao's collider config (`IY6`, `C3 = 4`, `bMax = 1.123`) is a different setting and was not used.
7. **float32 histograms:** the ROOT branches are float32 and `np.histogram` with non-uniform bins accumulates in the weights' dtype, so sparse bins next to populated ones lose most digits (a 6.65e-4 pb tail bin came out as
   6.1e-5 pb, errors exactly 0). Cast to float64 first. (Fixed in the analysis project's `kf_tools/resbos.py`; tables extracted before are inaccurate in sparse bins.)

## 7. Scope and what is not covered

* **Verified against Legacy / the manual recipe:** ZU, pp 8 TeV, CT25NLO (E253 windows; one-process test of the whole driver chain, `docs/CT25_COLLIDER_CAMPAIGNS_REPORT.md` 4.1). ResBos2 nodes also run at every Q of the full grid (report 4.10).
* **Run but never compared with Legacy grids:** W⁺, W⁻, Z/γ* at 5.02, 7 and 13 TeV, p pbar 1.8 and 1.96 TeV (the ten campaigns of 2026-10-14; all validations passed with warnings, report 4.6). W432 was not run.
* The recipe is in the driver (`[campaign] w_grid = resbos2`, `docs/CAMPAIGNS.md`): array of ResBos2 runs, assembly under the header of Legacy's own Y-piece grid, dependencies, analysis file names. With `w_grid = legacy` (the default) the chain is unchanged; both are valid modes.
* **What the grid depends on:** the non-perturbative function and the b* settings. Our grid uses BLNY (g = 0.21, 0.68, −0.126, bMax 0.5, C1 = C2 = C3 = 1); Yao's ResBos2 config uses IY6, C3 = 4, bMax 1.123. At Q = 91.19 GeV, y = 0 the qT integral of L0 differs by 5.7 % (report 4.12). `[resbos2_w] settings = template` runs a config as it is.
* The generator of the events is `resbos_root`: its inputs (widths, EW flags) change the W/Z cross sections by percent (Γ_W: 0.83 %, report 4.4); the ResBos2 grid does not depend on them.
* PDF and HOPPET of Yao's collider histograms are uncertain (his `overall.sh` points to CT18NNLO, his folders are named `_BLNY`, the user remembers `pp830a016`); the 4–8 % cross-section offset is not quantified.

## 8. Do not use ResBos2 alone for the collider

`XSec = Total` and `YPiece` are not built (`# Total.cc`, `# YPiece.cc` are commented out in `codes/resbos2/src/Calculation/CMakeLists.txt`; `XSec=Total` gives "Invalid calculation mode"). A patched copy compiles
them (signatures, vector-size mapping in `GetCalc`, the crossing tolerance, the uninitialised central `scale` of `WmA`/`Total`/`YPiece`), but `Total` gives 54 pb against 35 pb of Legacy for ZU, 46 < Q < 66 GeV, `WmA` gives 0.5 pb
(incoherent with `Total`), and the histogram saving is commented out in `main.cc` ("yfu"). Use ResBos2 only for the W grid. The patch is `scripts/collider_resbos2_w/resbos2_Total_YPiece_fixes.patch` (applies to `codes/resbos2`, not applied here); the tests are in the analysis project (`LOG.md` 30.1).

## 9. Where the material is

`scripts/collider_resbos2_w/` (this repository): the scripts that produced the results above, kept as run, with a `README.md` (order, inputs/outputs, what to adapt).

Analysis project `/home/elser/Documents/KFactor_Raw_simulations`: `RESBOS2_W_WORKFLOW.md` (the same recipe, in Spanish, with the table-extraction side: `Simulations/ResbosR2W/`, the `RESBOS_FOLDERS` field of
the `.yml`), `LOG.md` sections 30.1–30.11, `R2W_test/` (CSVs, raw outputs, scripts for the W grids, assembly, validation and analysis). HPCC: W grids `/mnt/scratch/lopezels/Resbos2_W_for_legacy_full2/`,
events `/mnt/scratch/lopezels/KFactorsCT25resNLO/DY_R2W2/`, Legacy campaign `/mnt/scratch/lopezels/KFactorsCT25resNLO/ZUZD_8TeV_CT25NLO_resNLO_NLO/`.
