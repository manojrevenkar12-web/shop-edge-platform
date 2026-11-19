"""README results block and SVG charts, written only from reports/*.json. Nothing in the README is typed by hand."""
from __future__ import annotations

import json

from sep.config import ROOT
from sep.sim.designs import ORDER

START, END = "<!-- results:start -->", "<!-- results:end -->"
CHARTS = ROOT / "reports" / "charts"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
PLATFORM, BASELINE, NEUTRAL = "#2a78d6", "#eb6834", "#b9b8b3"
BASELINES = {"shop_as_found", "short_ttl"}
LINE = {"shop_as_found": "#eb6834", "short_ttl": "#1baf7a", "platform": "#2a78d6"}


def load(name: str) -> dict | None:
    p = ROOT / "reports" / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def pct(x: float, d: int = 2) -> str:
    return f"{x * 100:.{d}f}%"


def eur(x: float) -> str:
    return f"€{x:,.0f}"


def _color(n: str) -> str:
    return PLATFORM if n == "platform" else BASELINE if n in BASELINES else NEUTRAL


def _bars(s: dict, key: str, ci_key: str | None, title: str, fmt, fname: str) -> None:
    names = [n for n in ORDER if n in s["designs"]]
    w, row, left, right = 780, 26, 330, 90
    h = 44 + row * len(names) + 24
    vals = [s["designs"][n][key] for n in names]
    his = [s["designs"][n][ci_key][1] if ci_key else s["designs"][n][key] for n in names]
    top = max(max(his), max(vals), 1e-9) * 1.08
    x = lambda v: left + (w - left - right) * v / top  # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Inter, system-ui, sans-serif" '
           f'role="img" aria-label="{title}">', f'<rect width="{w}" height="{h}" fill="{SURFACE}"/>',
           f'<text x="16" y="24" font-size="14" font-weight="600" fill="{INK}">{title}</text>']
    for i, n in enumerate(names):
        y = 44 + i * row
        d = s["designs"][n]
        v = d[key]
        wt = "600" if n == "platform" else "400"
        out.append(f'<text x="{left - 10}" y="{y + 14}" font-size="12" text-anchor="end" fill="{INK}" '
                   f'font-weight="{wt}">{d["label"].split(":")[0]}</text>')
        out.append(f'<rect x="{left}" y="{y + 3}" width="{max(x(v) - left, 1.5):.1f}" height="16" rx="4" '
                   f'fill="{_color(n)}"/>')
        if ci_key:
            lo, hi = d[ci_key]
            out.append(f'<line x1="{x(lo):.1f}" x2="{x(hi):.1f}" y1="{y + 11}" y2="{y + 11}" stroke="{INK}" '
                       f'stroke-width="1.5"/>')
        out.append(f'<text x="{max(x(v), x(his[i])) + 6:.1f}" y="{y + 15}" font-size="11" fill="{MUTED}">{fmt(v)}</text>')
    note = "Whiskers: 95% interval from resampling days." if ci_key else "Development shops, all seeds."
    out.append(f'<text x="{left}" y="{h - 8}" font-size="10" fill="{MUTED}">{note}</text></svg>')
    CHARTS.mkdir(parents=True, exist_ok=True)
    (CHARTS / fname).write_text("\n".join(out) + "\n")


