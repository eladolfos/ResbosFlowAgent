---
name: review-and-authorize
description: Before any campaign is submitted - tell the user exactly where files will be read and written, let them set their own paths, show the .ini and what the generated scripts will send, and obtain their explicit authorization. Use for every campaign, right after the .ini is written and before anything is submitted.
---

# review-and-authorize

Goal: the user knows where every file goes, has put their own paths in, has seen what will be sent to the scheduler, and has authorized it. The authorization is recorded and bound
to the exact `.ini` and the exact generated scripts; changing either voids it. Nothing is submitted without it.

Read first: `rules/approval_before_submit.md`, `rules/cluster_etiquette.md`, `rules/pdf_name_trap.md`, `local/env.md`.

Remote mode (`local/remote.conf` exists): edit the `.ini` on the laptop, `python3 scripts/remote.py push`, and run every cluster command as `python3 scripts/remote.py run -- <command>` (table in `AGENTS.md`, setup in `docs/REMOTE.md`). Paths are cluster paths.

The tool is `scripts/campaign_review.py` (`show`, `approve`, `submit`). It prints the path map, the environment, the scheduler options, what the prepared scripts ask for, and refuses
to submit without a matching approval.

## Steps

1. **Path map first.** Run `python3 scripts/campaign_review.py show local/<name>.ini`. Explain the table to the user in plain words:
   - `WRITE paths.dest` is the one folder where all outputs and logs of this campaign are written. Every job runs there. It must be new (or use `--reuse`).
   - `READ` lines are the things the jobs only read: templates, scripts, executables, libraries, PDF data.
   - Say what ends up in `dest` (per boson: merged grids of `w_pert`, `w_asym`, `legacy`, `get_yk_new`; `resbos` logs and `.root` ntuples; `submit_all.sh`; `PROVENANCE.*`;
     fixed target: `legacy/`, `resbos2/`, `results/`) and the sizes quoted in `docs/CAMPAIGNS.md` (about 1 GB per `.root`; `stage_outputs = copy` adds about 1 GB per boson). Do not invent other sizes.
2. **The user supplies their paths.** For each path ask the user to confirm or replace it: `dest` (scratch space with enough room), `[executables]`, `[environment]` `lhapdf`, `hoppet`, `root_setup`, and for
   fixed target `getfixed`, `resbos2_env`, `lhapdf_data_path`. Propose values from `local/env.md`; never invent a path. If you are on the cluster, check each with `test -e`. Any path the table flags as
   the original author's (`lopezels`) must be replaced. Edit only the `.ini` in `local/`, then `show` again until there are no warnings the user has not accepted.
3. **Scheduler.** If `show` says there is no `[scheduler]` section, the scripts ask for the author's partition and no account. Ask for the user's partition, account, qos and walltime limit, or run the
   `adapt-scheduler` skill if they have an example script.
4. **Prepare, do not submit.** `python3 run_process.py local/<name>.ini` (add `--reuse` if `dest` exists from an earlier preparation). Then `show --full`. In remote mode `push` first, so the cluster has the `.ini` that the user is about to approve.
5. **Present a review to the user**, short and concrete, in this order:
   1. the `.ini` (the full text printed by `--full`; point out the lines that matter: energy, processes, PDF, order, grids, shards);
   2. where it reads and writes (the table);
   3. what will be sent: number of scripts, partitions, accounts, walltimes, total array tasks against the site's queue limit (`rules/cluster_etiquette.md`);
   4. warnings that remain, and anything unverified (`docs/LIMITATIONS.md`): for example walltimes capped by `max_time`, a PDF set present in two LHAPDF paths.
6. **Ask for authorization** with a direct question that names the campaign and the destination: "Approve `<name>` to be submitted to partition `<p>`, writing to `<dest>`?" Then:
   - Authorization is an explicit yes to that question after step 5. "Looks fine", a question, or an answer about something else is not authorization.
   - Record it: `python3 scripts/campaign_review.py approve local/<name>.ini --yes-i-reviewed --note "<the user's words>"`. The user may run it themselves
     (in Claude Code: `! python3 scripts/campaign_review.py approve local/<name>.ini --yes-i-reviewed`); if they tell you to, run it and quote their words in `--note`.
7. **Submit** only after approval is recorded: `python3 scripts/campaign_review.py submit local/<name>.ini`. It refuses if the `.ini` or the prepared scripts changed after the approval, or if the campaign
   was already submitted. Report the job ids it prints. Do not poll.

## If something changes after approval
Any edit to the `.ini`, and any re-preparation that changes the scripts, voids the approval. Go back to step 4, show the user what changed, and ask again. Do not work around a refusal by calling
`run_process.py --submit`, `bash submit_all.sh` or `sbatch` yourself.

## Do not
- Do not choose `dest` for the user.
- Do not approve on the user's behalf from an earlier general permission ("go ahead with everything").
- Do not submit several campaigns on one approval: each `.ini` has its own.
