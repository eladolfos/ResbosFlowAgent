# ResbosFlowAgent

Run resummed-qT (ResBos family, CSS formalism) simulation campaigns **on your own installation**, with an AI assistant that follows written rules.
You do not build anything from this repository: your executables, LHAPDF, HOPPET and ROOT stay where they are. The repository gives the assistant:

- `AGENTS.md` / `CLAUDE.md` — how to behave;
- `rules/` — the invariants that silently break results if violated;
- `skills/` — procedures: `resbosflow` (onboarding), `setup-ssh`, `discover-environment`, `adapt-scheduler`, `new-collider-campaign`, `new-fixedtarget-campaign`, `review-and-authorize`, `validate-and-diagnose`, `add-recipe`;
- `recipes/` — concrete calculations and how far each one is validated;
- `ResbosFlowAI` — the launcher;
- `run_process.py`, `scripts/`, `templates/`, `examples/` — the deterministic toolchain the assistant calls (copied from ResbosFlow, see `docs/SOURCE.md`).

**What it can compute:** orders `NLO`, `resNLO` (and `LO` for fixed target); collider W+, W-, Z0, photon, Z/gamma* in pp and ppbar; fixed-target Drell-Yan (E605, E866, E906). See `docs/CAPABILITIES.md`.

The assistant chooses and runs the scripts and explains the result. It does not calculate physics itself.

Start with `QUICKSTART.md`: run `./ResbosFlowAI`, and the assistant asks whether you want your software and paths reviewed, then sends a test.

## Use

Two ways to run it (`AGENTS.md`, "Where commands run"):

- **Remote mode (the usual one):** the agent runs on your laptop and reaches the cluster through one SSH connection that you open yourself; `scripts/remote.py` is the only channel, with an allow list and a rate limit. Setup: `docs/REMOTE.md`.
- **Local mode:** the agent runs on the machine that has the executables and the scheduler.


```bash
git clone <this repository> && cd ResbosFlowAgent
claude            # or any agent that reads AGENTS.md
```

Then say, for instance: *"Describe my environment"* (runs `discover-environment`), *"Prepare W+ and W- at 13 TeV with CT18NLO"* (`new-collider-campaign`),
*"Add a recipe for Z at 5.02 TeV with my PDF"* (`add-recipe`). The assistant prepares campaigns and shows what it resolved; it submits only when you say so.

## Make your own rules or recipes

Edit the Markdown files directly or ask the assistant. Personal material goes in `local/` (git-ignored, survives updates); things to share go in `rules/`, `recipes/` or `skills/`
through a pull request. A new recipe starts as `unvalidated` until it reproduces a reference (`rules/unvalidated_recipes.md`).

## Status

New repository (2026-11-06), nothing has yet been run from it on an installation other than the authors'. The driver assumes SLURM, a partition called `general-long` and
environment modules unless you set `[scheduler]` and `[environment]` in your `.ini` (skill `adapt-scheduler`); read `docs/LIMITATIONS.md` before relying on it. Preparing and reviewing a campaign works anywhere; submitting is where the assumptions bite.

## Requirements

- Python 3 (standard library) for the driver; numpy for the fixed-target final job.
- Your own ResBos executables (Legacy family and, for fixed target and the ResBos2 W grid, ResBos2), LHAPDF, HOPPET and, for events and the fixed-target final job, ROOT.
- SLURM at present.
