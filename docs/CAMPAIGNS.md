# Running campaigns

A campaign is one `.ini` in `Examples/`. `run_process.py` prepares a new `dest` folder (inputs, job scripts, `submit_all.sh`); `--submit` also runs `submit_all.sh`, which chains the
SLURM jobs with `--dependency=afterok`. Run it on the HPCC login/dev node after the executables are built (`INSTALL.md`).

```bash
python3 run_process.py Examples/pp_8TeV_WpWmZ0_CT25NLO.ini            # prepare dest + dest/submit_all.sh, print the inputs it resolved
python3 run_process.py Examples/pp_8TeV_WpWmZ0_CT25NLO.ini --submit   # ... and submit
python3 run_process.py <ini> --reuse                                   # dest exists: refresh .in files/scripts, skip stages whose output is already valid
python3 run_process.py <ini> --resbos-only --submit                    # collider: only (re)submit the resbos runs of a finished campaign
```

The mode is chosen by `[campaign] mode` (`collider` is the default, `fixedtarget` for E605/E866/E906). It is checked: a `[fixedtarget]` section without `mode = fixedtarget`
is refused, and fixedtarget refuses `[energies]` and `[grids] experimental/generate`.

## The examples

| `.ini` | Process | ECM (GeV) | Template | Q range (`[grids] active`) | Legacy shards |
|---|---|---|---|---|---|
| `pp_5.02TeV_WpWmZ0_CT25NLO.ini` | W+, W−, Z0 | 5020 | `7TeV_WpWm` | index 1–79 (≤ 4900 GeV) | 20 |
| `pp_7TeV_WpWmZ0_CT25NLO.ini` | W+, W−, Z0 | 7000 | `7TeV_WpWm` | 1–80 (≤ 5000 GeV) | 20 |
| `pp_8TeV_WpWmZ0_CT25NLO.ini` | W+, W−, Z0 | 8000 | `7TeV_WpWm` | 1–80 | 20 |
| `pp_13TeV_WpWmZ0_CT25NLO.ini` | W+, W−, Z0 | 13000 | `13TeV_WpWm` (155 y points) | 1–80 | 20 |
| `ppbar_1.8TeV_WpWmZ0_CT25NLO.ini` | W+, W−, Z0 (`iBeam=-1`) | 1800 | `Tevatron_WpWm` | 1–47 (≤ 1700 GeV) | 20 |
| `ppbar_1.96TeV_WpWmZ0_CT25NLO.ini` | W+, W−, Z0 (`iBeam=-1`) | 1960 | `Tevatron_WpWm` | 1–49 (≤ 1900 GeV) | 20 |
| `pp_8TeV_ZUZD_CT25NLO.ini` | Z/γ* = ZU + ZD | 8000 | `7TeV_WpWm` | 1–30 (10–500 GeV), resbos generates 40 < Q < 200 | 15 |
| `<beam>_<E>TeV_{WpWmZ0,Zgamma}_CT25NLO_ResBos2W.ini` (12 files: pp 5.02, 7, 8, 13 TeV; ppbar 1.8, 1.96 TeV) | W+, W−, Z0 / Z/γ* = ZU + ZD | as the Legacy one | as the Legacy one | 1–30 (10–500 GeV), resbos generates 40 < Q < 200 | 15–20 |
| `FT_e605_CT25NLO.ini` | E605 (E201), p+Cu, 119 points | 38.8 | `FixedTarget` | per point | – |
| `FT_e866ppxf_CT25NLO.ini` | E866 pp (E204), 184 points | 38.75 | `FixedTarget` | per point | – |
| `FT_e866f_CT25NLO.ini` | E866 pd/pp (E203), 15 points, pp + pd | 38.76 | `FixedTarget` | per point | – |
| `FT_e906aF_CT25NLO.ini` | SeaQuest (E906), 6 points, pp + pd | 15.07 | `FixedTarget` | per point | – |

