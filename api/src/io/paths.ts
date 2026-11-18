// Repository paths for local runs (resolved from this file, so commands work from any directory).
// Last edited: 2026-11-17: first version.

import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));      // api/dist/src/io
export const REPO_ROOT = resolve(HERE, "../../../..");
export const GRAPH_JSON = resolve(REPO_ROOT, "build/graph.json");
export const QUESTIONS_CSV = resolve(REPO_ROOT, "data/eval_questions.csv");
export const EVAL_DIR = resolve(REPO_ROOT, "build/eval");
