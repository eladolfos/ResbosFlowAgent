# Q must not exceed the collision energy

## Rule
Every Q on the active grid must satisfy Q <= ECM (collider) and every row of the data table must satisfy Q <= ECM (fixed target).

## Why
The perturbative code (`pert.for`, PERTURB) aborts the **whole shard** when a point is kinematically impossible. One bad point loses the shard's work.

## Enforced by
`run_process.py` checks the active Q range (collider) and the data table (fixed target) at prepare time and refuses to continue.

## If violated
Lower the Q maximum in `[grids] active` (indices into `inp/q_grid.inp`; list the grid with `cat templates/<template>/legacy/inp/q_grid.inp`) or drop the offending rows of the table.
When adding a new, lower collision energy, this is the first thing to check.
