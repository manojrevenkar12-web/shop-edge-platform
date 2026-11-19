/** The API, and the one hook every screen loads with: loading, error (with retry) and data. */
import { useCallback, useEffect, useState } from "react";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, { headers: { accept: "application/json" } });
  } catch {
    throw new ApiError(0, "The dashboard cannot reach the API. Start it with `uvicorn sep.service.api:app --port 8080`.");
  }
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(r.status, (body as { detail?: string }).detail ?? `The API answered ${r.status}.`);
  return body as T;
}

export type Resource<T> = { data: T | null; error: ApiError | null; loading: boolean; retry: () => void };

export function useResource<T>(path: string | null): Resource<T> {
  const [state, setState] = useState<{ data: T | null; error: ApiError | null; loading: boolean }>({
    data: null,
    error: null,
    loading: !!path,
  });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!path) return;
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    api<T>(path)
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch((error: ApiError) => live && setState({ data: null, error, loading: false }));
    return () => {
      live = false;
    };
  }, [path, attempt]);
  const retry = useCallback(() => setAttempt((x) => x + 1), []);
  return { ...state, retry };
}
