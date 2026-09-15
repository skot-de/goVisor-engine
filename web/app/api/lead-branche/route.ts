import { NextResponse } from "next/server";
import { leadBranchen } from "@/lib/leadIndex";

/* In welchem Grundraum liegt diese Kennung?
 *
 * Der Vergabe-Verlauf einer Vergabestelle zeigt Zuschläge über ALLE Branchen, die geladene
 * Liste trägt aber nur einen Grundraum. Damit ein Klick dorthin nicht in einer Sackgasse
 * endet, fragt der Explorer hier nach und wechselt selbst (`ExplorerShell::holeFremdenLead`).
 *
 * ⚠ Bewusst NUR der Grundraum, nicht der Lead. Den holt danach der reguläre Weg
 * (`/api/leads?branche=…` + `/api/lead-detail`) — mit derselben Redaktion je Tarif. Eine
 * Route, die einen einzelnen Lead an der Branchenliste vorbei ausliefert, wäre ein zweiter
 * Weg an dieselben Daten und müsste jede Gate-Regel noch einmal nachbauen.
 *
 * Liegt hinter dem Anmelde-Tor (nicht in `middleware.ts::OFFEN`), wie `/api/leads` auch.
 */
export async function GET(req: Request) {
  const id = new URL(req.url).searchParams.get("id") || "";
  if (!id) return NextResponse.json({ error: "keine Kennung" }, { status: 400 });

  const branche = (await leadBranchen()).get(id) ?? null;
  // 404 wäre hier irreführend: die Route gibt es, die Kennung kennen wir nur nicht. Der
  // Aufrufer unterscheidet ohnehin nur „Grundraum da" von „kein Grundraum".
  return NextResponse.json({ branche }, { headers: { "cache-control": "no-store" } });
}
