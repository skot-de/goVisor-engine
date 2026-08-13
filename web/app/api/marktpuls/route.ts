import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";

/**
 * Marktpuls — vorberechnete Saisonalität + aktuelle Marktlage.
 *
 * Reine Auslieferung einer **statischen, aggregierten** Datei (`scripts/build_marktpuls.py`
 * schreibt sie, Saisonalität monatlich / Lage täglich). Keine Datenbankabfrage im
 * Seitenaufruf, keine Einzelverfahren, ~23 KB.
 *
 * Kein Tier-/Paywall-Gate: der Marktpuls ist bewusst öffentlich — er positioniert goVisor
 * als Datenquelle. Er enthält ausschliesslich Aggregate ohne Bezug zu einem einzelnen
 * Verfahren, Käufer oder Bieter; es gibt hier nichts zu redigieren.
 *
 * `stand`/`erzeugt` liegen IN der Datei. Fällt der nächtliche Lauf aus, liefert diese Route
 * den letzten erfolgreichen Stand mit seinem echten Datum — die Anzeige kennzeichnet ihn
 * dann als veraltet (Briefing §4.3), statt alte Zahlen als aktuell auszugeben. Genau
 * deshalb wird hier NICHTS auf „jetzt" umgeschrieben.
 */
export const revalidate = 3600;

export async function GET() {
  const raw = await loadDataFile("marktpuls.json");
  if (!raw) {
    return NextResponse.json(
      { fehler: "marktpuls.json nicht verfügbar" },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
  return new NextResponse(raw, {
    headers: {
      "content-type": "application/json",
      // Aggregat, das sich höchstens täglich ändert — eine Stunde frisch, danach darf der
      // Cache die alte Fassung ausliefern, während im Hintergrund nachgeladen wird.
      "cache-control": "public, max-age=3600, stale-while-revalidate=86400",
    },
  });
}
