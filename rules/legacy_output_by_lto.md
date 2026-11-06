# Legacy output depends on LTO

## Rule
The `LTO` value in the Legacy `.in` decides what the output contains. Every `LTO` writes 15 header lines; the number of rows per point differs.

| LTO | Piece | Rows per point |
|---|---|---|
| -1 | LO (fixed target) | 1 |
| 0 | full CSS grid (the "Main data grid" of `resbos`) | 1 |
| 1 | DeltaSigma | 1 |
| 2 | asymptotic | 1 |
| 3 | Y piece (input of `get_yk_new`) | 3 |

## Why
`get_yk_new` and the merge scripts read a fixed layout. Wrong header or row counts shift every later column without raising an error.

## Enforced by
The driver rewrites `LTO` itself for each pass and, when merging shards, strips 15 header lines and checks the row count per piece (fixed target: LO 1 per point,
LTO=1 one per qT, LTO=3 three per qT). The `LTO=1` and `LTO=2` shapes were read from the source, not verified on a real output of every build; see `docs/LIMITATIONS.md`.

## If violated
If a user's Legacy build has a different header length or column layout, stop. The merge scripts assume the layout above. Report the difference; do not adapt the scripts silently.
