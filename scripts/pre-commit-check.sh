#!/usr/bin/env bash
# Pre-commit checks (CONTRIBUTING.md §3) — run before every git commit.
# Fails fast on the first failing check.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Repo: boundary & design-token checks"
node scripts/check-boundaries.mjs

echo "==> Backend: lint (ruff)"
( cd backend && uv run ruff check . )

echo "==> Backend: tests (pytest)"
( cd backend && uv run pytest -q )

echo "==> Backend: import check"
( cd backend && uv run python -c "from app.main import app" )

echo "==> Frontend: typecheck (tsc)"
( cd frontend && pnpm run typecheck )

echo "==> Frontend: lint (eslint)"
( cd frontend && pnpm run lint )

echo "==> Frontend: tests (vitest)"
( cd frontend && pnpm run test )

echo "==> Frontend: build (vite)"
( cd frontend && pnpm run build )

echo ""
echo "All pre-commit checks passed."
