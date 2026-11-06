---
name: discover-environment
description: Inspect the user's machine or cluster and write local/env.md - scheduler, modules, compilers, LHAPDF/HOPPET/ROOT, installed PDF sets and the locations of their ResBos executables. Use before the first campaign, when a campaign fails with a missing executable or library, or when the user says their installation changed.
---

# discover-environment

Goal: a verified profile of the user's installation in `local/env.md` (template: `local/env.example.md`), so that campaign `.ini` files point at the user's executables
and libraries instead of the author's. Nothing is installed or built by this skill.

Read first: `rules/pdf_name_trap.md`, `rules/cluster_etiquette.md`, `docs/LIMITATIONS.md`. In remote mode (`local/remote.conf`): `python3 scripts/remote.py status` first, and every cluster command goes through `remote.py` (`docs/REMOTE.md`).

## Steps

1. **Ask what they have.** Which ResBos codes are installed and where. The collider chain needs five Legacy-family executables (`w_pert`, `w_asym`, Legacy `main`,
   `get_yk_new`, `resbos_root`); fixed target needs a Legacy `main` and ResBos2 `GetFixed` with an environment script. Ask whether their Legacy `main` was built with
   the `Type_V = 'A0'` normalisation override (`CONST=PI*ACOUPL*2.0/3.0 ! yfu test 2024.10.13 (override)`) on or off; fixed target with it on gives A0 LO/NLO ~1250 Q^2 too large.
   Ask which `.in` format family they use (`docs/COLLIDER_WORKFLOW.md`, section 1).
2. **Detect the machine with one call**: `bash scripts/collect_env.sh --check <path> --check <path> ...` (read-only; in remote mode: `python3 scripts/remote.py run -- bash scripts/collect_env.sh --check ...`).
   It reports scheduler and partitions, modules, compilers, python/numpy, LHAPDF (version, prefix, data path, installed sets), HOPPET, ROOT, disk space, and the state of every `--check` path.
   Pass the user's candidate paths: executables, `dest` base folder, library prefixes, `thisroot.sh`. The account and qos are not discoverable this way: ask the user (or take them from their batch script, `adapt-scheduler`).
   Record the HOPPET version: it changes results at the 0.1 % level. Where the report says "not found", that is "not verified", not "absent": ask the user for the prefix.
3. **Check the executables the user names** from the `--check` output: exists and executable. Do **not** run them: some read stdin or start long computations.
4. **Dry-run the driver.** Copy the closest `examples/*.ini` to `local/`, set the executables, `dest` and `[environment]` (`modules`, `lhapdf`, `hoppet`, `root_setup`),
   run `python3 run_process.py local/<x>.ini` **without** `--submit` with `dest` set to a scratch folder, and read the resolved inputs it prints. Missing files are reported here, cheaply.
5. **Compare against what the driver assumes.** Open the generated `.in` files and the job scripts (`dest/*.sb`). Report to the user, item by item:
   - SLURM `#SBATCH --partition=...` lines (without a `[scheduler]` section the driver uses the author's partition: see `docs/LIMITATIONS.md`);
   - `module purge` / `module load` lines in the job environment block;
   - differences between the user's `.in` files and the template's keys, if they supplied their own.
6. **Write `local/env.md`** from the template with facts only: command outputs, paths, versions, the date, and a "Not verified" list. Never fill a field by guessing.
7. **If the user has a batch script that works for them**, hand over to `adapt-scheduler`; it writes the `[scheduler]` and `[environment]` sections.
8. **Tell the user what blocks them**, in order: unsupported scheduler, missing executables, missing PDF set, missing ROOT for the final job. Do not edit the driver to get around it unless
   they ask for that change.

## Output
`local/env.md` plus a short summary: what works, what will not, what you did not check.

## Do not
- Do not install, build or `module load` anything permanently.
- Do not run `sbatch`, even `--test-only`, unless asked.
- Do not loop over `squeue`/`sinfo`; `collect_env.sh` gathers everything in one call.
