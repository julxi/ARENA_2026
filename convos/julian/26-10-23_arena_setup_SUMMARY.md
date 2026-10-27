# SUMMARY: ARENA setup

**Last updated:** 26-10-27 (GPU question moved to its own topic)

Questions about setting up and running the ARENA environment: venv, packages, VS Code, imports. Julian asked for all setup questions to go in this topic. Exercise content belongs in separate topics. Julian is starting with `chapter0_fundamentals/exercises/part0_prereqs/` and writes solutions in their own file `my_0.0.py` there.

**Environment facts**
- The venv is `.venv/` at the repo root (Python 3.13), created by ARENA's `install_uv.sh`. Agents' shells don't have it activated, so use `.venv/bin/python`. [verified: 26-10-23]
- ARENA is **not a uv project**. `pyproject.toml` holds only ruff settings. Dependencies live in `requirements.txt` and are installed with `uv pip install`. Because of this, `uv add <pkg>` fails ("missing a `[project]` table"). Use `uv pip install <pkg>` instead. Don't add a `[project]` table: `pyproject.toml` belongs to upstream, so editing it would cause merge conflicts on upstream pulls. [verified: error reproduced 26-10-23] [concluded: advice on not editing]
- `ipykernel` 7.4.0 is installed, and a Jupyter kernel named `arena-env` is registered. [verified: 26-10-23]

**Import error (fixed).** `python my_0.0.py` failed with `ModuleNotFoundError: No module named 'part0_prereqs'`. The import needs `chapter0_fundamentals/exercises/` on `sys.path`, and Julian's copy of ARENA's setup block imported before adding that folder (and never added it). The fix puts the path setup and `sys.path.append(str(exercises_dir))` before the imports, matching `solutions.py`. [verified: exit code 0 from `part0_prereqs/`, 26-10-23]

**Running the exercises**
- The setup code finds the repo root by searching the *parents* of the current working directory. Run from inside the exercise folder; from the repo root it raises `StopIteration`. [concluded: from reading the code; not run]
- ARENA intends `# %%` cells to run in VS Code's interactive window (or the notebooks). VS Code chooses the interactive window's **kernel** separately from the **interpreter**, so selecting `.venv` as interpreter isn't enough. Julian got "Running cells with 'Python 3.14.3' requires the ipykernel package": the kernel was a uv-downloaded Python 3.14 (`~/.local/share/uv/python/`), not the venv. Fix: Change Kernel → `.venv (3.13.12)` or `arena-env`. Don't click Install, because that Python lacks ARENA's packages. [assumed: fix not yet confirmed by Julian]

**GPU access** has its own topic: `convos/julian/26-10-27_vastai_gpu_setup_SUMMARY.md`. This laptop has no NVIDIA GPU, and Julian chose VastAI. [verified: no `nvidia-smi`, 26-10-27]

- See also: `convos/julian/26-10-27_vastai_gpu_setup_SUMMARY.md` — renting and setting up a VastAI GPU machine for the exercises.
