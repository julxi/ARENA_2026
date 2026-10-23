Set up the epistemic memory system for this repo. You'll need to move some folders out of the `EpistemicMemory-main` folder. One problem is the readme. Maybe it's best to merge the two in some way. Ask me about how to merge them for this setup

---

26-10-23, Claude Opus 5.5 — *setup interview and installation*

I have read the template's README (setup checklist), CLAUDE.md, docs/HOW_TO_USE.md, docs/README_SKELETON.md, FEEDBACK.md, FUTURE_WORK.md and .gitignore, plus ARENA's README.md and .gitignore and the git remotes.

**Situation.** This repo is a fork of ARENA_materials (`origin` = julxi/ARENA_2026, `upstream` = ARENA-education/ARENA_materials). The template's setup replaces `README.md` with a working index, but ARENA's `README.md` is owned by upstream. `git log --since=2026-01-01 -- README.md` lists 10 commits that touched it, so editing it would cause regular merge conflicts on upstream pulls.

**Interview.** I asked four multiple-choice questions in chat. The answers are transcribed verbatim, each under the question it answers:

Q: How should the ARENA README and the Epistemic Memory working README be combined? (Options: separate index file / prepend to README / replace README and keep ARENA's as ARENA_README.md.)
    C: (transcribed from chat) Separate index file (Recommended)

Q: Git workflow: should agents never commit or push, so you review every change in the git diff first (the template's default)?
    C: (transcribed from chat) Agents never commit (Recommended)

Q: Do you want the gitignored private-records folder (convos/{you}/private/) set up now?
    C: (transcribed from chat) No, skip for now

Q: Who is on the team, and what is this project? My guess: just you (Julian, folder convos/julian/), working through the ARENA 2026 curriculum in this fork.
    C: (transcribed from chat) Correct as guessed

**Decisions recorded:**
- [decided] The memory index lives in `MEMORY_INDEX.md` at the repo root, and ARENA's `README.md` stays unchanged. Every place in CLAUDE.md, docs/HOW_TO_USE.md, docs/procedures/sync.md and docs/procedures/multi_agent_debate.md that told agents to read or update "the README" now points to `MEMORY_INDEX.md`. CLAUDE.md also gained a paragraph saying that this repo is an ARENA fork and that `README.md` is upstream's file and should not be edited.
- [decided] Agents never commit or push. Julian reviews the diff and commits. The template's git rules are kept as written.
- [decided] No private-records folder for now. The `.gitignore` rules for it are in place, so creating `convos/julian/private/` later is enough.
- [decided] Team of one: Julian Bitterlich, folder `convos/julian/`. Project: a personal workspace for the ARENA 2026 curriculum.

**What I changed:**
- Moved `CLAUDE.md`, `FEEDBACK.md`, `FUTURE_WORK.md` and `docs/` from `EpistemicMemory-main/` to the repo root. The template's MIT `LICENSE` went to `docs/EPISTEMIC_MEMORY_LICENSE` rather than the root, so it is not mistaken for the license of the ARENA material.
- Removed the template-only content, as the setup checklist says: the template note in CLAUDE.md, the example entries in FEEDBACK.md and FUTURE_WORK.md, `CORE.md`, the demo user `convos/jamie/`, the template's landing README, and `docs/README_SKELETON.md` (used to write MEMORY_INDEX.md). After that I deleted the empty `EpistemicMemory-main/` folder. I left the original archive `EpistemicMemory-main.zip` in place.
- Merged `.gitignore`. ARENA's file already covered `.env`, `.venv` and `__pycache__`, so I appended only the private-folder and `scratch/` rules, plus `!convos/**/*.md`. [verified: `git check-ignore` on 26-10-23] Without that re-include, ARENA's broad patterns would ignore topic files: `*master*.md`, for example, would silently ignore a file like `26-10-23_master_files_LOG.md`. With it, such files are tracked, and both a real `convos/julian/private/` folder and a symlink in its place are still ignored.
