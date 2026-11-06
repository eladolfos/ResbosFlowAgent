#!/bin/bash
# Write REVISION (git commit, branch, uncommitted files) in the repository root. Run it before copying the tree to a machine
# without .git (rsync to the HPCC): scripts/provenance.py reads REVISION when there is no .git, so campaigns prepared there
# still record exactly which ResbosFlow version made them.
cd "$(dirname "$0")/.." || exit 1
dirty=$(git status --porcelain | sed 's/^...//' | tr '\n' ',' | sed 's/,$//')
{ echo "commit=$(git rev-parse HEAD)"; echo "branch=$(git rev-parse --abbrev-ref HEAD)"
  echo "date=$(date '+%F %T')"; echo "dirty=$([ -n "$dirty" ] && echo 1 || echo 0)"; echo "dirty_files=$dirty"; } > REVISION
cat REVISION