The collider ones are the production set behind `KFactor_Raw_simulations/Simulations/ResbosLegacy/*.root` (CT25NLO, no cuts, NLO + resNLO). Z0 is the pure Z resonance;
ZU/ZD also carry γ* and the interference (σ(Z/γ*) = ZU + ZD, add the two ntuples). `Simulations/` also holds 5 TeV files (`pp_5TeV_*`); to regenerate them copy the 5.02 TeV `.ini`
and set `ecm = 5000`.

## Provenance: which software made a campaign

Every prepared campaign gets, next to `campaign.ini` (a copy of the .ini):

* `PROVENANCE.txt` / `PROVENANCE.json` (written by `run_process.py` through `scripts/provenance.py`): ResbosFlow git commit and any uncommitted files, python version, host, user, date; for each executable its
  sha256, build time, compiler, the HOPPET version it was linked with, and the key libraries it resolves in the job environment (LHAPDF and ROOT versions, HOPPET, BAT, libstdc++, libgfortran, with realpath and
  sha256); the PDF set found along the search path with the sha256 of its `.info` and member 0 (a same-named set with another grid is detected); sha256 of the grids, templates, scripts and data tables; the modules.
* `provenance_runtime.log`: one record per job (array tasks: only the first) with node, compiler, loaded modules, `LD_LIBRARY_PATH` and `LHAPDF_DATA_PATH` as the job really ran.

Reproducing a run later means checking out that commit, rebuilding with the same libraries (compare the sha256 of the executables) and running `campaign.ini`. To get the same record for an old campaign:
`python3 scripts/provenance.py --dest <dir> --exe name=<exe>;ld=<libdirs> ...` (see its docstring). When the repository is copied to the HPCC without `.git`, run `scripts/mkrevision.sh` first: it writes `REVISION`
(commit, branch, uncommitted files), which `provenance.py` then reads.

### ResBos2 W grid for the resNLO (`w_grid = resbos2`)

`[campaign] w_grid = legacy` (default) computes the CSS grid of the resNLO with Legacy (`LTO = 0`). With `w_grid = resbos2` that stage is replaced: one ResBos2 run (`XSec = Resummation`) per Q node
of the Legacy Q grid, assembled into the same file format and read by `resbos_root` (why: `docs/COLLIDER_RESBOS2_W_WORKFLOW.md`; what `resbos_root` does with it: `docs/RESBOS_ROOT.md`). Only the resNLO changes, the NLO stays Legacy.
Works for `processes` = `W+`, `W-`, `Z0`, `ZU`, `ZD`, `Zgamma` (= `ZU, ZD`; `A0` has no ResBos2 W process) with `[legacy] ibeam = 1` (pp) or `-1` (ppbar); the CSS scheme and BLNY form (`iNONPERT = 5`) only.

```
w_pert, w_asym, legacy LTO=3 --> get_yk_new --> Yk grid --\
ResBos2 Resummation x Q nodes (SLURM array) --> assemble --+--> resbos (resNLO)
```

Per boson, `dest/resbos2_w/` gets `configs_<tag>/Q<Q>.config` (one per node), `run_*.sb` (the array), `assemble_*.sb` and `q_nodes_<tag>.txt`. The physics settings (orders, `C1..C3`, BLNY `g`, `bMax`, `Q0`, scale, PDF,
quark masses, kinematic correction) are read from the Legacy `legacy_main` template and written into every ResBos2 config, so both generators compute the same thing; the rest (electroweak inputs, widths) comes from
`templates/ResBos2W/resbos_w.config`. The assembly needs the Legacy Y-piece output of the same boson (its header is reused), so it waits for `legacy_Y`.

