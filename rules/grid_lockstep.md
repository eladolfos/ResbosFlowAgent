# Grid lockstep (collider)

## Rule
`w_pert`, `w_asym` and Legacy must run on identical (Q, qT, y) grids: the same three files `inp/{q,qt,y}_grid.inp` and the same `[grids] active` range.
`get_yk_new` combines their outputs point by point.

## Why
`get_yk_new` aborts if a (Q, qT, y) triplet differs by more than 1e-8 between the inputs. A grid edit in one code only wastes the whole chain.

## Enforced by
`run_process.py` compares the three grid sets by md5 at prepare time and refuses to continue if they differ. `get_yk_new` checks the triplets at run time.

## If violated
- Do not copy one code's grids over the others by hand. Fix the template or `[grids]` and prepare again.
- Custom grids: use `[grids] generate = yes` (see `scripts/make_grid_from_data.py`), which writes the same grid for all codes.
- Sharding splits along Q only; the shards of the three codes must use the same Q partition (the driver does this).
