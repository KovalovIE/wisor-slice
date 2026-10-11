# wisor-slice

A Claude Code plugin for [wisor](https://github.com/KovalovIE/wisor) — a personal finance tracker built as a
TypeScript monorepo (Express + Postgres API in Clean Architecture, React web app, feature-first).

## Purpose

Every new entity in wisor is the same vertical slice: a SQL migration, a domain entity, a repository port,
five use cases, a Postgres adapter, REST endpoints, unit and integration tests, and a React screen with RTK
Query — about 25 files across two apps. Doing the first one (Category) by hand took **14 prompts and 1 h 51 min**,
and more than half of that was the human pausing between layer-by-layer prompts, re-asking for doc syncs
(3 times) and watching Claude retry throwaway verification scripts (4 times).

This plugin turns that slice into three commands and adds two hooks that catch the mistakes that kept
recurring. Every rule in it is traced to a line in wisor's `LOG.md`.

## Install

From GitHub (the repo is its own marketplace):

```
/plugin marketplace add KovalovIE/wisor-slice
/plugin install wisor-slice@wisor-tools
```

For local development, from the wisor checkout:

```bash
claude --plugin-dir ../wisor-slice
# after editing the plugin: /reload-plugins
```

Requirements: `python3` (3.9+) on `PATH` for the hooks, and the wisor repo (`make`, Docker for Postgres).
The hooks are no-ops in any repo that doesn't look like wisor (`CLAUDE.md` + `apps/api` + `apps/web`).

## Commands

| Command | What it does | Example |
|---|---|---|
| `/wisor-slice:log-step` | Appends one timestamped line to `LOG.md` under F1/F2 (picked from the branch name) in the log's own format. Changes nothing else. | `/wisor-slice:log-step slice-api done \| prompt#2, hook: docs-sync R1` |

The three skills below are also invoked as slash commands (they set `disable-model-invocation`, so they run
only when you call them):

```
/wisor-slice:slice-api Obligation in budgeting: name text 1–100; amount money required; dayOfMonth int 1–31; categoryId → Category, nullable
/wisor-slice:slice-web Obligation in budgeting: route /obligations; list shows name, amount, day; form edits all fields
/wisor-slice:slice-ship Obligation CRUD + screen
```

## Skills

| Skill | Trigger | Does |
|---|---|---|
| `slice-api` | `/wisor-slice:slice-api <Entity> in <bc>: <fields>` — after the domain is clear | Asks once about what `CLAUDE.md` doesn't decide, then builds migration → domain → port → use cases → Postgres adapter → DTO/controller/routes → wiring → unit + integration tests, mirroring the Category slice. Ends green on `make lint-api` + `make test-api`. |
| `slice-web` | `/wisor-slice:slice-web <Entity> in <bc>: route …` — after `slice-api` | Builds `types.ts` (DTO mirror), RTK Query `api.ts` with cache tags, the page (dumb component + `hooks/` + `helpers.ts` + CSS module) and msw tests, mirroring the categories page; registers the route. Ends green on `make lint-web` + `make test-web`. |
| `slice-ship` | `/wisor-slice:slice-ship [summary]` — when the slice is done | `make format` → `make lint` → `make test` with at most 3 fix rounds, docs and CHANGELOG sync, commit message proposal. Never commits without an explicit "ok, go". |

The skills reference the live Category code as the pattern instead of shipping templates, so they don't drift
from the codebase.

## Hooks

| Hook | Event / matcher | Condition | Effect |
|---|---|---|---|
| `docs-sync` | `Stop` | Uncommitted changes contain: **R1** a new shared building block (`*/shared/`, a new file directly in `presentation/http/`, non-repository persistence code) and neither `CLAUDE.md` nor an ADR changed; **R2** a new file outside the documented slice structure (e.g. a non-hook file in `hooks/`) and `CLAUDE.md` unchanged; **R3** a modified backend `*.dto.ts` whose web mirror `features/*/types.ts` didn't change. | Returns `decision: "block"` with the list of problems, so Claude updates the docs before ending the turn. Blocks once per stop (`stop_hook_active`), so "no doc change needed" is still possible. |
| `probe-guard` | `PreToolUse`, `Bash` | **B1** `node`/`tsx`/`ts-node`/`bun`/`deno` running a `.js`/`.ts` file from `/tmp`, `$TMPDIR` or the session scratchpad; **B2** `tsc` given explicit `.ts` files. | Denies the call (`permissionDecision: "deny"`) and points Claude to a real test plus `make test-unit` / `make test-web`, or to the project typecheck. |

Every block is appended to `${CLAUDE_PLUGIN_DATA}/hook-events.log` (tab-separated: time, hook, decision,
details) — the evidence trail for the capstone log.

### Development

```bash
python3 -m unittest discover -s tests -v   # 20 tests: each rule fires on a violation and stays quiet on the documented structure
claude plugin validate .                   # manifest + marketplace
```

## License

MIT
