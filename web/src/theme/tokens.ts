/**
 * Tokens for the shop's platform dashboard. Cool slate ground, deep navy ink, amber for the lamp-lit details (focus,
 * the active tab). Series follow the evaluation: blue the platform, orange the shop as found, green the five-minute
 * TTL, grey the ablations. Teal is good, red is broken. Every colour, size and duration comes from here.
 */
export const color = {
  ground: "#EEF1F4",
  sheet: "#FFFFFF",
  ink: "#111A2E",
  copy: "#2B3448",
  muted: "#535C72",
  line: "#D6DBE4",
  glow: "#A64B00",
  good: "#0F766E",
  goodWash: "#D7EEEA",
  bad: "#B42318",
  badWash: "#FBE4E1",
  platform: "#2A78D6",
  asFound: "#EB6834",
  shortTtl: "#1BAF7A",
  ablation: "#B9B8B3",
  focus: "#A64B00",
} as const;

export const font = {
  ui: ["Instrument Sans Variable", "Instrument Sans", "system-ui", "sans-serif"],
} as const;

/** 1.25 ratio from a 15px base. [size, line-height] */
export const type = {
  small: ["0.8125rem", "1.4"],
  body: ["0.9375rem", "1.55"],
  lead: ["1.1875rem", "1.4"],
  title: ["1.875rem", "1.15"],
  hero: ["2.75rem", "1.05"],
} as const;

export const space = { 0: "0", 1: "0.25rem", 2: "0.5rem", 3: "0.75rem", 4: "1rem", 5: "1.5rem", 6: "2rem", 7: "3rem", 8: "4rem" } as const;
export const radius = { none: "0", soft: "6px", pill: "999px" } as const;
export const measure = { prose: "68ch", page: "76rem", hero: "58rem", table: "62rem" } as const;
export const line = { hair: "1px", rule: "2px" } as const;
export const size = { swatch: "0.625rem", bar: "0.625rem", barTrack: "8rem", chart: "22rem" } as const;
export const chart = { width: 960, height: 340, left: 52, right: 130, top: 20, bottom: 36 } as const;
