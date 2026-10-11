---
name: slice-api
description: >
  Scaffold the backend half of a CRUD vertical slice in the wisor monorepo — SQL migration, domain entity
  and errors, repository port, use cases, Postgres adapter, REST endpoints, unit and integration tests —
  by mirroring the Category slice. Use when adding a new entity to apps/api (e.g. "add Obligation CRUD").
argument-hint: "<Entity> in <bc>: <field: type, constraints>; … [references: <other BC entity>]"
disable-model-invocation: true
---

# slice-api — backend half of a CRUD slice

Arguments: `$ARGUMENTS`

The reference implementation is **Category in BC `categorization`**. Mirror its structure, naming, contracts
and test style, replacing `category`/`categories`/`categorization` with the new entity and BC. Read each
reference file before writing its counterpart — copy the shape, not the content.

## Step 0 — clarify once, only what is not already decided

Already decided in `CLAUDE.md` — do **not** ask about these: PATCH semantics, invalid uuid → 404,
`created_at`/`updated_at`, error mapping (`DomainError.kind`, `HttpError`), money in minor units.

Ask in **one** message, only if the arguments leave it open:
- a field's constraints (length, range, required vs nullable), uniqueness;
- for a reference to another BC: what happens when the referenced row is deleted (`ON DELETE SET NULL` /
  `RESTRICT`), and whether the API must reject a non-existent referenced id (400) or accept it.

If nothing is open, say so in one line and continue.

## Step 1 — files, in this order

| # | File (new entity) | Reference (Category) |
|---|---|---|
| 1 | `apps/api/migrations/<ts>_create-<entities>.sql` via `make migration name=create-<entities>` | `migrations/*_create-categories.sql` |
| 2 | `src/domain/<bc>/<entity>.entity.ts` + `invalid-<entity>.error.ts`, `<entity>-not-found.error.ts`, (`<entity>-<field>-taken.error.ts` if unique) | `src/domain/categorization/*` |
| 3 | `src/application/<bc>/ports/<entity>-repository.port.ts` | `…/ports/category-repository.port.ts` |
| 4 | `src/application/<bc>/{create,list,get,update,delete}-<entity>.use-case.ts` | `src/application/categorization/*.use-case.ts` |
| 5 | `src/infrastructure/persistence/pg-<entity>.repository.ts` | `pg-category.repository.ts` |
| 6 | `src/presentation/http/dto/<entity>.dto.ts`, `controllers/<entity>.controller.ts`, `routes/<entity>.routes.ts` | `category.*` |
| 7 | Register: `presentation/http/app.ts` (`AppDeps` + router), `src/main.ts`, `test/integration/helpers/create-test-app.ts` — keep the last two identical in wiring | same files |
| 8 | Unit tests mirroring `src/`: entity, each use case with `test/unit/fakes/in-memory-<entity>.repository.ts` | `test/unit/**/category*`, `fakes/in-memory-category.repository.ts` |
| 9 | `test/integration/<entities>.test.ts`: full CRUD over HTTP on the real DB, `resetDb` in `beforeEach`, incl. 400 / 404 (unknown and malformed id) / 409 / 401 | `test/integration/categories.test.ts` |

Run `make migrate` right after step 1.

## Rules learned in F1 (each one cost a retry there)

- **Money:** reuse `domain/shared/money.value-object.ts`, `InvalidMoney` and `application/shared/money-input.ts`.
  Use cases build `Money` from `MoneyInput`; presentation only type-imports domain. DB columns:
  `<x>_minor bigint` + `<x>_currency char(3)` with a CHECK that both are null or both set; the adapter
  converts bigint with `Number.isSafeInteger` and throws a plain `Error` (→ 500) if it isn't.
- **Uniqueness:** unique index on the normalized column; the adapter maps `23505` to the conflict error
  **only** for that constraint name.
- **Update:** `prepareChanges` validates; the adapter builds `SET` from the given fields only, plus
  `updated_at = now()`, with `UPDATE … RETURNING` — no read-then-write.
- **Cross-BC reference** (e.g. `Obligation.categoryId`): never import `domain/<other-bc>` from
  `application/<bc>` (dependency-cruiser: `application-no-foreign-domain`). Declare a port in your BC
  (e.g. `application/<bc>/ports/category-lookup.port.ts` with `exists(id)`), implement it in
  `infrastructure/` by wrapping the other BC's use case or repository, and wire it in `main.ts` and
  `create-test-app.ts`.
- **Size limits** (ESLint errors): file ≤ 200 lines, function ≤ 50, ≤ 4 params, complexity ≤ 10. Design for
  them up front — command objects for use cases, small mapping helpers in the adapter.
- **Verify only through the project's toolchain:** `make migrate`, `make test-unit`, `make test-api`,
  `make lint-api`. No throwaway scripts in `/tmp` or the scratchpad and no `tsc` on single files — in F1
  they failed on module resolution 4 times and proved nothing (the `probe-guard` hook now blocks them).
  To check a behaviour, write it as a test; it stays as a regression check.
- **New shared building block** (anything in `*/shared/`, a new file directly in `presentation/http/`):
  add a line to `CLAUDE.md` in the same step. The `docs-sync` hook stops the turn otherwise.

## Finish

1. `make format`, then `make lint-api` and `make test-api` — all green.
2. Report: files created/changed (grouped by layer), checks run with results, decisions taken in step 0.
3. Do not commit. Next step: `/wisor-slice:slice-web`.
