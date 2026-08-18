import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";

/**
 * Regionen — vorberechnete NUTS-3-Kennzahlen (`scripts/export_regionen.py`).
 *
 * Wie beim Marktpuls: reine Auslieferung einer statischen Aggregatdatei, keine Abfrage im
 * Seitenaufruf. 174 KB, 437 Regionen, kein Bezug zu einem einzelnen Verfahren, Käufer oder
 * Bieter — es gibt hier nichts zu redigieren und darum auch kein Tier-Gate.
 *
 * `stand`/`kontextJahr` liegen IN der Datei. Fällt der Tageslauf aus, kommt der letzte
 * erfolgreiche Stand mit seinem echten Datum — die Anzeige beschriftet ihn dann als das,
 * was er ist. Hier wird NICHTS auf „jetzt" umgeschrieben.
 */
export const revalidate = 3600;

export async function GET() {
  const roh = await loadDataFile("regionen.json");
  if (!roh) {
    return NextResponse.json({ fehler: "regionen.json nicht verfügbar" },
      { status: 503, headers: { "cache-control": "no-store" } });
  }
  return new NextResponse(roh, {
    headers: {
      "content-type": "application/json",
      "cache-control": "public, max-age=3600, stale-while-revalidate=86400",
    },
  });
}