def _bf_chart(bf: dict) -> None:
    series = bf["series"]
    names = [n for n in ("shop_as_found", "short_ttl", "platform") if n in series]
    if not names:
        return
    w, h, l, r, t, b = 780, 300, 56, 150, 44, 40
    n = len(series[names[0]]["pods"])
    top = max(max(series[k]["pods"]) for k in names) * 1.1
    x = lambda i: l + (w - l - r) * i / max(n - 1, 1)  # noqa: E731
    y = lambda v: t + (h - t - b) * (1 - v / top)  # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Inter, system-ui, sans-serif" '
           f'role="img" aria-label="PHP pods running on Black Friday">',
           f'<rect width="{w}" height="{h}" fill="{SURFACE}"/>',
           f'<text x="16" y="24" font-size="14" font-weight="600" fill="{INK}">PHP pods running, Black Friday '
           f'(from 18:00 the evening before)</text>']
    for v in range(0, int(top) + 1, max(10, int(top / 5) // 10 * 10 or 10)):
        out.append(f'<line x1="{l}" x2="{w - r}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{GRID}"/>')
        out.append(f'<text x="{l - 8}" y="{y(v) + 4:.1f}" font-size="10" text-anchor="end" fill="{MUTED}">{v}</text>')
    for hh in range(0, n, 36):
        label = f"{(18 + hh // 12) % 24:02d}:00"
        out.append(f'<text x="{x(hh):.1f}" y="{h - b + 16}" font-size="10" text-anchor="middle" '
                   f'fill="{MUTED}">{label}</text>')
    for k in names:
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(series[k]["pods"]))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{LINE[k]}" stroke-width="2"/>')
        last = series[k]["pods"][-1]
        lab = {"shop_as_found": "Shop as found", "short_ttl": "Five-minute TTL", "platform": "Platform"}[k]
        out.append(f'<text x="{w - r + 8}" y="{y(last) + 4:.1f}" font-size="11" fill="{INK}">{lab}</text>')
    out.append("</svg>")
    (CHARTS / "blackfriday_pods.svg").write_text("\n".join(out) + "\n")


def charts(s: dict) -> None:
    _bars(s, "lost_orders_per_month", "lost_orders_ci", "Orders lost to errors per month (simulated shop)",
          lambda v: f"{v:,.0f}", "lost_orders.svg")
    _bars(s, "compute_eur_per_month", None, "PHP compute per month", eur, "compute_cost.svg")
    bf = load("blackfriday")
    if bf:
        _bf_chart(bf)


def _headline(s: dict, which: str) -> list[str]:
    d = s["designs"]
    p, a, st = d["platform"], d["shop_as_found"], d["short_ttl"]
    wd = s["world"]
    rows = [
        ("Page views answered without an error", lambda x: pct(x["availability"], 3)),
        ("... on Black Friday", lambda x: pct(x["bf_availability"], 3)),
        ("Served from the cache", lambda x: pct(x["hit_ratio"], 1)),
        ("Views showing a price that had already changed, per 100k", lambda x: f"{x['wrong_per_100k']:,.1f}"),
        ("Orders lost to errors per month", lambda x: f"{x['lost_orders_per_month']:,.0f}"),
        ("Orders taken for items out of stock per month", lambda x: f"{x['oversold_per_month']:,.0f}"),
        ("PHP compute per month", lambda x: eur(x["compute_eur_per_month"])),
        ("Peak PHP pods", lambda x: str(x["peak_pods"])),
        ("Broken builds that reached every visitor", lambda x: f"{x['reached_everyone']} of {x['bad_builds']}"),
        ("Pages that were not about a real problem, per week", lambda x: f"{x['false_pages_per_week']:.1f}"),
    ]
    out = [f"| {which} | Platform | Shop as found | Five-minute TTL |", "|---|---:|---:|---:|"]
    for label, f in rows:
        out.append(f"| {label} | **{f(p)}** | {f(a)} | {f(st)} |")
    out += ["", f"{len(wd['seeds'])} simulated shops, {wd['days']} days, {wd['views']:,} page views across 15 country "
            f"shops, {wd['changes']:,} price and stock changes, {wd['deploys']} releases ({wd['defective_builds']} "
            f"broken), {wd['incidents']} incidents and {wd['blips']} short error blips, Black Friday included."]
    return out


def _design_table(s: dict) -> list[str]:
    rows = ["| Design | Availability (95% interval) | Black Friday | Cache hits | Wrong prices per 100k | "
            "Lost orders / month | Compute / month | Broken builds to everyone | False pages / week |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for n in ORDER:
        if n not in s["designs"]:
            continue
        d = s["designs"][n]
        cells = [f"{pct(d['availability'], 3)} ({pct(d['availability_ci'][0], 3)}–{pct(d['availability_ci'][1], 3)})",
                 pct(d["bf_availability"], 3), pct(d["hit_ratio"], 1), f"{d['wrong_per_100k']:,.1f}",
                 f"{d['lost_orders_per_month']:,.0f}", eur(d["compute_eur_per_month"]),
                 f"{d['reached_everyone']} of {d['bad_builds']}", f"{d['false_pages_per_week']:.1f}"]
        label = d["label"]
        if n == "platform":
            label, cells = f"**{label}**", [f"**{c}**" for c in cells]
        rows.append(f"| {label} | " + " | ".join(cells) + " |")
    return rows


def _alerts_table(s: dict) -> list[str]:
    rows = ["| Design | Page-worthy episodes | Paged for | Mean minutes to page | Pages in all | Blocked by "
            "SonarQube | Caught by the canary |", "|---|---:|---:|---:|---:|---:|---:|"]
    for n in ("shop_as_found", "platform_threshold_alerts", "platform_ratio_burn_alerts", "platform_no_canary",
              "platform_no_sonar_gate", "platform"):
        if n not in s["designs"]:
            continue
        d = s["designs"][n]
        mt = "–" if d["mttd_minutes"] is None else f"{d['mttd_minutes']:.1f}"
        rows.append(f"| {d['label'].split(':')[0]} | {d['episodes']} | {d['detected']} | {mt} | {d['pages']} | "
                    f"{d['blocked_by_gate']} | {d['caught_by_canary']} |")
    return rows


def block() -> str:
    dev, ho = load("dev"), load("heldout")
    if dev is None:
        return f"{START}\n_No results yet: run `python -m sep.eval.cli evaluate`._\n{END}"
    out = [START, "", "### Dashboard (development shops)", ""] + _headline(dev, "Development")
    out += ["", "![Orders lost to errors per month](reports/charts/lost_orders.svg)", "",
            "![PHP compute per month](reports/charts/compute_cost.svg)", "",
            "![PHP pods running on Black Friday](reports/charts/blackfriday_pods.svg)", "",
            "### Every design on the same traffic", ""] + _design_table(dev)
    out += ["", "### Alerts and releases", ""] + _alerts_table(dev)
    if ho:
        from sep.eval.cli import gate

        fails = gate(ho)
        out += ["", "### Held-out shops (run once)", ""] + _headline(ho, "Held-out") + ["", (
            "Gate (`config/gate.yaml`) on the held-out shops: " + (
                "**passed**." if not fails else "**not passed**: " + "; ".join(fails) + ".")),
            "", "What happened on the held-out shops, and what changed after: [docs/heldout.md](docs/heldout.md)."]
    out += ["", END]
    return "\n".join(out)


def readme(check: bool = False) -> bool:
    p = ROOT / "README.md"
    if not p.exists():
        return False
    text = p.read_text()
    a, b = text.index(START), text.index(END) + len(END)
    new = text[:a] + block() + text[b:]
    if check:
        return new != text
    p.write_text(new)
    return new != text
