import { useResource } from "../../shared/api";
import { ORDER, eur, int, pct, swatch } from "../../shared/format";
import type { Results, Summary } from "../../shared/types";
import { ErrorState, Skeleton } from "../../shared/ui/states";

export function ResultsView() {
  const r = useResource<Results>("/api/results");
  if (r.loading) return <Skeleton label="Loading the evaluation" rows={8} />;
  if (r.error || !r.data) return <ErrorState error={r.error!} retry={r.retry} what="the evaluation" />;
  const s = r.data.dev;
  return (
    <div className="flex flex-col gap-8">
      <Hero s={s} />
      <section aria-labelledby="designs" className="flex flex-col gap-4">
        <h2 id="designs" className="text-title font-bold narrow">
          Every design on the same traffic
        </h2>
        <p className="max-w-prose text-muted">
          The same shops, page views, catalogue changes, incidents and releases for every row. A grey row is the
          platform with exactly one safeguard removed; its gap to the blue row is what that safeguard is worth.
        </p>
        <DesignTable s={s} caption="Development shops" />
      </section>
    </div>
  );
}

function Hero({ s }: { s: Summary }) {
  const p = s.designs.platform!;
  const a = s.designs.shop_as_found!;
  return (
    <section aria-labelledby="hero" className="flex max-w-hero flex-col gap-4 pt-2">
      <h1 id="hero" className="text-title font-semibold leading-snug narrow">
        Across {int(s.world.views)} page views and a Black Friday, the platform lost{" "}
        <span className="text-hero font-bold text-good" data-testid="platform-lost">
          {int(p.lost_orders_per_month)}
        </span>{" "}
        orders a month to errors. The shop as found lost{" "}
        <span className="text-hero font-bold text-bad" data-testid="asfound-lost">
          {int(a.lost_orders_per_month)}
        </span>
        .
      </h1>
      <p className="max-w-prose text-lead">
        {pct(p.hit_ratio, 0)} of views came from the cache (as found {pct(a.hit_ratio, 0)}), no view showed a price that
        had already changed, and PHP compute cost {eur(p.compute_eur_per_month)} a month instead of {eur(a.compute_eur_per_month)}.
      </p>
    </section>
  );
}

function Bar({ value, max, name }: { value: number; max: number; name: string }) {
  const w = max > 0 ? Math.max((value / max) * 100, value > 0 ? 2 : 0) : 0;
  return (
    <span aria-hidden="true" className="inline-block h-bar w-track overflow-hidden rounded-pill bg-ground align-middle">
      <span className={`block h-full rounded-pill ${swatch(name)}`} style={{ width: `${w}%` }} />
    </span>
  );
}

export function DesignTable({ s, caption }: { s: Summary; caption: string }) {
  const names = ORDER.filter((n) => s.designs[n]);
  const maxLost = Math.max(...names.map((n) => s.designs[n]!.lost_orders_per_month));
  return (
    <div role="region" aria-label={caption} tabIndex={0} className="overflow-x-auto rounded-soft border border-line bg-sheet">
      <table className="w-full min-w-table border-collapse text-left">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line text-small text-muted">
            <th scope="col" className="px-4 py-3 font-semibold">Design</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Availability</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Black Friday</th>
            <th scope="col" className="px-4 py-3 font-semibold">Served from cache</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Old prices per 100k</th>
            <th scope="col" className="px-4 py-3 font-semibold">Orders lost a month</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Compute a month</th>
          </tr>
        </thead>
        <tbody>
          {names.map((n) => {
            const d = s.designs[n]!;
            const strong = n === "platform";
            return (
              <tr key={n} className={`border-b border-line last:border-0 ${strong ? "bg-ground" : ""}`}>
                <th scope="row" className={`px-4 py-3 ${strong ? "font-bold text-ink" : "font-normal"}`}>
                  <span className="flex items-center gap-2">
                    <span aria-hidden="true" className={`size-swatch shrink-0 rounded-pill ${swatch(n)}`} />
                    {d.label.split(":")[0]}
                  </span>
                </th>
                <td className="px-4 py-3 text-right">{pct(d.availability, 3)}</td>
                <td className="px-4 py-3 text-right">{d.bf_availability === null ? "–" : pct(d.bf_availability, 3)}</td>
                <td className="px-4 py-3">
                  <span className="flex items-center gap-3">
                    <Bar value={d.hit_ratio} max={1} name={n} />
                    {pct(d.hit_ratio, 1)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">{d.wrong_per_100k.toFixed(1)}</td>
                <td className="px-4 py-3">
                  <span className="flex items-center gap-3">
                    <Bar value={d.lost_orders_per_month} max={maxLost} name={n} />
                    {int(d.lost_orders_per_month)}
                  </span>
                </td>
                <td className={`px-4 py-3 text-right ${strong ? "font-bold text-ink" : ""}`}>{eur(d.compute_eur_per_month)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
