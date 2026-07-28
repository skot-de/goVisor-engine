import { notFound } from "next/navigation";
import { ExplorerShell } from "@/components/explorer/ExplorerShell";
import "../explorer.css";

// Jede Explorer-Ansicht hat eine eigene, stabile URL: /leads /watchlist /network /strategy.
// Slugs englisch/universell (über alle Länder gleich); die Shell liest den Slug beim Mount und
// wechselt in-app per history.pushState (kein Remount).
const VIEWS = new Set(["leads", "watchlist", "network", "strategy"]);

export function generateStaticParams() {
  return [...VIEWS].map((view) => ({ view }));
}

export default async function Page({ params }: { params: Promise<{ view: string }> }) {
  const { view } = await params;
  if (!VIEWS.has(view)) notFound();
  return <ExplorerShell initialSlug={view} />;
}
