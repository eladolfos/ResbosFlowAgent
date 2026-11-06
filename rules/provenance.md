# Provenance

## Rule
Every campaign must be traceable to the software and inputs that produced it. Keep the files the driver writes; do not delete them.

## What the driver writes
At prepare time (`scripts/provenance.py`): `PROVENANCE.txt`, `PROVENANCE.json` and a copy of the `.ini` as `campaign.ini` in `dest`. At run time each job appends to
`provenance_runtime.log` (node, compiler, loaded modules, library and PDF search paths).

## Why
Results differ by version: the original authors measured 0.13 % rms (max 0.8 %) between two HOPPET versions on the same input. Without the versions on record, nobody
can tell a physics change from an installation difference.

## For the assistant
- Run the campaign through the driver so provenance is written.
- When comparing against a reference, state the versions of both sides.
- If you add a new executable or input that the driver should know about, make it visible to `scripts/provenance.py` (see "Provenance" in `docs/CAMPAIGNS.md`).
- The repository also holds a `REVISION` file when there is no `.git`. Regenerate it with `scripts/mkrevision.sh` before copying the tree to a host without git.

## Enforced by
The driver, at prepare time. The runtime log has not yet been produced by a real job in this repository; see `docs/LIMITATIONS.md`.
