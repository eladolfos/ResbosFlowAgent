# Source of the copied files

This repository holds **copies** from the ResbosFlow repository (`https://github.com/eladolfos/ResbosFlow`, branch `main`, commit `0f6e46c`, copied 2026-11-06).
They are not shared; a fix in one place does not propagate.

| Here | From ResbosFlow | Notes |
|---|---|---|
| `run_process.py` | `run_process.py` | **modified** (2026-11-06), see below |
| `scripts/` | `scripts/` | only what the driver uses: `make_shards.py`, `merge_shards.py`, `make_grid_from_data.py`, `make_fixedtarget_tables.py`, `validate_campaign.py`, `provenance.py`, `run_getnlo.sh`, `mkrevision.sh`, `*_w_asym_array.sb`, `getnlo/` |
| `templates/` | `templates/` | unmodified (includes `templates/Yao/`, Yao's tree; see its README) |
| `docs/{COLLIDER_WORKFLOW,COLLIDER_RESBOS2_W_WORKFLOW,FIXED_TARGET_WORKFLOW,CAMPAIGNS,RESBOS_ROOT}.md` | `docs/` | unmodified; references to `codes/`, `setup.sb`, `bin/` and `data/` point to ResbosFlow |
| `examples/` | `Examples/` | three `.ini`: `pp_13TeV_WpWmZ0_CT25NLO`, `pp_13TeV_Zgamma_CT25NLO_ResBos2W`, `FT_e605_CT25NLO`; `dest` and `[executables]` still hold the author's paths and must be edited |

Not copied: `codes/`, `setup.sb`, `bin/`, `data/`, the other `Examples/`, the generator scripts of the author's batch campaigns, `docs/HPCC_CONNECTION.md`, `docs/INSTALL*.md`,
`docs/CT25_COLLIDER_CAMPAIGNS_REPORT.md`.

To update a copy: diff against ResbosFlow, copy, and record the new commit here.

## Changes made here to `run_process.py` (not in ResbosFlow)

1. **`[scheduler]` section** (opt-in): `partition`, `account`, `qos`, `constraint`, `extra`, `max_time`. Implemented in `write()`: the `#SBATCH` header of every generated script is rewritten;
   `report_scheduler()` prints a summary and a warning when `--time` lines were lowered. Unknown keys are rejected.
2. **Shard scripts honour `[environment]`**: `scripts/run_w_asym_array.sb` (the template of the `w_pert`, `w_asym` and Legacy shard jobs) has the author's modules and LHAPDF/HOPPET paths written in it
   and ignored `[environment]`. When the `.ini` has an `[environment]` section, that block is replaced by `env_lines(cfg)`. Without the section nothing changes.
3. `from types import SimpleNamespace` moved to module level; `main()` calls `init_scheduler()` before building and `report_scheduler()` after.

Verification: two campaigns (collider `pp_13TeV_WpWmZ0_CT25NLO`, fixed target `FT_e605_CT25NLO`) prepared with fake executables by both drivers: the fixed-target output is identical;
the collider output differs only in the shard scripts, because that example has an `[environment]` section (a blank line is kept; one `export PATH=<hoppet>/bin` line is added, as in the other jobs).
These changes are not in ResbosFlow. To keep both drivers in step, port them there or re-apply them after updating the copy.

## Added here (not from ResbosFlow)

`ResbosFlowAI`, `QUICKSTART.md`, `scripts/campaign_review.py`, `scripts/remote.py`, `scripts/collect_env.sh`, `scripts/preflight.py`, `examples/smoke_collider_Wp_13TeV.ini`, `docs/REMOTE.md`, `.claude/settings.json`, `local/remote.example.conf`, everything under `rules/`, `skills/`, `recipes/`, `local/` and the top-level `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/LIMITATIONS.md`, `docs/SOURCE.md`, `docs/CAPABILITIES.md`;
the commented `[scheduler]` block at the end of each `examples/*.ini`.
