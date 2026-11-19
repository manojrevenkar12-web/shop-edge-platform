export const int = (n: number) => n.toLocaleString("en-GB", { maximumFractionDigits: 0 });
export const pct = (x: number, d = 2) => `${(x * 100).toFixed(d)}%`;
export const eur = (n: number) => `€${int(n)}`;

export const ORDER = [
  "shop_as_found",
  "short_ttl",
  "platform_broad_bans",
  "platform_utm_only",
  "platform_keeps_cookies",
  "platform_no_grace",
  "platform_flush_on_deploy",
  "platform_no_warm",
  "platform_cpu_scaling",
  "platform_no_prescale",
  "platform_threshold_alerts",
  "platform_ratio_burn_alerts",
  "platform_no_sonar_gate",
  "platform_no_canary",
  "platform",
];

export const SERIES_NAME: Record<string, string> = {
  shop_as_found: "Shop as found",
  short_ttl: "Five-minute TTL",
  platform: "Platform",
};

export const swatch = (name: string) =>
  name === "platform" ? "bg-platform" : name === "shop_as_found" ? "bg-asFound" : name === "short_ttl" ? "bg-shortTtl" : "bg-ablation";
