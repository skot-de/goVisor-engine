import { NextRequest, NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";
import { bremse } from "@/lib/rateLimit";

/* Verfahrenstermine mehrerer Leads — für die Terminansicht der Merkliste.
 *
 * WAS HIER MEHR STEHT ALS IM LEAD. Die Bekanntmachung kennt genau einen Termin, die
 * Angebotsfrist. Aus den Unterlagen kommen die dazu, die dort NICHT stehen und trotzdem
 * über Erfolg oder Ausschluss entscheiden — vor allem die **Bindefrist** (wie lange man
 * an sein Angebot gebunden bleibt) und der **letzte Tag für Bieterfragen**, der VOR der
 * Angebotsfrist liegt. Erzeugt von `scripts/export_kalender.py`.
 *
 * ⚠ EINE DATEI JE VORGANG, kein Sammelabruf. `doc-analysis.json` war auf 252 MB gewachsen,
 * bevor sie zerlegt wurde; der Kalender wiederholt das nicht. Die Merkliste umfasst eine
 * Handvoll Leads — genau die werden geholt.
 *
 * ⚠ NICHT JEDER LEAD HAT EINE DATEI. Nur wo die Unterlagen ausgelesen sind UND ein Termin
 * sich einer Art zuordnen liess. Fehlt sie, fehlt der Eintrag — der Aufrufer zeigt dann
 * weiter die Angebotsfrist aus dem Lead, statt Wissen zu behaupten, das wir nicht haben.
 */

// Obergrenze je Anfrage. Eine Merkliste ist eine Merkliste; wer 500 IDs schickt, klappert
// den Bestand ab, und das ist nicht der Zweck dieser Route.
const MAX_IDS = 60;

export async function GET(req: NextRequest) {
  const zuViel = bremse(req, "kalender", 60, 60_000);
  if (zuViel) return zuViel;

  const roh = (req.nextUrl.searchParams.get("ids") || "").split(",");
  // Derselbe Filter wie beim Analyse-Abruf: der Dateiname darf nie aus ungeprüfter
  // Eingabe entstehen, sonst ist die Route ein Pfad-Ausbruch.
  const ids = Array.from(new Set(roh.map((s) => s.replace(/[^A-Za-z0-9_-]/g, ""))))
    .filter(Boolean)
    .slice(0, MAX_IDS);
  if (!ids.length) return NextResponse.json({});

  const paare = await Promise.all(
    ids.map(async (id) => {
      try {
        const txt = await loadDataFile(`kalender/${id}.json`);
        return txt ? ([id, JSON.parse(txt)] as const) : null;
      } catch {
        return null; // fehlt oder kaputt → dieser Lead hat eben keine Termine
      }
    }),
  );

  const aus: Record<string, unknown> = {};
  for (const p of paare) if (p) aus[p[0]] = p[1];
  return NextResponse.json(aus, { headers: { "cache-control": "no-store" } });
}
