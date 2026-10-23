# SUMMARY: Epistemic Memory setup

**Last updated:** 26-10-23 (setup done; waiting for Julian to review the diff)

The Epistemic Memory template is installed in this ARENA fork. The decisions below were ratified by Julian in chat; their verbatim transcriptions are in the LOG.

- [decided] **Index file:** the working index (team, status, conversation index) is `MEMORY_INDEX.md`, not `README.md`. ARENA's `README.md` belongs to upstream (ARENA-education/ARENA_materials) and stays unchanged, so upstream pulls don't conflict. CLAUDE.md and the docs point to `MEMORY_INDEX.md`.
- [decided] **Git:** agents never commit or push; Julian reviews the diff and commits.
- [decided] **Private records:** not set up. The `.gitignore` rules exist, so creating `convos/julian/private/` later is enough.
- [decided] **Team:** a team of one, Julian Bitterlich, in `convos/julian/`.

Notes for later agents:
- `.gitignore` re-includes `convos/**/*.md`. Without that, ARENA's broad patterns (e.g. `*master*.md`) would silently ignore topic files with those words in their names. [verified: `git check-ignore`, 26-10-23]
- The template's MIT license is kept at `docs/EPISTEMIC_MEMORY_LICENSE`.