| `[resbos2_w]` key | Default | Meaning |
|---|---|---|
| `resbos`, `env` | `bin/resbos2/bin/resbos`, `bin/resbos2/env_getfixed.sh` | ResBos2 executable and the environment of its build |
| `config` | `templates/ResBos2W/resbos_w.config` | base configuration |
| `qtmax` | `auto` | largest qT of the ResBos2 grid; `auto` = largest qT of the Legacy grid. **It must not be smaller**: `resbos_root` loses the events above it (seen with 600 GeV) |
| `ymax` | 6 | grid range in y (must cover the Legacy y grid) |
| `margin` | 2 | extra Q nodes on each side of the active Q range (the main grid is interpolated with 4 points and must contain the Y grid's range) |
| `threads`, `time`, `mem`, `partition`, `throttle` | 4, 02:00:00, 8G, general-long, – | SLURM resources of one Q node (`throttle` = `--array=…%N`) |

`[output] convention = analysis` (default, `none` to switch off) also hard-links every final `.root` as `dest/for_analysis/<generator>/{beam}_{ECM}TeV_{PDF}_{PROCESS}_{CUTS}_{ORDER}.root`, the name `KFactor_Raw_simulations/extract_tables.py` reads,
with `<generator>` = `ResbosLegacy` for NLO and for a Legacy resNLO, `ResbosR2W` for a ResBos2-W resNLO: copy the two folders into `Simulations/` (ResBos2-W files in the NLO's folder or
listed with `RESBOS_FOLDERS` in the experiment `.yml`). The campaign's own names are kept.

### `Examples/CT25NLOExpResbos2/`: what the analysis needs

Ten campaigns to regenerate every experiment of `KFactor_Raw_simulations/KineticCuts` (`scripts/make_exp_inis.py` derives them from the `.yml`; CT25NLO, no cuts).
**Collider** (six, one per beam and ECM, NLO + resNLO with the ResBos2 W grid, processes = union of what the experiments read, Z0 served as `Zgamma` = ZU + ZD):
pp 5.02 TeV W±, Z/γ* (E215); pp 7 TeV W±, Z/γ* (E245, E248, E266, E267); pp 8 TeV W±, Z/γ* (E211, E214, E217, E246, E249, E250, E253); pp 13 TeV Z/γ* (E212, E218);
p p̄ 1.8 TeV W± (E225); p p̄ 1.96 TeV W±, Z/γ* (E227, E234, E260, E261, E281). **Fixed target** (four, copies of `FT_*.ini` with the paths of that folder):
E201 `e605`, E203 `e866f`, E204 `e866ppxf`, E206 `e906aF`. The table is in that folder's `README.md`.
The Z experiments at 5.02, 7, 13 and 1.96 TeV still say `Z0` in their `.yml`: set `PROCESS: Zgamma` (and drop the Z0 normalisation divisor), or run `make_exp_inis.py --z0 keep`.

### Yao's inputs (`templates/Yao`, `Examples/CT25NLOExpYao/`)

`[physics] sync = no` makes every template keep its own masses, widths and EW flags (nothing is copied from one file to another), and `[resbos2_w] settings = template`
uses the ResBos2 config as it is (only beam, ECM, process, PDF, set, Q node, qT/y range and threads are set; with the default `derive` the CSS settings are read from the
Legacy `.in` and only BLNY is accepted). `templates/Yao/` holds the inputs of Yao's collider chain (his Legacy `.in` and grids of 33 Q x 106 qT x 100 y, his `resbos_root` input with
W 2.0895 / Z 2.498353 and EW flag 2 2, his ResBos2 W321 config with IY6, C3 = 4, bMax 1.123, y in [-5, 5]); what is his, what was changed and what his files leave open: `templates/Yao/README.md`.
`Examples/CT25NLOExpYao/` are the six collider campaigns with them, VEGAS `1,30,30000,100,250000`, window 40 < Q < 500 GeV.

### Skipping `w_pert` and `w_asym` (`[get_yk_new] skip_pert_asym = yes`)

At `order = NLO`, `get_yk_new` reads the `w_pert` and `w_asym` files only to check that they carry the same (Q, qT, y) points as Legacy's Y piece; their values do not enter the Yk (tested: real, all-ones and random
inputs, and `R_Ai` = 5 instead of 1, all give a byte-identical Yk; `LOG.md` 1i). With `skip_pert_asym = yes` the driver does not run those two stages (no executable, no shards, no `.in`, ~10 array tasks fewer per boson and no
`w_pert` wait of about 3 h): the `get_yk_new` job writes placeholder files with the points of the Legacy Y piece (`run_process.py _wpa_placeholders`) and runs as usual. Needs `order = NLO` (refused otherwise: NNLO uses the values) and a resNLO in
`compute`. Default `no`; it is `yes` in `Examples/CT25NLOExpResbos2/`. The placeholders were checked on the E253 ZU 8 TeV files: Yk byte-identical to the one made with the real `w_pert`/`w_asym`.

