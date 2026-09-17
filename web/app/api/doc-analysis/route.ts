import { NextResponse } from "next/server";
import { analyseIndexMitGrund } from "@/lib/docAnalysis";
import { dateiMarke } from "@/lib/dataSource";
import { etagAus, unveraendert } from "@/lib/etag.js";

export const dynamic = "force-dynamic";
const CACHE = "public, max-age=0, must-revalidate";

/* Welche Vorgaenge haben ausgewertete Vergabeunterlagen, und wie dicht?
 *
 * ⚠ WARUM EINE EIGENE ROUTE UND NICHT IN `/api/leads`. Jene Route gibt die Branchendatei
 * ROH zurueck, ohne sie zu parsen — gemessen am 2026-09-04 sind das 47,2 MB und 103 ms
 * Parse-Zeit, die dort ausdruecklich vermieden werden. Die Auswertungen einzumischen
 * hiesse, diesen Weg fuer 0,4 MB Zusatzinhalt aufzugeben.
 *
 * Dazu kommt: die beiden Quellen bewegen sich unabhaengig. Der Dokumenten-Arbeiter laeuft
 * staendig, der Lead-Export einmal taeglich. Zwei Dateien, zwei Marken, zwei ETags — so
 * bekommt eine frische Auswertung ihre Marke, ohne dass 47 MB neu ausgeliefert werden.
 */
export async function GET(req: Request) {
  const marke = await dateiMarke("doc-analysis-index.json");
  const etag = etagAus("doc-analysis", [marke]);
  if (unveraendert(etag, req.headers.get("if-none-match"))) {
    return new NextResponse(null, { status: 304, headers: { etag: etag!, "cache-control": CACHE } });
  }

  const { index, stoerung } = await analyseIndexMitGrund();

  /* ⚠ STOERUNG IST NICHT „KEINE AUSWERTUNGEN". Liefert der Datenspeicher nichts, waere
   * eine leere Karte mit Status 200 eine Behauptung: die Liste zeigte dann bei JEDEM Lead
   * „nicht ausgewertet", und das sieht aus wie ein Befund statt wie ein Ausfall. Genau
   * diese Verwechslung beschreibt `lib/leadIndex.ts` als den Fehler, der dort zweimal
   * passiert ist. 503 zwingt die Oberflaeche, den Unterschied zu kennen. */
  if (stoerung) {
    return NextResponse.json({ error: "Datenspeicher antwortet nicht" }, { status: 503 });
  }

  return NextResponse.json(Object.fromEntries(index), {
    headers: { "cache-control": CACHE, ...(etag ? { etag } : {}) },
  });
}
