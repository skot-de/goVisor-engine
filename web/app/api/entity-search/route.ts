import { NextRequest, NextResponse } from "next/server";
import { loadSuppliersBasis, loadSupplier, type SupplierBasis } from "@/lib/suppliers";
import { bremse } from "@/lib/rateLimit";

/* Firmen-Matching fürs Onboarding (Ticket #7 v2): getippter Name → Fuzzy-Abgleich gegen
 * die echten Gewinner (identity-gruppiert). Liefert bestätigbare Vorschläge, kein Auto-Match. */

const norm = (s: string) =>
  s.toLowerCase().replace(/[^a-z0-9äöüß ]/g, " ").replace(/\b(gmbh|ag|se|kg|co|ohg|mbh|und|the)\b/g, " ").replace(/\s+/g, " ").trim();

/* ⚠ DAS IST DIE ENUMERATIONS-FLÄCHE. Diese Route MUSS vor dem Anmelde-Tor liegen (das
   Onboarding braucht sie, bevor es ein Konto gibt) und gibt zu jedem Namensfragment Firma,
   Zuschlagszahl, Auftraggeberzahl und CPV-Felder heraus. Ohne Bremse holt eine Schleife über
   „aa".."zz" den Bestand ab.
   Die Zahlen sind an der echten Nutzung gemessen: das Onboarding tippt mit 220 ms Verzögerung,
   ein voller Firmenname löst eine Handvoll Abfragen aus. 60 pro Minute merkt niemand, der
   tippt; 600 pro Stunde deckelt die Schleife, die über Nacht laufen soll. */
const PRO_MINUTE = 60, PRO_STUNDE = 600;

export async function GET(req: NextRequest) {
  const zuViel = bremse(req, "entitysearch-min", PRO_MINUTE, 60_000)
              ?? bremse(req, "entitysearch-std", PRO_STUNDE, 3_600_000);
  if (zuViel) return zuViel;
  const q = norm(req.nextUrl.searchParams.get("q") || "");
  if (q.length < 2) return NextResponse.json({ matches: [] });
  // ⚠ Gesucht wird ueber die BASIS (Name, Aliasse, wins) — 46 MB dafuer zu laden waere
  // das Fuenfzehnfache dessen, was die Suche anfasst. Die schweren Felder holt erst die
  // Anreicherung unten, und zwar fuer sechs Firmen statt fuer 37.901.
  const all = await loadSuppliersBasis();

  const scored: { s: SupplierBasis; score: number }[] = [];
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
  const matches = (await Promise.all(scored.slice(0, 6).map(async ({ s, score }) => {
    const v = await loadSupplier(s.id);
    if (!v) return null;
    return {
      id: v.id, name: v.name, wins: v.wins, buyers: v.buyers, seit: v.seit,
      fields: v.fields, fields6: v.fields6 ?? [], regions: v.regions,
      regionTyp: v.regionTyp ?? null, volMedian: v.volMedian,
      topBuyers: v.topBuyers ?? [], topShare: v.topShare ?? null,
      strong: score >= 80,          // starker Vorschlag vs. „meinst du eine dieser?"
    };
  }))).filter(Boolean);
  return NextResponse.json({ matches });
}
