import { NextRequest, NextResponse } from "next/server";
import { loadSuppliers, type Supplier } from "@/lib/suppliers";

/* Firmen-Matching fürs Onboarding (Ticket #7 v2): getippter Name → Fuzzy-Abgleich gegen
 * die echten Gewinner (identity-gruppiert). Liefert bestätigbare Vorschläge, kein Auto-Match. */

const norm = (s: string) =>
  s.toLowerCase().replace(/[^a-z0-9äöüß ]/g, " ").replace(/\b(gmbh|ag|se|kg|co|ohg|mbh|und|the)\b/g, " ").replace(/\s+/g, " ").trim();

export async function GET(req: NextRequest) {
  const q = norm(req.nextUrl.searchParams.get("q") || "");
  if (q.length < 2) return NextResponse.json({ matches: [] });
  const all = await loadSuppliers();

  const scored: { s: Supplier; score: number }[] = [];
  for (const s of all) {
    const hay = [s.name, ...s.aliases].map(norm);
    let score = 0;
    for (const h of hay) {
      if (h === q) { score = Math.max(score, 100); break; }
      if (h.startsWith(q)) score = Math.max(score, 80);
      else if (h.includes(q)) score = Math.max(score, 60);
      else if (q.length >= 4 && h.includes(q.slice(0, Math.ceil(q.length * 0.7)))) score = Math.max(score, 35);
    }
    if (score > 0) scored.push({ s, score });
  }

  // Nach Trefferqualität, dann nach Zuschlägen (die stärkeren Firmen zuerst).
  scored.sort((a, b) => b.score - a.score || b.s.wins - a.s.wins);
  // Mitglieder bleiben draußen (lädt der Gruppen-Screen bei Bedarf) — Suche schlank halten.
  const matches = scored.slice(0, 6).map(({ s, score }) => ({
    id: s.id, name: s.name, wins: s.wins, buyers: s.buyers, seit: s.seit,
    fields: s.fields, fields6: s.fields6 ?? [], regions: s.regions, regionTyp: s.regionTyp ?? null, volMedian: s.volMedian,
    strong: score >= 80,          // starker Vorschlag vs. „meinst du eine dieser?"
  }));
  return NextResponse.json({ matches });
}
