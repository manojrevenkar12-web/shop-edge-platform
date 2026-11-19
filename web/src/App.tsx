import { BlackFridayView } from "./features/blackfriday/BlackFridayView";
import { ReleasesView } from "./features/releases/ReleasesView";
import { ResultsView } from "./features/results/ResultsView";
import { type View, go, useRoute } from "./shared/route";

const TABS: { view: View; label: string }[] = [
  { view: "results", label: "Results" },
  { view: "blackfriday", label: "Black Friday" },
  { view: "releases", label: "Releases and alerts" },
];

export function App() {
  const { view } = useRoute();
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-sheet">
        <div className="mx-auto flex max-w-page flex-wrap items-end justify-between gap-4 px-6 pt-5">
          <div className="pb-4">
            <p className="text-lead font-bold text-ink narrow">Shop edge platform</p>
            <p className="text-small text-muted">Varnish, GKE and Prometheus for a 15-country lighting shop, simulated</p>
          </div>
          <nav aria-label="Views" className="flex gap-1">
            {TABS.map((t) => (
              <button
                key={t.view}
                type="button"
                onClick={() => go(t.view)}
                aria-current={view === t.view ? "page" : undefined}
                className={`border-b-rule px-4 pb-3 pt-2 font-semibold transition-colors ${
                  view === t.view ? "border-glow text-ink" : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-page px-6 py-7">
        {view === "results" && <ResultsView />}
        {view === "blackfriday" && <BlackFridayView />}
        {view === "releases" && <ReleasesView />}
      </main>
    </div>
  );
}
