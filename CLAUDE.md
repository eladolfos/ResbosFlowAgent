@AGENTS.md

# Claude Code notes

- Project skills live in `skills/` and are exposed through the symlink `.claude/skills -> ../skills`. If the symlink is missing (for example after unzipping on
  Windows), recreate it or copy `skills/` to `.claude/skills/`.
- The rules above are instructions, not guarantees. The invariants in `rules/` are also enforced by `run_process.py` and `scripts/validate_campaign.py` where
  possible; always run those instead of checking by eye.
- Ask before running anything that submits jobs, writes outside this repository, or contacts a cluster.