### Masses, widths and electroweak inputs (`[physics]`)

**One set of values everywhere.** Every template now carries the same numbers (checked by `tests/test_run_process_r2w.py::test_templates_share_one_set_of_parameters`):
`m_t = 172`, `m_W = 80.385`, `m_Z = 91.1876`, `m_H = 125`, `Γ_W = 2.108`, `Γ_Z = 2.4952`, and the quark masses `0.06983, 0.06984, 0.15, 1.3, 4.75` (u, d, s, c, b), in the Legacy `.in` of
the collider and fixed-target templates, in the six `resbos.in` (`resbos_root`), in `templates/ResBos2W/resbos_w.config` and in `templates/FixedTarget/resbos2/fixedtarget.config`.
So Legacy mode, ResBos2 mode and `resbos_root` use the same inputs without any `[physics]`. (Before 2026-10-14 the Legacy `.in` had `M_W = 80.358`, `M_Z = 91.118`; `resbos.in` had `m_t = 173.5`, `Γ_W = 2.0906`;
the fixed-target ResBos2 config had massless light quarks, `m_t = 173.5` and no `mW`, so ResBos2 used its built-in `mW = 80.48`.)

`[physics]` overrides them from the `.ini`. A key that is not given keeps the template value (with `w_grid = resbos2` the electroweak keys come from the ResBos2 config and the quark masses, the top included, from the Legacy
template; they are written to all files). A value is written to **every** file that has it:

| Key | Written to |
|---|---|
| `mt mw mz mh` | Legacy `.in` (`t,W,Z,h` line), `resbos.in` (`mt,mh`, W and Z mass lines), ResBos2 config (`mT mW mZ mH`) |
| `gamw gamz` | `resbos.in` (width of the mass lines), ResBos2 config (`gamW gamZ`) |
| `mu md ms mc mb` | Legacy `.in` (`Quark masses` line), ResBos2 config |
| `gamt gamh gf alpha_em0 alpha_em_mz ew_mass_scheme` | ResBos2 config only (ignored with a note when `w_grid = legacy`) |

`sinw2` and `ew_inputs` are refused: ResBos2 hard-wires `EWInputs = GFMWMZ` and derives `sin²θ_W = 1 − m_W²/m_Z²`; those config keys are never read. `dest/PHYSICS.txt` lists what was written and where each value came from; the
driver prints a WARNING when the templates disagree on a value that `[physics]` does not set.

**What is still not the same in every code:**
* **Electroweak scheme.** ResBos2: `G_F, m_W, m_Z` inputs, `sin²θ_W = 1 − m_W²/m_Z²` (= 0.2229 with these masses), α from `G_F`. Legacy (`res.for`): `G_μ = 1.1663787e-5`, `α(0) = 1/137.036`, and a hard-wired
  `sin²θ_eff = 0.231676` ("effective Born"). The inputs are equal, the couplings are not. The ZU/ZD ratio ResBos2/Legacy of 1.00 ± 0.02 (E253 validation) includes this difference; it was not isolated.
* **`w_pert`/`w_asym`:** the masses are `DATA` statements in the Fortran (`G_F = 1.16637e-5`, `M_Z = 91.1875`, `M_W = 80.385`); no `.in` changes them. At `order = NLO` (all these campaigns) `get_yk_new` does not use the `w_pert`/`w_asym` values, only checks their grids, so these built-in numbers do not enter the result. The differences from the values above are 7e-6 (`G_F`) and 1e-6 (`M_Z`) in relative terms.
* **Effect on production.** New Legacy campaigns use `M_W = 80.385`, `M_Z = 91.1876` (the earlier ones 80.358, 91.118) and the new `Γ_W`; the existing `Simulations/` files were not regenerated. In fixed target, ResBos2 now takes `mW = 80.385`
  instead of 80.48 and massive light quarks; the agreement with Yao's reference tables (`data/yao_reference`, `data/regression`) was **not re-run** and is expected to move.
