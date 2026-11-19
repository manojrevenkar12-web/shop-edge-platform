/** The three states every screen can be in besides "ready". */
import type { ReactNode } from "react";
import type { ApiError } from "../api";

export function Skeleton({ rows = 6, label }: { rows?: number; label: string }) {
  return (
    <div role="status" aria-label={label} aria-busy="true" className="flex flex-col gap-3 py-4">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-5 animate-pulse rounded-soft bg-line" style={{ width: `${92 - ((i * 13) % 35)}%` }} />
      ))}
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function ErrorState({ error, retry, what }: { error: ApiError; retry: () => void; what: string }) {
  return (
    <div role="alert" className="flex max-w-prose flex-col items-start gap-3 rounded-soft border border-bad bg-badWash p-5">
      <h2 className="text-lead font-semibold text-bad">Couldn't load {what}</h2>
      <p>{error.message}</p>
      <button type="button" onClick={retry} className="rounded-pill bg-ink px-4 py-2 font-semibold text-sheet">
        Try again
      </button>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex max-w-prose flex-col gap-2 rounded-soft border border-dashed border-line p-6">
      <h2 className="text-lead font-semibold">{title}</h2>
      <div className="text-muted">{children}</div>
    </div>
  );
}

export function Tone({ tone, children }: { tone: "good" | "bad"; children: ReactNode }) {
  const cls = { good: "bg-goodWash text-good", bad: "bg-badWash text-bad" }[tone];
  return <span className={`inline-flex items-center rounded-pill px-3 py-1 text-small font-semibold ${cls}`}>{children}</span>;
}
