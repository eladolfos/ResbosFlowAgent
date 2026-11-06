# PDF-name trap

## Rule
A PDF set name is only meaningful together with the LHAPDF installation that resolves it. Record which installation and which data path a campaign used.

## Why
In the original setup `pp830a016` existed in two LHAPDF installs with different grids (3 members vs 1; MZ 91.1876 vs 91.1870). The same name gave different numbers
depending on search order. Any user can hit the same thing, for example when a shared and a personal `LHAPDF_DATA_PATH` both contain a set.

## What to do
1. During `discover-environment`, list the installed sets with `lhapdf ls --installed` and the data path with `lhapdf-config --datadir`; write both to `local/env.md`.
2. If a set name appears in more than one `LHAPDF_DATA_PATH` entry, ask the user which one is meant and pin it (for fixed target: `[fixedtarget] lhapdf_data_path`).
3. Never substitute a "similar" set when the requested one is missing. Ask.

## Enforced by
`scripts/provenance.py` records the PDF search paths and the modules a campaign used (`PROVENANCE.txt`, `provenance_runtime.log`). Nothing prevents the ambiguity itself.
