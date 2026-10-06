export async function api<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/proxy${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...options.headers,
    },
    cache: "no-store",
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail || "Request failed"),
    );
  return data;
}
export const post = <T = unknown>(path: string, data: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(data) });
export type Language = {
  id: string;
  name: string;
  slug: string;
  alternate_names: string[];
  iso_code: string | null;
  description: string;
  default_dialect: string;
  orthography_notes: string;
  source_community: string;
  governance_notes: string;
  entry_count?: number;
  model_count?: number;
  dataset_count?: number;
};
export type Quality = {
  entries: number;
  unique_headwords: number;
  alternate_definitions: number;
  issues: Record<string, number>;
  needs_review: number;
  variants: number;
  transformations: number;
  score: number;
  score_method: string;
};
export type Source = {
  id: string;
  filename: string;
  status: string;
  quality: Quality;
  columns: string[];
  mapping: Record<string, string>;
  governance: Governance;
  sha256: string;
};
export type Governance = {
  owner: string;
  custodian: string;
  source: string;
  licence: string;
  training_allowed: boolean;
  commercial_use_allowed: boolean;
  redistribution_allowed: boolean;
  attribution: string;
};
export type Entry = {
  id: string;
  headword: string;
  normalized_headword: string;
  definitions: string[];
  alternate_spellings: string[];
  issues: string[];
  approved: boolean;
  training_eligible: boolean;
  original_row: Record<string, unknown>;
  metadata?: { transformations: unknown[]; explicit_review?: boolean };
  entry_metadata?: { transformations: unknown[]; explicit_review?: boolean };
};
export type Dataset = {
  id: string;
  version: number;
  entry_count: number;
  sha256: string;
  manifest: {
    counts: Record<string, number>;
    group_count: number;
    entry_splits: Record<string, string>;
  };
  generation_version: string;
  seed: number;
  source_ids: string[];
};
export type Metrics = {
  baseline?: Record<string, unknown>;
  fine_tuned?: Record<string, unknown>;
  delta?: Record<string, number>;
  baselines?: Record<string, Record<string, number>>;
  test_only_encoder?: boolean;
  experimental?: boolean;
  warning?: string;
};
export type Run = {
  id: string;
  dataset_id: string;
  task: string;
  base_model: string;
  base_model_revision: string;
  status: string;
  hyperparameters: Record<string, unknown>;
  metrics: Metrics;
  error?: string;
  created_at: string;
  cancel_requested: boolean;
};
export type Model = {
  id: string;
  dataset_id: string;
  task: string;
  version: number;
  base_model: string;
  status: string;
  metrics: Metrics;
  experimental: boolean;
  created_at: string;
};
export type RunEvent = {
  id: number;
  message: string;
  created_at: string;
  data: Record<string, unknown>;
};
export type User = {
  id: string;
  name: string;
  role: "owner" | "editor" | "viewer";
};
export type Match = {
  entry_id: string;
  headword: string;
  definitions: string[];
  score: number;
};
export const number = (value: number | undefined) =>
  (value || 0).toLocaleString();
export const short = (id: string) => id.slice(0, 8);
