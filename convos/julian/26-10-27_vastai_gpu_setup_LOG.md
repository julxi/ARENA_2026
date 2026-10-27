# Topic: renting a VastAI GPU for ARENA

Split off from `convos/julian/26-10-23_arena_setup_LOG.md`, where the general GPU question was first answered (entry *cloud GPU options for ARENA*). In short, that entry said: this laptop has no NVIDIA GPU; ARENA documents Colab plus three rental providers (VastAI, RunPod, Lambda Labs); chapter 0 mostly runs on CPU and chapter 1 onward needs a GPU.

C: (transcribed from chat) This should go into a now convo:

C: (transcribed from chat) Alright. I want vastai I think. How does the setup work there exactly?

---

26-10-27, Claude Opus 5.5 — *VastAI setup walkthrough*

I have read ARENA's setup page (`infrastructure/core/django_run/pages/content/setup_instructions.md`, VastAI section), ARENA's `install.sh` in full, `requirements.txt`, Julian's `~/.ssh/config`, and current VastAI docs (SSH page, storage page, troubleshooting page via search).

## Two problems with ARENA's instructions

1. **The host's NVIDIA driver must support CUDA 13.** `requirements.txt` pins `torch>=2.11,<2.15`, and its comment says torch ≥2.11 on PyPI is built against CUDA 13. The local venv has `torch 2.14.1+cu130` [verified: 26-10-27]. On a host whose driver supports only CUDA 12.x, `torch.cuda.is_available()` will return False. In VastAI's search, set the "Max CUDA" filter to ≥ 13.0. ARENA's page doesn't mention this. [concluded: from the pin; the driver/CUDA compatibility rule is standard NVIDIA behavior]
2. **`install.sh` hardcodes the folder name `ARENA_materials`** (`PRIMARY_REPO_DIR="ARENA_materials"`, then `cd ARENA_materials` to run `pip install -r requirements.txt`). Cloning Julian's fork the normal way creates `ARENA_2026/`, so the script would fail at that step. Fix: clone the fork *into* a folder named `ARENA_materials`. This corrects my advice in the setup topic, which just said "clone your fork". [verified: read install.sh 26-10-27]

## Steps

**One-time (on the laptop / website)**
1. Create an account at cloud.vast.ai and add credit. VastAI is prepaid.
2. Make a dedicated key: `ssh-keygen -t ed25519 -f ~/.ssh/vastai`. Paste the contents of `~/.ssh/vastai.pub` into the account's SSH keys page. Account keys only apply to instances created afterwards, so do this first. [verified: VastAI SSH docs, 26-10-27]

