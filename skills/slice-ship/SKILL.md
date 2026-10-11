---
name: slice-ship
description: >
  Final gate for a wisor vertical slice: format, lint, test (fix-and-rerun loop with a cap), sync docs and
  CHANGELOG, and propose the commit message — without committing. Use when a slice's code is done and the
  user wants to wrap it up.
argument-hint: "[short summary of the slice, e.g. 'Obligation CRUD + screen']"
disable-model-invocation: true
---

# slice-ship — wrap up a slice

Summary from the user (may be empty): `$ARGUMENTS`

## 1. Checks — in this order, from the repo root

1. `make format`
2. `make lint`
3. `make test` — needs Postgres. If the DB is down, tell the user to run `make db-up`; don't work around it.

If something is red: name the cause in one sentence, fix it, rerun **the failing check and everything after
it**. At most **3** fix rounds — then stop and report what is still failing and why; don't keep guessing.

## 2. Docs

Look at `git status` / `git diff --stat` and check the change against `CLAUDE.md`:
- a new convention or shared building block → a line in `CLAUDE.md`;
- an architectural decision (new dependency, new cross-cutting mechanism) → an ADR in `docs/adr/`;
- a changed backend DTO → its mirror `apps/web/src/features/*/types.ts` in the same change.

The `docs-sync` hook is the safety net for these; don't rely on it to do this step.

## 3. CHANGELOG

In `docs/CHANGELOG.md` → `## [Unreleased]` → `### Added`, add one entry for the slice (API + screen) if it is not
there yet. One or two lines, in the language of the existing entries.

## 4. Hand-off

1. Report: checks with results (`make lint`, `make test` with test counts), docs touched.
2. Propose the commit message in the repo's style (`Add <Entities> …`), and for capstone feature branches a
   body line naming the plugin commands that were used.
3. **Never** run `git add`, `git commit` or `git push` without the user's explicit "ok, go" for that action.
4. Remind the user to log the step: `/wisor-slice:log-step <what> | <metrics>`.