* The ZU/ZD 8 TeV validation of the ResBos2 grid was done with the old inputs (`m_t = 173.5`, massless light quarks, Legacy 80.358/91.118) and was not repeated.

The 12 `*_ResBos2W.ini` examples are made from the Legacy ones by `scripts/make_r2w_examples.py` (they restrict the Q range to index 1–30 and generate 40 < Q < 200 GeV: one ResBos2 run per Q node makes the 80-node grid costly,
and the Z/W resonance region is what the analyses use). **Status:** ZU and ZD at pp 8 TeV is validated (docs/COLLIDER_RESBOS2_W_WORKFLOW.md); the scripts for W+, W−, Z0 and for ppbar are generated and pass the prepare step
(`tests/test_run_process_r2w.py`), but they have not been run on the HPCC and their grids have not been compared with Legacy's.

## Collider campaigns

For each boson (`processes`) one chain runs, all inside `dest/`:

```
w_pert  ---------------\
w_asym  -----------------> get_yk_new --> Yk grid --\
legacy LTO=3 (Y piece) --/                           +--> resbos x [resbos] runs  (VEGAS MC, never sharded)
legacy LTO=0 (main grid) ----------------------------/
legacy LTO=1 and LTO=2 (compute = NLO) --> resbos (nlodsi, nloasy) --> hadd --> <...>_NLO.root
```

* `w_pert`, `w_asym` and Legacy are split along Q (`[shards]`) into SLURM arrays and merged with a row-count check. Shard along Q only.
* The three grids must be identical (md5-checked) and Q must stay ≤ ECM: PERTURB aborts the whole shard otherwise (the driver checks the active Q range before submitting).
* Job names must stay under ~95 characters (Fortran `character*100`).
* Outputs land in `dest/`: `<name>_<tag>_<run>_resNLO.root` and `<name>_<tag>_<run>_NLO.root` (`tag` = `Wp`, `Wm`, `Z0`, `ZU`, `ZD`; `run` = a `[resbos] runs` name, `nocuts` here),
  plus `timing.log` (per-stage timings), `analysis.sb` (a SLURM job that waits for the campaign and runs `validate_campaign.py`) and `validation_summary.txt`.
* Naming for the analysis project: copy to `KFactor_Raw_simulations/Simulations/ResbosLegacy/{beam}_{ECM}{unit}_{PDF}_{PROCESS}_{CUTS}_{ORDER}.root`, e.g.
  `pp8TeVCT25NLO_Wp_nocuts_NLO.root` → `pp_8TeV_CT25NLO_Wp_nocuts_NLO.root`. The same name in two generator folders is an error there.
* `--reuse` detects stage outputs that already exist and are valid (right header and row count) and does not resubmit them; it refuses to reuse a `<job>_shards/` whose `.in` changed.
* Reference timings (ATLAS 8 TeV W±, 80×153×143 grid): `w_pert` ~3 h, Legacy ~16 h serial per full grid (hence the shards), `resbos` ~4 min per 25 M events.
  Rerunning the Z0 production with the tighter integration tolerance (1e-7) is slower than the old 1e-4 runs, hence 20 Legacy shards.
* Adding a cut set to a finished campaign: add it to `[resbos] runs`/`[cuts.<name>]` and use `--resbos-only --submit`.

## Fixed-target campaigns

Per target (pp, pd, or the single one) the driver creates a Legacy array with one task per measured point (LTO −1, 3 and 1 in the same task), a merge job, a `GetFixed` job, and one
final job that integrates the NLO in qT and writes the tables. Details and physics: `FIXED_TARGET_WORKFLOW.md`.