**Each time you rent a machine**
3. Template: any CUDA/Ubuntu template with SSH access is fine. `install.sh` installs its own Miniconda and torch, so the template's preinstalled packages don't matter. Set disk to ≥ 50 GB when creating; I believe disk size can't be changed afterwards. [assumed]
4. Search filters: GPU = RTX 3060 / 3090 / A4000 / A5000 (ARENA's recommendation: 8 GB+ VRAM, 12 GB+ ideal); **Max CUDA ≥ 13.0**; disk ≥ 50 GB; bandwidth ≥ 100 Mbps; prefer on-demand (not interruptible), verified hosts with high reliability, and direct SSH (open ports). VastAI's docs call direct SSH faster and more reliable than its default proxy. Then click Rent.
5. When the instance is running, click its SSH button. It shows a command like `ssh -p 50983 root@154.64.230.50`.
6. Put that into an SSH host entry. Julian's `~/.ssh/config` already includes `~/.ssh/config.d/*`, so create `~/.ssh/config.d/vastai`:
   ```
   Host arena
       HostName <ip>
       Port <port>
       User root
       IdentityFile ~/.ssh/vastai
   ```
   Test with `ssh arena nvidia-smi`. IP and port change with every new instance, so edit these two lines each time.
7. VS Code: Command Palette → "Remote-SSH: Connect to Host…" → `arena`. Install the Python and Jupyter extensions on the remote when asked.
8. In the remote VS Code terminal:
   ```bash
   cd ~
   git clone https://github.com/julxi/ARENA_2026.git ARENA_materials
   bash ARENA_materials/install.sh --platform vastai
   ```
   The fork is public (HTTP 200 without login, 26-10-27), so cloning needs no credentials. `--no-llm-context` skips an extra clone of ARENA's LLM-context repo; including it is harmless. VastAI drops you into tmux by default; `touch ~/.no_auto_tmux` turns that off.
9. Open `/root` (home) as the VS Code folder: `install.sh` writes `~/.vscode/settings.json` pointing the interpreter at `arena-env`. For `# %%` cells, also pick the `arena-env` kernel in the interactive window (same interpreter-vs-kernel split as in the setup topic).
10. Verify: `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name())"` should print `True` and the GPU name.

**Getting work back**
11. Set `git config --global user.name/user.email` on the VM, then commit and push from there; pull on the laptop. VS Code Remote-SSH normally passes HTTPS GitHub authentication through to the laptop's VS Code. If it doesn't, add `ForwardAgent yes` to the host entry and use an SSH remote. [assumed: not tested with Julian's setup]

## Stop vs destroy (cost and data)

- **Stop**: data kept, but storage is still billed. The GPU is released and someone else may rent it. On restart the instance sits in "SCHEDULING" waiting for its GPU; VastAI says that if this lasts > 30 s, someone else probably has it. VastAI itself recommends not stopping unless you accept a possibly long wait. [verified: VastAI troubleshooting docs, 26-10-27]
- **Destroy**: data gone, billing ends.
- Persistent volumes exist but are tied to one physical machine, so they don't solve the "GPU got taken" problem. [verified: VastAI storage docs, 26-10-27]

**Recommendation:** treat instances as disposable. Push, then destroy at the end of a session, and redo steps 3–10 next time. Steps 8–10 are mostly waiting for install.sh. Stopping overnight is fine if you accept the occasional restart failure. [concluded: everything worth keeping is in git, and the environment is reproducible from install.sh]

Side note: `~/.ssh/config` already has entries for RunPod and SkyPilot, so Julian may have used those before. Both would work for ARENA as well.

Sources: https://docs.vast.ai/instances/sshscp , https://docs.vast.ai/instances/storage/types , https://docs.vast.ai/guides/reference/troubleshooting

---

C: (transcribed from chat) I want to automate the process. I want a script that automates the renting and uploading of the current state. If possible this script should set up as much as possible:uv sync or whatever needs to be done for this project, installing necessary packeges for vs-code (don't know ruff and other stuff). For your inspiration I have copied two files to this repo @run_vast.py  and @vast_config.yaml . Can you ask me some questions in the log so I can see what you are building?

---

26-10-27, Claude Opus 5.5 — *automation script: what I found and questions*

I have read `run_vast.py` and `vast_config.yaml` (copied from Julian's SPD project at the repo root; they import the `spd` package, so they don't run here as-is), `install_uv.sh`, `install.sh`, `requirements.txt`, `.gitignore`, `docs/CODING.md`, Julian's VS Code user settings and `~/.ssh/config.d/`. I haven't written any code yet.

## What I found

- **Local tools are ready.** `vastai` CLI 1.2.0, `uv`, `rsync` are installed, and a VastAI API key is in `~/.config/vastai/vast_api_key`. No instances are currently rented. [verified: `vastai show instances`, 26-10-27]
- **This project's "uv sync" is `install_uv.sh`.** ARENA isn't a uv project, so there is no `uv sync`. `install_uv.sh --platform vastai` is the equivalent: it installs uv, creates `.venv` (Python 3.13), runs `uv pip install -r requirements.txt`, registers the `arena-env` Jupyter kernel, and works whatever the folder is called. Your local `.venv` was made the same way, so remote and local would match. This also corrects step 8 of my walkthrough above: `install_uv.sh` is better than `install.sh` (conda) and doesn't need the `ARENA_materials` folder trick. [verified: read both scripts]  
C: I'd like to not install a separate uv instance. I want to use an image that already has uv. So can we just use the parts of the install script that we need?
- **The install is heavy.** `requirements.txt` covers all chapters: torch (CUDA 13), jax[cuda13], mujoco, brax, envpool, transformer_lens, sae-lens, etc. That is several GB, so a host with a slow route to PyPI will stall here, as you saw in SPD.
- **SSH key: reuse `~/.ssh/id_rsa`.** Your SPD script already rents VastAI machines with it, so my earlier advice to make a new `~/.ssh/vastai` key was unnecessary.
- **The alias names `arena` and `vastai` are both taken** in `~/.ssh/config.d/`: `arena.conf` points at `91.108.80.253:30153` (an older machine of yours?), and `vastai.conf` was written by spd-vast on 26-10-26.
- **`vastai show instances` now prints a deprecation notice** ("use `show instances-v1`"). That notice breaks JSON parsing of `--raw` output for that command. The new script must avoid deprecated commands or handle the notice. [verified: 26-10-27]
- **Upload = rsync of the working tree**, as in `run_vast.py`: uncommitted changes and `.git` included (so you can commit/push from the machine), everything gitignored excluded (`.venv`, `*data`, `models/`, `.env`, any `private/` folder). That is about 70 MB plus 193 MB of `.git`.

## My plan, in brief (subject to your answers)

A standalone script `vast/arena_vast.py` with a YAML config next to it, depending only on the standard library and pyyaml (already in `requirements.txt`), run with `.venv/bin/python`. It reuses the parts of `run_vast.py` that encode lessons you paid for: offer search with filters, walking down offers that are already taken, host blacklist, excluded countries, `attach ssh` + waiting for ssh, the install time budget, and checking that destroy actually worked. Subcommands:

- `offers`: list matching offers, rent nothing
- `up`: rent → wait for ssh → write ssh config → rsync repo → run `install_uv.sh` (with time budget) → check `torch.cuda.is_available()` → print how to connect
- `push`: rsync local → remote again (local edits)
- `pull`: rsync remote → local (bring work back)
- `down`: pull, then destroy; refuses to destroy if the pull failed
- `status`: what is rented, for how long, at what price

## Questions

Answer below each with a `C:` line. If you skip one, I'll go with my recommendation.

**Q1 — Where do you edit while a machine is up?**
(a) On the machine: VS Code connects via Remote-SSH, you edit and run cells there, and `pull` brings files back at the end. This is what ARENA assumes, and the interactive window and kernel work natively. Claude Code would also run on the remote, so you'd log in there and it edits the remote copy of `convos/`.
(b) Locally: you edit here, `push` after each change, and run on the remote. Clumsy for `# %%` cells.
Recommendation: (a). Rule that follows: don't edit the same files locally while a machine is up, because `pull` would overwrite them.
C: I would completely work on the remote machine

**Q2 — How should work come back?**
(a) `pull` (rsync remote → local, no deletions), then you commit locally as usual. (b) commit + push to GitHub from the machine, `git pull` locally. (c) both available.
Recommendation: (a) as the default, done automatically by `down`. (b) remains possible by hand because `.git` is uploaded.
C: exactly, both

**Q3 — Safety net against a forgotten machine?** A rented machine bills until destroyed.
(a) None: `down` and `status` only.
(b) A watchdog on the machine that **stops** it (data kept, only storage billed) after N hours with no SSH/VS Code connection and an idle GPU. I'd need to check how a container can stop itself (I believe VastAI puts an instance-scoped API key into the container [assumed, unchecked]).
(c) Same, but destroy instead of stop. That's cheaper, but unpulled work is lost.
Recommendation: (b) with N = 2 hours. If yes, what N?
C: no safety net

**Q4 — Install all of `requirements.txt`?** The alternative, a per-chapter subset, would be a list that I maintain and that drifts from upstream.
Recommendation: install everything via `install_uv.sh`, with a time budget after which the host is rejected and blacklisted. SPD used 10 min; this install may be bigger, so I'd start at 15 min. OK?

**Q5 — VS Code extensions on the remote.** VS Code has a user setting, `remote.SSH.defaultExtensions`, that installs listed extensions on every SSH host automatically, so no script is needed. Proposed list:
- `ms-python.python` + `ms-python.vscode-pylance` (Python support)
- `ms-toolsai.jupyter` (the interactive window for `# %%` cells)
- `charliermarsh.ruff`: Ruff is a fast Python formatter + linter. It's already your local default formatter for Python (`"editor.defaultFormatter": "charliermarsh.ruff"`), and ARENA's `pyproject.toml` holds ruff settings.
- `anthropic.claude-code`? Only if Q1 = (a) and you want Claude on the remote.
That file is your user `settings.json`, outside this repo. May I add the setting there? Any extensions to add or remove?
Separately, the script would write `.vscode/settings.json` into the remote repo (gitignored) pointing at its `.venv`, so the right interpreter is picked when you open the folder.
C: everything except claude-code

**Q6 — Which machines?** Required: CUDA ≥ 13.0 on the host (torch is built for CUDA 13). Questions:
- GPU: ARENA's baseline is an RTX 3060 / A4000 class card; a 3090/4090 is faster and has 24 GB. Allow a list (e.g. RTX_3090, RTX_4090, RTX_A5000, RTX_A4000) and rent the best price/performance among them, or a single GPU type as in SPD?
- Max price in $/hour?
- Disk: I suggest 80 GB (venv of several GB plus Hugging Face models from chapter 1 on).
- Carry over from SPD: exclude CN (Hugging Face is unreachable there, and chapter 1 needs it), reliability ≥ 0.95, `datacenter_only: false`? Your SPD config has a comment pointing to datacenter lessons in that project.
C: a config per card. For the beginning the simplest cards is all I need. A generous max price per hour and a warning for quite high price (the values depend on the card type). You can carry over from spd the no CN, relibility and not necessarily datacenters

**Q7 — Secrets.** No `.env` exists here yet. Later chapters need keys: WandB (from 0.3), a Hugging Face token (gated models), OpenAI/Anthropic (chapter 3). `.env` is gitignored, so rsync won't upload it. Should `up`/`push` copy `.env` to the machine (permissions 600) if it exists? Recommendation: yes.  
C: yes

**Q8 — SSH alias.** Which name for the generated host entry? Options: overwrite `arena.conf` and keep the name `arena`, if that old machine is gone; or a new name like `arena-vast`. Recommendation: `arena`, if `91.108.80.253` is obsolete.  
C: use `arena`.

**Q9 — Open VS Code automatically?** At the end of `up`, the script could run `code --remote ssh-remote+arena /root/ARENA_2026`, which opens a VS Code window connected to the machine in the repo folder. Recommendation: yes.  
C: ooh, yes

**Q10 — Housekeeping.** May I put the script in a new folder `vast/` at the repo root? Upstream ARENA has no such folder, so no merge conflicts. And should I delete the copied `run_vast.py` and `vast_config.yaml` afterwards (they are untracked and don't run here), or keep them as reference?
C: yes

---

26-10-27, Claude Opus 5.5 — *automation script implemented (untested on a real rental)*

I have read Julian's answers to Q1–Q10 above, `run_vast.py`/`vast_config.yaml`, `install_uv.sh`, `docs/CODING.md`, and checked the vastai CLI, Docker Hub and current offers live.

## How I read the answers

- Q1 work entirely on the remote; Q2 both ways of getting work back; Q3 no safety net; Q5 the four extensions, no claude-code; Q6 one config per card, start with the simplest card, generous max price plus a warning price; Q7 copy `.env`; Q8 alias `arena`; Q9 open VS Code; Q10 folder `vast/` and delete the copied SPD files.
- **Q4 had no answer**, so I used my recommendation: install all of `requirements.txt`, 15-minute budget. [assumed]
- **The `C:` on `install_uv.sh`** (no separate uv, use an image that has uv, only the needed parts of the script) is implemented as `vast/remote_setup.sh` (below).
- Q10 said "yes" to an either/or question ("delete … or keep?"). I read it as delete. The deleted files are byte-identical to `~/projects/targeted-parameter-decomposition/spd/scripts/run_vast.py` and `vast_config.yaml`, so nothing is lost. [verified: `cmp`, 26-10-27]

## What exists now

- `vast/arena_vast.py`: subcommands `offers`, `up`, `status`, `push`, `pull`, `down`. Run with `.venv/bin/python vast/arena_vast.py <cmd>`; `--config <name>` before the subcommand picks `vast/<name>.yaml`.
  - `up`: refuses if an `arena`-labelled instance already exists → search → rent the first available offer (asks first if it costs more than `warn_price`) → wait for running → attach ssh key → write `~/.ssh/config.d/arena.conf` (this overwrote the old `arena` entry for 91.108.80.253, per Q8) → wait for ssh → upload the working tree → copy `.env` (mode 600) → copy local git `user.name`/`user.email` to the remote → run `remote_setup.sh` under a 15 min `timeout` → check `torch.cuda.is_available()` → `code --remote ssh-remote+arena /root/ARENA_2026` (skip with `up --no-code`). On a host failure (dead instance, ssh never works, install too slow, torch can't see the GPU) the host is added to `vast/blacklist.yaml` and the instance destroyed; as in SPD there is no automatic retry. On any other error the instance stays up and the script prints the destroy command.
  - `status`: every instance on the account with its cost so far; instances from other projects are marked "not ours".
  - `pull` / `push`: rsync in either direction, **never with deletions**. Each first does a dry run and lists new files and files that would be OVERWRITTEN. `push` asks before overwriting remote files, `pull` asks before overwriting local ones.
  - `down`: pull preview → one confirmation ("pull and then DESTROY?") → pull → destroy (destroy only after the pull has succeeded) → delete `~/.ssh/config.d/arena.conf`.
  - Only instances labelled `arena` are ever touched.
- `vast/remote_setup.sh`: the parts of `install_uv.sh` the machine needs: venv (Python 3.13) + `uv pip install -r requirements.txt`, the same install-complete marker logic, `arena-env` Jupyter kernel, venv activation in `.bashrc`, `~/.no_auto_tmux`, and `.vscode/settings.json` (interpreter + `extraPaths`) **in the repo folder**, because VS Code opens the repo, not `/root`. Not included: installing uv and the apt install of git/curl. The script fails loudly if the image lacks uv or git.
- `vast/rtx_3060.yaml`: image `vastai/base-image:cuda-13.0.3-auto` (the CUDA 13 counterpart of SPD's `cuda-12.8.1-auto`, which ships uv), min CUDA 13.0, `max_price` 0.30, `warn_price` 0.15, disk 80 GB, reliability > 0.95, no CN, no datacenter requirement, `inet_down` ≥ 100, sort by performance per dollar. Adding a card = copying this file.
- `vast/blacklist.yaml`: empty, same format as SPD's.
- Julian's VS Code user settings (`~/.config/Code/User/settings.json`, outside the repo): added `remote.SSH.defaultExtensions` = python, pylance, jupyter, ruff. Backup of the previous file: `/tmp/claude-1000/-home-jx-projects-ARENA-2026/bcc6ad61-4f1b-4c17-9934-e39825b10e50/scratchpad/vscode_settings_backup.json` (temporary; it disappears with the session).

## Design decisions not covered by the questions

- **Which files are uploaded: decided by git, not by rsync's `.gitignore` filter (which SPD used).** The file list comes from `git ls-files --cached --others --exclude-standard` (tracked + untracked-not-ignored, i.e. what `git status` covers) plus `.git`. Reason: rsync doesn't read gitignore negations the way git does. ARENA's `.gitignore` has `!chapter1_…/part32_function_vectors_and_model_steering/data`; with SPD's filter, all 6 tracked files in it are skipped, while the git list includes them. [verified: rsync dry run vs `git ls-files`, 26-10-27] For `pull` the list is generated by git on the remote.
- **No `--delete` in either direction.** Since the work happens on the remote, a push with deletions would wipe files created there. Consequence: files deleted on one side are not deleted on the other.
- **`.git` is synced both ways**, so commits made on the remote come back with `pull` and local git stays consistent (otherwise a later `git pull` from GitHub would trip over the pulled-in working-tree changes). This relies on the Q1 rule: while a machine is up, don't edit or commit locally.
- **The ssh alias is rewritten by every subcommand** from `vastai ssh-url`, so it stays correct if the instance's address changes.
- The `vastai show instances-v1 --raw` output includes each container's env vars, e.g. the SPD instance's WandB key, so the script never prints raw instance dicts.

## Verification so far

- `offers` and `status` run against the live API: 15 RTX 3060 offers at $0.069–0.121/hr; `status` lists the SPD instance as "not ours". [verified: 26-10-27]
- Sync logic, tested with a local directory standing in for the remote (ssh/rsync target monkeypatched): the remote file list equals the local one after a push (595 entries); after a "remote" edit, a new untracked file and a gitignored `models/` file, the pull preview shows 1 new, 1 OVERWRITE (`MEMORY_INDEX.md`), and the ignored file is left out; the push preview flags the same file as an overwrite on the remote and deletes nothing. [verified: local simulation 26-10-27]
- `ruff check` / `ruff format` clean; `bash -n remote_setup.sh` OK.
- **Not tested:** a real `up`/`down` cycle, i.e. renting, the install inside the image, the GPU check, VS Code opening, git push from the remote. [assumed to work: the rental code is SPD's, which has been used, but `remote_setup.sh`, the CUDA 13 image and the sync are new]

## Open

- Run a first real `up` → work → `down` cycle (≈ 20 min, a few cents on a 3060).
- Note: at the time of writing, the SPD instance 58003044 (RTX 4090, $0.662/hr, label `spd-provision-s-2c37c396`) was still running. `arena_vast.py` leaves it alone.
