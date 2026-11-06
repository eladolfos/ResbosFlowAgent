# Environment profile (example)

Written by `discover-environment`. Facts only: paste command output, never guess. Items not checked go under "Not verified".

- Date:
- Host / login node:
- OS:

## Scheduler
- Type: slurm | pbs | htcondor | none
- Partitions (name, max walltime):
- Account (if required):
- Queue limits (tasks per user, array tasks count?):
- How the user connects (direct login node, ssh ControlMaster, VPN):

## Modules and toolchain
- `module` available: yes | no
- Modules to load (for `[environment] modules`):
- gcc / gfortran version:
- python3 version, numpy importable:

## Libraries
| Library | Version | Prefix | Source of the version |
|---|---|---|---|
| LHAPDF | | | `lhapdf-config --version` |
| HOPPET | | | |
| ROOT | | | `root-config --version` |
| `thisroot.sh` | | | |

## PDF sets
- LHAPDF data path(s):
- Sets installed that matter:
- Sets present in more than one path (see `rules/pdf_name_trap.md`):

## ResBos executables
| Code | Path | Exists / executable | Notes (version, build flags, A0 override on/off for Legacy) |
|---|---|---|---|
| w_pert | | | |
| w_asym | | | |
| Legacy `main` (collider) | | | |
| Legacy `main` (fixed target, A0 override off) | | | |
| get_yk_new | | | |
| resbos_root | | | |
| ResBos2 `GetFixed` + env script | | | |

## Scratch space
- Path for `dest` folders:
- Quota:

## Not verified
-
