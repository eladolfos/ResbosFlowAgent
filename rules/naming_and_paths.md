# Names and paths are short

## Rule
Keep `[campaign] name` short and `dest` paths moderate. The Fortran codes read file names into `character*100`; longer names are truncated and files collide or are not found.

## Enforced by
`run_process.py` refuses job names longer than 95 characters. It does not check the total path length of `dest`; keep it well under 100 characters where the codes receive full paths.

## If violated
Shorten `name` (and the base folder of `dest`), then prepare again with a new `dest` or `--reuse`.

## Related
- `dest` must be a new, empty folder unless `--reuse` is given. All jobs run there; executables and grids are copied into it.
- Relative paths in an `.ini` resolve against the `.ini` file's folder. A campaign `.ini` in `local/` finds `../templates` and `../scripts`.
