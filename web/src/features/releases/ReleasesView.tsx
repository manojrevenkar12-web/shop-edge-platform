import { useResource } from "../../shared/api";
import { pct } from "../../shared/format";
import type { Results, Summary } from "../../shared/types";
import { ErrorState, Skeleton, Tone } from "../../shared/ui/states";

const ROWS = ["shop_as_found", "platform_threshold_alerts", "platform_ratio_burn_alerts", "platform_no_sonar_gate", "platform_no_canary", "platform"];

export function ReleasesView() {
  const r = useResource<Results>("/api/results");
  if (r.loading) return <Skeleton label="Loading releases and alerts" rows={6} />;
  if (r.error || !r.data) return <ErrorState error={r.error!} retry={r.retry} what="releases and alerts" />;
  const { dev, heldout, heldout_gate_fails } = r.data;
  return (
    <div className="flex flex-col gap-8">
      <div className="flex max-w-prose flex-col gap-2">
        <h1 className="text-title font-bold narrow">Releases and alerts</h1>
        <p className="text-muted">
          Broken builds come from the same commits for every design. SonarQube can only see some defects; the canary
          sees the rest on 10% of traffic. Alerts are scored against episodes that burned at least 2% of their SLO's
          monthly budget: a page outside one is a page someone was woken for without a reason.
        </p>
      </div>
      <Table s={dev} caption="Development shops" />
      {heldout ? (
        <section aria-labelledby="heldout" className="flex flex-col gap-3">
          <h2 id="heldout" className="text-lead font-bold">Held-out shops, run once</h2>
          <Gate fails={heldout_gate_fails ?? []} />
          <Table s={heldout} caption="Held-out shops" />
        </section>
      ) : (
        <p className="text-muted">The held-out shops have not been run yet.</p>
      )}
    </div>
  );
}

function Table({ s, caption }: { s: Summary; caption: string }) {
  return (
    <div role="region" aria-label={caption} tabIndex={0} className="overflow-x-auto rounded-soft border border-line bg-sheet">
      <table className="w-full min-w-table border-collapse text-left">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line text-small text-muted">
            <th scope="col" className="px-4 py-3 font-semibold">Design</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Broken builds</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Stopped by SonarQube</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Stopped by the canary</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Reached everyone</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Episodes paged for</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">False pages a week</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.filter((n) => s.designs[n]).map((n) => {
            const d = s.designs[n]!;
            const strong = n === "platform";
            return (
              <tr key={n} className={`border-b border-line last:border-0 ${strong ? "bg-ground font-bold text-ink" : ""}`}>
                <th scope="row" className={`px-4 py-3 ${strong ? "" : "font-normal"}`}>{d.label.split(":")[0]}</th>
                <td className="px-4 py-3 text-right">{d.bad_builds}</td>
                <td className="px-4 py-3 text-right">{d.blocked_by_gate}</td>
                <td className="px-4 py-3 text-right">{d.caught_by_canary}</td>
                <td className="px-4 py-3 text-right">{d.reached_everyone}</td>
                <td className="px-4 py-3 text-right">{d.detected} of {d.episodes}</td>
                <td className="px-4 py-3 text-right">{d.false_pages_per_week.toFixed(1)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Gate({ fails }: { fails: string[] }) {
  // the verdict is computed once, by the same code as `python -m sep.eval.cli gate`
  return (
    <div className="flex flex-col gap-2">
      <p className="flex flex-wrap items-center gap-3">
        {fails.length === 0 ? <Tone tone="good">Gate passed</Tone> : <Tone tone="bad">Gate not passed</Tone>}
        <span className="text-muted">
          {fails.length ? `Missed on: ${fails.join("; ")}.` : "Every limit in config/gate.yaml was met."}
        </span>
      </p>
      {fails.length > 0 && (
        <p className="max-w-[70ch] text-muted">
          The held-out numbers stay as they were run. The cause and what changed afterwards are in docs/heldout.md.
        </p>
      )}
    </div>
  );
}
