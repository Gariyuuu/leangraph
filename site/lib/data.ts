import fs from "node:fs";
import path from "node:path";
import type { RetrievalSummary, Summary, TheoremDetail, TheoremRow } from "./types";

// Files are written by `python -m leangraph.export_site`; the site never computes a result.
const DATA_DIR = path.join(process.cwd(), "data");

function readOptional<T>(rel: string): T | null {
  const p = path.join(DATA_DIR, rel);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, "utf-8").replace(/:\s*NaN/g, ": null")) as T;
}

function readText(rel: string): string | null {
  const p = path.join(DATA_DIR, rel);
  return fs.existsSync(p) ? fs.readFileSync(p, "utf-8") : null;
}

export const getSummary = () => readOptional<Summary>("summary.json");
export const getTheorems = () => readOptional<TheoremRow[]>("theorems.json") ?? [];
export const getTheorem = (id: string) => readOptional<TheoremDetail>(path.join("theorem", `${id}.json`));
export const getRetrieval = () => readOptional<RetrievalSummary>("retrieval.json");
export const getErrorExamples = () =>
  readOptional<Record<string, { task_id: string; config: string; proof: string; output: string }[]>>("error_examples.json") ?? {};
export const getTasksSummary = () => readOptional<Record<string, unknown>>("tasks_summary.json");
export const getEnvironment = () => readText("environment.md");
export const getPaper = () => readText("paper.md");

export type RunStatus = {
  configs: { config: string; done: number; total: number; state: "complete" | "partial" | "not started" }[];
  complete: number; expected: number; final: boolean;
};
export const getStatus = () => readOptional<RunStatus>("status.json");
