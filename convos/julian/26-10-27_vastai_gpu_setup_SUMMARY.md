# SUMMARY: Renting a VastAI GPU for ARENA

**Last updated:** 26-10-27 (automation script `vast/arena_vast.py` implemented; not yet tested on a real rental)

Julian has no local NVIDIA GPU and chose VastAI to rent one (the options were compared in `convos/julian/26-10-23_arena_setup_LOG.md`, entry *cloud GPU options for ARENA*). Full step list: LOG entry *VastAI setup walkthrough*.

**Gotchas not covered by ARENA's own instructions**
- Filter hosts by **Max CUDA ≥ 13.0**: ARENA's `requirements.txt` installs torch built for CUDA 13 (local venv: `2.14.1+cu130`). [verified: 26-10-27] On an older driver, CUDA won't be available. [concluded]
- Use `install_uv.sh --platform vastai` (uv venv, same as the local `.venv`), not `install.sh` (conda). `install.sh` also hardcodes the folder name `ARENA_materials`; `install_uv.sh` works under any folder name. [verified: read both scripts]

**Short version of the setup:** prepaid account → SSH key (Julian already uses `~/.ssh/id_rsa` with VastAI) added to the account *before* renting → rent an RTX 3060/3090/A4000/A5000 class GPU with ≥ 50 GB disk, direct SSH, on-demand → `Host arena` entry in `~/.ssh/config.d/vastai` (IP/port change per instance) → VS Code Remote-SSH → clone + `install_uv.sh --platform vastai` → select `arena-env` interpreter and kernel → check `torch.cuda.is_available()`.

**Stop vs destroy:** a stopped instance still pays for storage and may not get its GPU back on restart (stuck in "SCHEDULING"). [verified: VastAI docs] Recommendation: push to git and destroy after each session. [concluded: not ratified]

**Open / untested** [assumed]: whether pushing from the VM works without extra auth setup; whether disk size can be changed after creation.

**Automation: `vast/arena_vast.py`** (implemented 26-10-27; LOG entry *automation script implemented (untested on a real rental)*). Julian works entirely on the rented machine via VS Code Remote-SSH [decided: Q1 C:]; the script handles everything around that. Run with `.venv/bin/python vast/arena_vast.py <cmd>`:
- `offers` (browse) · `up` (rent → upload working tree incl. `.git` and uncommitted changes → copy `.env` → `vast/remote_setup.sh` builds `.venv` within 15 min, else the host is blacklisted → GPU check → opens VS Code on `/root/ARENA_2026`) · `status` (all instances on the account and their cost so far) · `pull` / `push` (rsync, never deleting; a preview lists files that would be overwritten and asks first) · `down` (pull, then destroy; no destroy if the pull fails).
- Only instances labelled `arena` are touched; ssh alias `arena` [decided: Q8 C:] in `~/.ssh/config.d/arena.conf`.
- One config per GPU type [decided: Q6 C:]: `vast/rtx_3060.yaml` (image `vastai/base-image:cuda-13.0.3-auto`, which ships uv [decided: C: no separate uv install]; max $0.30/hr, asks above $0.15/hr; 80 GB disk; no CN hosts; reliability > 0.95). Host blacklist: `vast/blacklist.yaml`.
- The upload file list comes from `git ls-files`, not rsync's `.gitignore` filter, because rsync ignores ARENA's `!…/part32_…/data` negation and would skip 6 tracked files. [verified: 26-10-27]
- VS Code installs python, pylance, jupyter and ruff on every ssh host via `remote.SSH.defaultExtensions` in Julian's user settings. [decided: Q5 C:]
- Install all of `requirements.txt` with a 15 min budget: [assumed] (Q4 left unanswered, my recommendation used).
- Verified: `offers`/`status` against the live API, sync and preview logic against a local stand-in for the remote. **Not yet tested: a real `up`/`down` cycle.** [assumed]
- The copied SPD files `run_vast.py`/`vast_config.yaml` were deleted (originals in `~/projects/targeted-parameter-decomposition/spd/scripts/`).

- See also: `convos/julian/26-10-23_arena_setup_SUMMARY.md` — local environment setup (venv, kernel selection); the GPU question was first raised there.
