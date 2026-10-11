# Changelog

## [0.1.1] - 2026-10-11

### Fixed

- `probe-guard` missed every real probe from wisor's F1 (0 of 8): the scratch path was in a variable
  (`S=… && npx tsx $S/x.ts`) and `tsc` ran on `.mts` files. Variables assigned in the same command are now
  expanded, and B2 accepts `.mts`/`.cts`. B2 is checked before B1, so `tsc --types node …` gets the tsc reason.
- `docs-sync` went silent for the whole feature once `CLAUDE.md` had any uncommitted edit. R1/R2 now accept a
  file as documented only if text added to the docs names that file.

### Added

- Regression tests replaying the verbatim F1 events (`tests/fixtures/f1_probe_commands.json`, F1 doc-sync moments).
- README: measured catch rate on F1 and known limitations.

## [0.1.0] - 2026-10-11

- First release: `slice-api`, `slice-web`, `slice-ship` skills, `log-step` command, `docs-sync` and `probe-guard` hooks.
