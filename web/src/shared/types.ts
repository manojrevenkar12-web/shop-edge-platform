export type DesignResult = {
  label: string;
  availability: number;
  availability_ci: [number, number];
  fast_share: number;
  bf_availability: number | null;
  bf_fast_share: number | null;
  hit_ratio: number;
  wrong_per_100k: number;
  wrong_ci: [number, number];
  oversold_per_month: number;
  lost_orders_per_month: number;
  lost_orders_ci: [number, number];
  lost_revenue_per_month: number;
  compute_eur_per_month: number;
  cost_eur_per_month: number;
  peak_pods: number;
  pages: number;
  episodes: number;
  detected: number;
  mttd_minutes: number | null;
  false_pages_per_week: number;
  bad_builds: number;
  blocked_by_gate: number;
  caught_by_canary: number;
  reached_everyone: number;
  defect_hours_full: number;
};

export type Summary = {
  world: { seeds: number[]; days: number; views: number; changes: number; deploys: number; defective_builds: number; incidents: number; blips: number; pages: number };
  designs: Record<string, DesignResult>;
};

export type Results = {
  dev: Summary;
  heldout: Summary | null;
  gate: Record<string, number>;
  heldout_gate_fails: string[] | null;
};

export type Series = { views: number[]; errors: number[]; pods: number[]; hit: number[]; slow: number[] };
export type BlackFriday = { seed: number; step_minutes: number; series: Record<string, Series> };
