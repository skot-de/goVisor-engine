import { NextRequest, NextResponse } from "next/server";
import { ladeMitGrund, DATEN_STOERUNG } from "@/lib/dataSource";
import { STOERUNG_ANTWORT } from "@/lib/ladegrund.js";
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

  /* ⚠ „KEINE TERMINE" UND „ICH KOMME NICHT DRAN" SIND NICHT DASSELBE.
   *
   * Der Absatz oben ist richtig: nicht jeder Lead hat eine Datei, und dann fehlt der Eintrag
   * zu Recht. Nur konnte diese Route den zweiten Fall nicht sehen — `loadDataFile` gab fuer
   * jeden Fehlschlag `null` zurueck, auch fuer „Speicher antwortet 500". Bei unerreichbarem
   * Datenspeicher meldete sie also fuer JEDEN Lead „keine Termine", mit HTTP 200.
   *
   * Das ist die teuerste Stelle fuer diese Verwechslung im ganzen Produkt: hier stehen
   * Bindefrist und letzter Tag fuer Bieterfragen — Termine, nach denen jemand seinen
   * Kalender richtet. Eine ausgefallene Abfrage, die wie „nichts zu beachten" aussieht,
   * kostet eine Abgabe. */
  let stoerung = false;
  const paare = await Promise.all(
    ids.map(async (id) => {
      try {
        const { text, grund } = await ladeMitGrund(`kalender/${id}.json`);
        if (grund === DATEN_STOERUNG) stoerung = true;
        return text ? ([id, JSON.parse(text)] as const) : null;
      } catch {
        return null; // fehlt oder kaputt → dieser Lead hat eben keine Termine
      }
    }),
  );
  // Eine einzige Stoerung genuegt: dann ist die Antwort unvollstaendig, und welche Leads
  // wirklich terminlos sind, weiss niemand mehr.
  if (stoerung) return NextResponse.json(STOERUNG_ANTWORT, { status: 503 });

  const aus: Record<string, unknown> = {};
  for (const p of paare) if (p) aus[p[0]] = p[1];
  return NextResponse.json(aus, { headers: { "cache-control": "no-store" } });
}
