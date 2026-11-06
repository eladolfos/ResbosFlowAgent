#!/bin/bash
# collect_env.sh [--check PATH]...
#
# Read-only report of the machine it runs on, to fill local/env.md: scheduler, modules, compilers, LHAPDF, HOPPET, ROOT, python/numpy,
# disk space, and whether the given paths exist. It runs no ResBos executable and submits nothing.
# Runs on the cluster (login shell). In remote mode:  python3 scripts/remote.py run -- bash scripts/collect_env.sh --check <path> ...
# Paste the output as facts into local/env.md; anything missing from the output is "not verified".

CHECKS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECKS+=("$2"); shift 2;;
    *) echo "usage: collect_env.sh [--check PATH]..." >&2; exit 2;;
  esac
done

sec() { printf '\n== %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

sec "machine"
echo "date: $(date '+%F %T')"
echo "host: $(hostname)"
echo "kernel: $(uname -sr)"
[ -r /etc/os-release ] && grep -E '^PRETTY_NAME=' /etc/os-release

sec "scheduler"
for c in sbatch squeue sinfo qsub condor_submit bsub; do
  have "$c" && echo "found: $c -> $(command -v $c)"
done
have sinfo && { echo "--- sinfo -s"; sinfo -s 2>&1 | head -40; }
have sbatch || echo "NOTE: sbatch not found; the driver submits with sbatch (SLURM only)"

sec "modules"
if type module >/dev/null 2>&1; then
  echo "module command: available"
  module -t list 2>&1 | head -30
  echo "--- module -t avail (filtered: gcc gnu openmpi lhapdf hoppet root python scipy conda)"
  module -t avail 2>&1 | grep -iE '^(gcc|gnu|openmpi|lhapdf|hoppet|root|python|scipy|conda|miniconda)' | head -80
else
  echo "module command: NOT available (the generated job scripts call 'module purge' / 'module load')"
fi

sec "compilers and python"
for c in gcc gfortran g++ python3 make cmake rsync git; do
  if have "$c"; then printf '%s: ' "$c"; "$c" --version 2>&1 | head -1; else echo "$c: not found"; fi
done
python3 -c "import numpy; print('numpy', numpy.__version__)" 2>&1 | tail -1

sec "LHAPDF"
if have lhapdf-config; then
  echo "version: $(lhapdf-config --version)"
  echo "prefix:  $(lhapdf-config --prefix)"
  echo "datadir: $(lhapdf-config --datadir)"
else
  echo "lhapdf-config: not found in PATH (set [environment] lhapdf to your prefix)"
fi
echo "LHAPDF_DATA_PATH=${LHAPDF_DATA_PATH:-<unset>}"
if have lhapdf; then
  echo "installed sets: $(lhapdf ls --installed 2>/dev/null | wc -l)"
  lhapdf ls --installed 2>/dev/null | head -60
fi

sec "HOPPET"
if have hoppet-config; then echo "version: $(hoppet-config --version 2>&1)"; echo "prefix:  $(hoppet-config --prefix 2>&1)"
else echo "hoppet-config: not found in PATH (give the prefix by hand and record its version)"; fi

sec "ROOT"
if have root-config; then echo "version: $(root-config --version)"; echo "prefix:  $(root-config --prefix)"
else echo "root-config: not found in PATH (needed for resbos ntuples and the fixed-target final job; give the thisroot.sh path)"; fi
echo "ROOTSYS=${ROOTSYS:-<unset>}"

sec "environment variables"
echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-<unset>}"
echo "SCRATCH=${SCRATCH:-<unset>}"

sec "disk"
df -h "$HOME" 2>&1 | tail -n +1
[ -n "${SCRATCH:-}" ] && df -h "$SCRATCH" 2>&1 | tail -n 1

if [ ${#CHECKS[@]} -gt 0 ]; then
  sec "paths checked"
  for p in "${CHECKS[@]}"; do
    q="${p/#\~/$HOME}"
    if [ -e "$q" ]; then
      printf 'EXISTS   %s  [%s%s%s]\n' "$p" "$([ -d "$q" ] && echo dir || echo file)" "$([ -x "$q" ] && echo ' executable')" "$([ -w "$q" ] && echo ' writable')"
      [ -d "$q" ] && df -h "$q" 2>&1 | tail -n 1
    else
      printf 'MISSING  %s\n' "$p"
    fi
  done
fi
echo
echo "== end of report (nothing was executed from the ResBos codes; nothing was submitted)"
