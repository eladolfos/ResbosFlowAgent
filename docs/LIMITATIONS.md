# Limitations

What does not work yet on an installation other than the author's, and what is known to be wrong. Read this before telling a user "it will run". Last checked against the
ResbosFlow commit `0f6e46c` (2026-11-06) by reading `run_process.py`; nothing in this repository has been executed on a second installation.

## Toolchain assumptions (the driver)

Two opt-in sections were added to `run_process.py` in this repository (see `docs/SOURCE.md`). Without them the generated scripts are identical to ResbosFlow's (checked by `diff -r` of two
prepared campaigns, collider and fixed target, apart from the path of `run_process.py` inside the scripts).

| Topic | State | What to do |
|---|---|---|
| Partition, account, qos, constraint, extra options, walltime ceiling | **`[scheduler]` section** rewrites the `#SBATCH` header of every generated script. Without it: partition `general-long`, no account | skill `adapt-scheduler` |
| Memory, CPUs, nodes, `--time` per job | still set by the driver; no key (only the `max_time` ceiling) | tell the user if their site needs other values |
| Capped walltimes | a ceiling also lowers jobs that wait for a whole campaign (`validate`, 2 days) and shards that need hours | raise `[shards]`; the driver prints a warning with the longest original time |
| Modules and library paths | `[environment]` sets `modules`, `lhapdf`, `hoppet`, `root_setup` for every job, including the shard scripts (`run_*_array.sb`) when the section exists. Without `[environment]` everything uses the author's paths and modules | always set it (`campaign_review.py show` warns) |
| SLURM only | jobs are chained with `sbatch --dependency=afterok`; PBS, HTCondor, LSF or a plain workstation cannot submit. Preparation still works | add a scheduler backend (not written) |
| Environment modules | every job script starts with `module purge` and `module load <[environment] modules>` (the fixed-target final job also uses `final_modules`, `conda_module`). A site without Lmod/Environment Modules fails | make module handling optional (not written) |
| Shell lines of the user's own batch script (`conda activate`, `ulimit`, `OMP_NUM_THREADS`, other `source` lines) | not carried over; no key | report them in `adapt-scheduler`; extend the driver if needed |
| Fixed set of Legacy-family executables | five codes with the author's `.in` formats | a differently modified build can have another `.in` or output layout: compatibility check by version (not written) |
| `scripts/` need only the standard library, except the fixed-target final job (numpy) and the ROOT macros | | checked in `discover-environment` |
| `run_process.py --submit` | bypasses the approval | use `scripts/campaign_review.py submit` (`rules/approval_before_submit.md`) |

The `[scheduler]` and shard-environment changes were tested by preparing campaigns with fake executables (no job has run through them): header lines, account/qos/extra insertion, the
walltime ceiling and unknown-key rejection. The assistant can prepare and inspect campaigns on any machine; whether a particular site accepts the generated scripts is only known by submitting a small campaign.

## Remote mode (`scripts/remote.py`)

- **Windows:** the laptop side is supported only inside WSL2 (Ubuntu); native Windows lacks `ControlMaster` and `rsync`. The WSL instructions (`QUICKSTART.md`, `docs/REMOTE.md`) have not been tested on a real Windows machine.

- Tested only with a fake `ssh` (commands run in a local folder). Not used against the real HPCC yet: the assumptions are `ControlMaster`/`ControlPath` in `~/.ssh/config`, `ProxyJump` through the gateway,
  `bash -lc` defining `module` on the node, and `rsync` on both ends.
- The allow list is a guard rail; the `.claude/settings.json` deny rules only bind Claude Code's own shell tool. Output the agent reads is sent to the model provider (`docs/REMOTE.md`).
- `scripts/ssh_check.py` was tested with a throw-away home folder, the real local `ssh -G`, a fake `ssh` and unit checks of the error classification; never against a real cluster. The connection test is `BatchMode`: it cannot answer password/2FA, so many sites will report `AUTH`/`CLOSED` even when SSH works interactively; with `ProxyJump`, OpenSSH hides the jump host's own error, so the jump host must be tested alone.
- The RESOURCES summary and the execution plan (`campaign_review.py resources`: steps, what waits for what, placeholders) are read from the generated scripts and the dependency lines of `submit_all.sh`; it was checked on one collider and one fixed-target example. The core-hour figure is a ceiling from requested walltimes (the driver's defaults, not measurements).
  Shard arrays have no throttle; a form of `submit_all.sh` it cannot parse (for example some ResBos2-W or experimental-point layouts) shows "not available" rather than a wrong number.
- Approval records live on the cluster (next to `dest`), not on the laptop.
- `sync` copies files but does not delete removed ones on the cluster.

## Onboarding, preflight and the smoke test

- `ResbosFlowAI` (launcher), `scripts/preflight.py` and the skill `resbosflow` were tested with fake `claude`, `ssh` and `sbatch` and with simulated LHAPDF/ROOT tools (PASS and FAIL paths). Not used on the real HPCC.
- The preflight job checks that files exist, shared libraries resolve (`ldd`; the executables are not run), the PDF set is listed by `lhapdf ls --installed`, ROOT/numpy are visible and the folder for `dest` is writable.
  It cannot detect a build that links fine but is incompatible with the `.in` formats, or wrong physics.
- `recipes/smoke-test-collider.md` / `examples/smoke_collider_Wp_13TeV.ini` prepare correctly (24 shard tasks, 31 scheduler tasks in total, two Legacy passes) but **have never been run**: wall time, disk use and whether `resbos` is happy with only three Q points are unknown.
  The authors should run it once and record the numbers before handing the repository to someone else.

## Physics and numerics

- **Z0 normalisation:** Z0 cross sections from the chain are a flat factor ~2 too large at every energy; W is fine. Not fixed. Do not divide silently.
- **Legacy CSS grid is exactly zero for qT >= 2Q** (`res.for`, `fresum=0`). For resummed collider events use the W grid from ResBos2 (`COLLIDER_RESBOS2_W_WORKFLOW.md`).
- **NNLO** needs real `R_Ai` tables (`[get_yk_new] r_ai_<tag>`); `Z0` and `A0` at NNLO are not wired. With `order = NLO` an all-ones `R_Ai` table is generated (identical result).
- **A0 override:** a Legacy build with the `Type_V = 'A0'` override on gives A0 LO/NLO ~1250 Q^2 too large (K = NLO/LO is unaffected; W/Z/ZU/ZD never reach that branch).
  Fixed target needs the override off.
- **HOPPET version:** 1.3.0-devel vs 1.2.0 gives 0.13 % rms (max 0.8 %) on ResBos2 W321 for E605. Record versions when comparing.
- **PDF-name trap:** see `rules/pdf_name_trap.md`.

## Verification status

- The `LTO=1` and `LTO=2` output shapes (15 header lines, 1 line per point) were read off `main.for`, not verified on a real output for every build.
- The runtime provenance log (`provenance_runtime.log`) has not yet been produced by a real job.
- Fixed target: not automated are the fixed-xF refinement (y(qT) < y0) and W432.
- The driver was written and tested on one cluster. A first campaign on a new installation is a test of this repository, not just of the physics: start small.

## Not in this repository

- The Fortran/C++ sources and the build scripts (`setup.sb`, `build_resbos2_deps.sb`) stay in ResbosFlow. The documents under `docs/` that mention `codes/` or `setup.sb` refer to that repository.
- Campaign outputs and reference data (`data/`, `regression/`).
