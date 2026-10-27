# ARENA 2026 — Julian's workspace

Julian's personal fork of the [ARENA](https://github.com/ARENA-education/ARENA_materials) curriculum (the ML-for-AI-safety course: fundamentals, transformer interpretability, RL, LLM evals, alignment science), used to work through the exercises and keep notes and experiments alongside them. The curriculum itself is described in ARENA's [README.md](README.md). That file belongs to upstream and is left unchanged so that `git pull upstream main` merges cleanly, which is why this index is a separate file.

This project uses the [Epistemic Memory](https://github.com/FlorianDietz/EpistemicMemory) conventions: all project memory lives in LOG/SUMMARY file pairs under `convos/`, governed by [CLAUDE.md](CLAUDE.md). Human guide: [docs/HOW_TO_USE.md](docs/HOW_TO_USE.md). Open ideas and deferred items: [FUTURE_WORK.md](FUTURE_WORK.md). Workflow problems and lessons: [FEEDBACK.md](FEEDBACK.md).

## Team

A team of one, so agents don't need to work out who the current user is.

- Julian Bitterlich — `convos/julian/`

## Current status and goals

Epistemic Memory set up on 26-10-23. Work is starting on Chapter 0 (Fundamentals): the prerequisites exercises in `chapter0_fundamentals/exercises/part0_prereqs/`.

## Maintenance

Recurring tasks:

| Task | Last run | Due when | Notes |
|------|----------|----------|-------|
| Sync (LOG/SUMMARY drift) | — | After many LOG changes, or ~monthly | `!sync`; procedure: `docs/procedures/sync.md` |

## Conversation Index

All discussions live in `convos/{user}/`. **When starting a new topic, add a row here.** Read the SUMMARY first; open the LOG only if the SUMMARY is insufficient. Status cells describe current state only — rewrite them on update, don't append.

| Date | User | Topic | Status | SUMMARY | LOG |
|------|------|-------|--------|---------|-----|
| 26-10-23 | julian | Epistemic Memory setup for this ARENA fork | Done; waiting for Julian to review the diff | [SUMMARY](convos/julian/26-10-23_epistemic_memory_setup_SUMMARY.md) | [LOG](convos/julian/26-10-23_epistemic_memory_setup_LOG.md) |
| 26-10-23 | julian | ARENA setup: venv, packages, VS Code, imports (all setup questions go here) | Ongoing; import error fixed, ipykernel/`uv add` answered; GPU moved to its own topic | [SUMMARY](convos/julian/26-10-23_arena_setup_SUMMARY.md) | [LOG](convos/julian/26-10-23_arena_setup_LOG.md) |
| 26-10-27 | julian | Renting a VastAI GPU for the exercises | `vast/arena_vast.py` implemented (up/pull/down etc.); first real rental not yet tested | [SUMMARY](convos/julian/26-10-27_vastai_gpu_setup_SUMMARY.md) | [LOG](convos/julian/26-10-27_vastai_gpu_setup_LOG.md) |
