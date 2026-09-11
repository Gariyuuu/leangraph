export type CI = [number, number];

export interface ConfigMetrics {
  n: number; verified: number; rate: number; ci: CI;
  success_within: Record<string, number>;
  median_calls_to_solve: number | null; llm_calls: number; tokens: number; cost_usd: number;
  cost_per_verified: number | null; tokens_per_verified: number | null;
  lean_check_s: number; certify_s: number; timeout_rate: number;
  repair_success: number | null; n_first_failed: number;
  mean_retrieval_recall: number | null; median_proof_lines: number | null; errors_trace: number;
}

export interface Group { n: number; verified: number; rate: number; ci: CI }

export interface Contrast {
  name: string; treatment: string; control: string; question: string; n: number;
  rate_treatment: number; rate_control: number; diff: number; diff_ci: CI;
  only_a: number; only_b: number; p: number; p_holm: number;
}

export interface Summary {
  run_id: string;
  configs: Record<string, ConfigMetrics>;
  by_split: Record<string, Record<string, Group>>;
  by_family: Record<string, Record<string, Group>>;
  by_difficulty: Record<string, Record<string, Group>>;
  contrasts: Contrast[];
  errors: {
    classes: string[]; total: Record<string, number>; per_config: Record<string, Record<string, number>>;
    repair_by_class: Record<string, { n: number; next_round_verified: number; rate: number }>;
  };
  difficulty_correlations: Record<string, { spearman_rho: number; p: number; n: number }>;
}

export interface TheoremRow {
  id: string; family: string; difficulty: string; split: string; role: string | null;
  statement: string; opens: string; source: string; solved_by: string[]; n_configs: number;
}

export interface Attempt {
  sample: number | null; round: number | null; proof: string; compiler_output: string;
  repl_ok: boolean | null; verified: boolean; cert_reason: string | null; error_class: string | null;
  completion_tokens: number | null; latency_s: number | null; timed_out: boolean;
}

export interface RunTrace {
  verified: boolean; final_proof: string | null; retrieved: string[];
  plan: { informal: string; skeleton: string | null; skeleton_ok: boolean | null; skeleton_output: string | null } | null;
  usage: Record<string, number> | null;
  certificate: { verified?: boolean; reason?: string; axioms?: string[]; elapsed_s?: number } | null;
  attempts: Attempt[]; error: string | null;
}

export interface TheoremDetail {
  task: {
    id: string; statement: string; opens: string; family: string; difficulty: string; split: string;
    source: string; module: string; reference_proof: string; banned_modules: string[];
    gt_premises: string[]; features: Record<string, unknown>;
  };
  runs: Record<string, RunTrace>;
}

export interface RetrievalSummary {
  n_tasks_with_ground_truth: number;
  methods: Record<string, Record<string, Record<string, { mean: number; ci: CI } | number>>>;
}
