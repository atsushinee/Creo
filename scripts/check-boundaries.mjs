#!/usr/bin/env node
/**
 * Boundary & design-token checks (borrowed from OpenBitFun's check-scripts
 * culture: documentation rules must be machine-enforceable).
 *
 * Enforces:
 *   AGENTS.md §2  — layering boundaries (backend & frontend)
 *   DESIGN.md §2  — colors come from tokens; no raw hex in TS/TSX
 *
 * Zero dependencies: run with `node scripts/check-boundaries.mjs`.
 * Wired into scripts/pre-commit-check.sh.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(import.meta.url), "..", "..");
const violations = [];

function* walk(dir, skip = new Set(["node_modules", "dist", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".git", "coverage", "target"])) {
  for (const entry of readdirSync(dir)) {
    if (skip.has(entry)) continue;
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      yield* walk(full, skip);
    } else {
      yield full;
    }
  }
}

function checkLines(filePath, pattern, describe) {
  const lines = readFileSync(filePath, "utf8").split(/\r?\n/);
  lines.forEach((line, index) => {
    if (pattern.test(line)) {
      violations.push(
        `${relative(ROOT, filePath).replaceAll(sep, "/")}:${index + 1}  ${describe}: ${line.trim().slice(0, 120)}`,
      );
    }
  });
}

// --- AGENTS.md §2: backend layering -----------------------------------------

const FRAMEWORK_MODULES = /^\s*(?:from|import)\s+(?:deepagents|langchain|langgraph)\b/;

for (const file of walk(join(ROOT, "backend", "app"))) {
  if (!file.endsWith(".py")) continue;
  const rel = relative(ROOT, file).replaceAll(sep, "/");
  const inAgentLayer = rel.includes("/app/agent/");

  if (!inAgentLayer) {
    checkLines(
      file,
      FRAMEWORK_MODULES,
      "AGENTS.md §2: only backend/app/agent/** may import deepagents/langchain/langgraph",
    );
  }

  if (rel.includes("/app/api/")) {
    checkLines(
      file,
      /^\s*(?:from|import)\s+app\.agent\.(?:agent|model)\b/,
      "AGENTS.md §2: routes must not reach agent internals; consume AgentRuntime via deps",
    );
  }

  if (rel.includes("/app/services/")) {
    checkLines(
      file,
      /^\s*(?:from|import)\s+app\.agent\b/,
      "AGENTS.md §2: services must not depend on the agent layer",
    );
  }

  if (!rel.replaceAll("\\", "/").endsWith("app/services/kb_vector_store.py")) {
    checkLines(
      file,
      /^\s*(?:from|import)\s+pymilvus\b/,
      "AGENTS.md §2: only services/kb_vector_store.py may import pymilvus (ADR-0004)",
    );
  }
}

// --- AGENTS.md §2: frontend layering -----------------------------------------

for (const file of walk(join(ROOT, "frontend", "src"))) {
  if (!file.endsWith(".ts") && !file.endsWith(".tsx")) continue;
  const rel = relative(ROOT, file).replaceAll(sep, "/");

  if (rel.includes("/components/")) {
    checkLines(
      file,
      /from\s+["']@\/(?:services|lib\/sse)/,
      "AGENTS.md §2: components must go through hooks, not services/SSE directly",
    );
  }
  if (rel.includes("/stores/")) {
    checkLines(
      file,
      /from\s+["']@\/services/,
      "AGENTS.md §2: the store stays pure — no network access",
    );
  }
  if (rel.includes("/components/ui/")) {
    checkLines(
      file,
      /from\s+["']@(?!\/lib\/utils)/,
      "components/ui must stay generic: import only from @/lib/utils",
    );
  }
}

// --- DESIGN.md §2: no raw hex colors outside the token stylesheet -------------

const HEX_COLOR = /#[0-9a-fA-F]{3,8}\b/;

for (const file of walk(join(ROOT, "frontend", "src"))) {
  if (!file.endsWith(".ts") && !file.endsWith(".tsx")) continue;
  checkLines(file, HEX_COLOR, "DESIGN.md §2: colors must come from tokens (index.css), not literals");
}

// -----------------------------------------------------------------------------

if (violations.length > 0) {
  console.error(`✗ ${violations.length} boundary violation(s):\n`);
  for (const violation of violations) {
    console.error(`  ${violation}`);
  }
  process.exit(1);
}

console.log("Boundary & design-token checks passed.");
