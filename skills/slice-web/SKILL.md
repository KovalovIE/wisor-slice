---
name: slice-web
description: >
  Scaffold the screen half of a CRUD vertical slice in wisor's apps/web — types mirroring the backend DTO,
  RTK Query endpoints with cache tags, a list + create/edit/delete page with hooks and helpers, and
  msw-backed tests — by mirroring the categories page. Use after slice-api, when the REST endpoints exist.
argument-hint: "<Entity> in <bc>: route /<entities>; list shows <fields>; form edits <fields>"
disable-model-invocation: true
---

# slice-web — screen half of a CRUD slice

Arguments: `$ARGUMENTS`

The reference implementation is **`apps/web/src/features/categorization/`** (categories page). Mirror its
structure and conventions (`CLAUDE.md` «apps/web»), replacing the entity, BC and route. Read each reference
file before writing its counterpart.

## Files

| File (new entity) | Reference |
|---|---|
| `features/<bc>/types.ts` — mirror of the backend DTO. **First line names the DTO file** (`Mirrors … dto/<entity>.dto.ts`): the `docs-sync` hook uses it to catch drift | `features/categorization/types.ts` |
| `features/<bc>/api.ts` — `baseApi.enhanceEndpoints({ addTagTypes: ['<Entity>'] }).injectEndpoints(...)`: list/get/create/update/delete, `LIST` + per-id tags, mutations invalidate only on success | `features/categorization/api.ts` |
| `<entities>-page/index.tsx` — dumb component: no state, no computation | `categories-page/index.tsx` |
| `<entities>-page/hooks/use-<entities>-page.ts` — main hook: list, delete, composes the form hook | `hooks/use-categories-page.ts` |
| `<entities>-page/hooks/use-<entity>-form.ts` — form state, validation, submit; maps API 409 to a field error with `isApiError` (`shared/api/api-error.ts`) | `hooks/use-category-form.ts` |
| `<entities>-page/helpers.ts` — pure functions (row mapping, display formatting) | `categories-page/helpers.ts` |
| `<entities>-page/styles.module.css` | `categories-page/styles.module.css` |
| `<entities>-page/index.test.tsx` — msw: list renders, create sends minor units, validation errors, 409 shown next to the field, delete removes the row | `categories-page/index.test.tsx` |
| Route in `src/app/router.tsx` + a `Link` on the home page | same files |

## Rules learned in F1

- **Money:** reuse `src/shared/lib/money.ts` (UAH input ↔ minor units, formatting). Never re-implement it in
  a feature — in F1 it started as `hooks/budget.ts` and had to be moved.
- **Hooks folder holds hooks only** (`use-*.ts`, one per file). Pure functions go to `helpers.ts`; if a second
  feature needs one, to `src/shared/lib/`.
- **Data owned by another BC** (e.g. a category picker in the obligation form): a feature must not import
  another feature (`make lint` fails). Add a read-only endpoint for it in **your own** `api.ts` with a minimal
  type in your `types.ts` (e.g. `CategoryOption { id; name }`).
- **Size limits:** function ≤ 50 lines — split the form early (a small field component, a `change(field)`
  factory) instead of after lint fails.
- **Verify only through the toolchain:** `make test-web`, `make lint-web`. No throwaway probe scripts and no
  `console.log` probes inside tests — vitest hides the output, so they prove nothing. Assert with `expect`.

## Finish

1. `make format`, then `make lint-web` and `make test-web` — green.
2. Report files and checks. Ask the user to check the screen by hand: `make dev` → `http://localhost:5173/<route>`
   (create → edit → conflict error next to the field → delete).
3. Do not commit. Next step: `/wisor-slice:slice-ship`.
