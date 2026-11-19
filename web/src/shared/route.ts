import { useEffect, useState } from "react";

export type View = "results" | "blackfriday" | "releases";
const VIEWS: View[] = ["results", "blackfriday", "releases"];

function read(): { view: View; id: string | null } {
  const [, v, id] = window.location.hash.split("/");
  return { view: VIEWS.includes(v as View) ? (v as View) : "results", id: id ?? null };
}

export function useRoute() {
  const [r, setR] = useState(read);
  useEffect(() => {
    const on = () => setR(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return r;
}

export const go = (view: View, id?: string) => {
  window.location.hash = id ? `/${view}/${id}` : `/${view}`;
};