```
dest/
  legacy/main
  legacy/<target>/points/pt<N>/{inp/, <name>_<LO|Y|dsi>_pt<N>.in, .out}   run_<name>_points.sb  run_<name>_merge.sb
  legacy/<target>/<name>_{LO,Y,dsi}.out                                    merged (15 header lines + data)
  resbos2/<set>/{fixedtarget.config, <set>, <set>_pert.txt, run_getfixed.sb, <set>_ResBos2_w321.dat}
  resbos2/ConvGrids/                                                       generated by the first GetFixed run of a PDF, shared
  results/<set>_<PDF>_LO_NLO_W321.txt                                      LO, NLO, W321 and K-factors (per target for the ratio sets)
  results/<name>_<set>_LO_NLO.txt                                          per-target LO and NLO
```

* `compute` is any subset of `LO, NLO, resNLO`; the final K-factor table needs all three and every target of the dataset.
* The first `GetFixed` job generates the ConvGrids and the other targets wait for it; `[fixedtarget] convgrids = <dir>` reuses a finished set and runs them in parallel.
* One dataset is at most 184 array tasks per target; the HPCC allows 1000 queued tasks per user, so submit datasets one at a time.
* The final job needs python3 with numpy and scipy: `[fixedtarget] conda_env = resbosflow` (create it once with `module load Miniforge3/25.11.0-1; conda env create -f environment.yml`) or `final_modules`.
* Naming for the analysis project: `import_fixed_target.py` (in `KFactor_Raw_simulations`) splits these tables into one file per beam and order
  (`pCu_38.8GeV_CT25NLO_DY_E201_NLO.txt`, ...; LO/NLO to `ResbosLegacy/`, resNLO to `Resbos2/`).
* To reproduce Yao: `pdf = pp830a016`, `[executables] legacy = <his main>`, `[fixedtarget] lhapdf_data_path = <his PDF share>`; expected: LO and W321 identical, NLO within ~0.1 %.
* Not automated: the fixed-xF treatment of E866/E906 (rapidity depends on qT) and W432.

## New energy, process or dataset

* **New collider energy:** copy the closest `.ini`; change `name`, `ecm`, `dest` and the Q cap in `[grids] active` (Q index with Q ≤ ECM; list the grid with `cat templates/<t>/legacy/inp/q_grid.inp`). Use the 13 TeV
  template if the y range must be wider than ±5.6, the Tevatron one for ppbar. Several energies from one `.ini`: replace `[campaign] name/ecm` by an `[energies]` section
  (`<label> = <ecm_GeV>, <file_prefix>` per line).
* **Another boson:** `W+`, `W-`, `Z0`, `A0`, `ZU`, `ZD` are wired end to end at `order = NLO`. `Z0` at NNLO and `A0` at NNLO are not (no conversion constant in `get_yk_new.f`);
  NNLO needs real `R_Ai` tables (`[get_yk_new] r_ai_<tag>`).
* **Another fixed-target set:** add it to `FT_DATASETS` in `run_process.py` (ECM, Jacobian, targets with Legacy iBeam/FRACT_N and the name `GetFixed` knows) and to `FixedTarget.cc`'s
  name table in ResBos2; put its table (y col 1, Q col 2, data col 4) in `templates/FixTargetTables/`.
* **Custom Q×y grid (collider):** `[grids] generate = yes` builds one from the ranges given (see the comments in `scripts/make_grid_from_data.py`); it writes into the template's `inp/` folders.

## Common failures

| Message | Cause / fix |
|---|---|
| `... already exists (use --reuse ...)` | `dest` is not empty: use `--reuse` or a new folder |
| `executable(s) not found` / `not found: Legacy main ...` | build with `setup.sb` or point `[executables]` at the files |
| `[grids] active includes Q points above ... ecm` | lower the Q_max index of `active` |
| `... is N chars; the codes truncate at 100` | shorten `[campaign] name` |
| `qT grid differs between ...` / `... grid differs` | the three template grids must be identical |
| `[energies] is not used in mode = fixedtarget` (or similar) | the section belongs to the other mode |
| `GetFixed` job FAILED but the `.dat` is complete | normal for the raw program (exit 1); the driver's job judges by the row count |
