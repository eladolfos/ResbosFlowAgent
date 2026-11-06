# local/

Your own files. Everything here except this README and `env.example.md` is git-ignored, so `git pull` never overwrites it.

- `remote.conf` — remote mode: SSH alias and repo folder on the cluster (template `remote.example.conf`; `docs/REMOTE.md`). `remote.log` and `.remote_state.json` are written by `scripts/remote.py`.
- `env.md` — your environment profile (made by the `discover-environment` skill from `env.example.md`).
- `<campaign>.ini` — your campaigns. Keep them **directly in this folder** so `../templates` and `../scripts` in the examples still resolve.
- `recipes/` — your own recipes (skill `add-recipe`).
