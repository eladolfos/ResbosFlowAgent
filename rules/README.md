# Rules

Invariants of the workflow. Each file states the rule, why it exists, what enforces it, and what to do when it is violated.
"Enforced by" names the script that checks it; if that is "nothing", you are the only check, so be careful.

| File | Rule in one line |
|---|---|
| `determinism.md` | Physics and file mechanics come from the scripts, never from the model. |
| `grid_lockstep.md` | `w_pert`, `w_asym` and Legacy run on identical (Q, qT, y) grids. |
| `q_le_ecm.md` | Every Q point must be at or below the collision energy. |
| `legacy_output_by_lto.md` | The shape of a Legacy output depends on `LTO`. |
| `naming_and_paths.md` | Job names and paths are truncated at 100 characters by the Fortran codes. |
| `pdf_name_trap.md` | The same LHAPDF set name can be two different sets in two installs. |
| `provenance.md` | Every campaign records which software and inputs produced it. |
| `unvalidated_recipes.md` | A recipe is not a result until it reproduces a reference. |
| `approval_before_submit.md` | Submit only after the user has reviewed paths and scripts and authorized that campaign. |
| `cluster_etiquette.md` | Prepare before submitting; do not poll. |

To add a rule: copy the structure of an existing file (Rule / Why / Enforced by / If violated), add it to the table above, and, if a script can check it, say which.
