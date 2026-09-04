import { NextResponse } from "next/server";
import { loadDataFile, dateiMarke } from "@/lib/dataSource";
// ⚠ Die ETag-Regel liegt in Plain JS, damit `node` sie pruefen kann —
// `dataSource.ts` traegt `server-only` und waere fuer einen Test unerreichbar.
import { etagAus, unveraendert } from "@/lib/etag";

// Echte Leads aus der Gold-Schicht (per scripts/export_web_leads.py als JSON abgelegt), geladen
// über den konfigurierbaren Daten-Loader (lokal oder Object-Storage via DATA_BASE_URL).
// `ohne` = Vergaben, deren Quelle keinen CPV-Code führt (NetServer-Trefferlisten, Teile
// von DÖE). Seit die CPV-Pflicht aus dem Lead-Bau raus ist, sind sie im Bestand — ohne
// diesen Eintrag antwortet die Route auf sie mit HTTP 400 und die Leads wären zwar
// exportiert, aber für die App unerreichbar. Ein Grundraum ist erst durchgängig, wenn
// Export, Route UND Anzeige ihn kennen.
const BRANCHEN = new Set(["it", "bau", "medizin", "beratung", "sicherheit", "energie",
                          "ohne"]);

/* Wie der Browser die Antwort behandeln darf.
 *
 * `must-revalidate` mit `max-age=0`: bei JEDEM Aufruf wird nachgefragt, aber nur uebertragen,
 * wenn sich etwas geaendert hat. Keine veralteten Zahlen, und der Rueckweg kostet ein paar
 * hundert Byte statt 5,6 MB.
 *
 * ⚠ Bewusst KEIN `max-age=300` o. ae. Der Bestand wird nachts neu gebaut, aber auch tagsueber
 * von Hand — ein Fenster, in dem der Browser stillschweigend Altes zeigt, waere fuer ein
 * Produkt, das mit Fristen wirbt, der falsche Tausch. `private`, weil die Antwort je nach
 * Konto redigiert sein kann und in keinen geteilten Zwischenspeicher gehoert. */
const CACHE = "private, max-age=0, must-revalidate";

export async function GET(req: Request) {
  const branche = new URL(req.url).searchParams.get("branche") || "it";
  if (!BRANCHEN.has(branche)) {
    return NextResponse.json({ error: "unbekannter Grundraum" }, { status: 400 });
  }

  /* ⚠ ERST DIE MARKE, DANN DER RUMPF. Hier stand `cache-control: no-store`, und die Route
   * baute bei jedem Aufruf die volle Antwort — gemessen am 2026-09-04: 47,2 MB roh, 5,6 MB
   * gzip, dazu 103 ms `JSON.parse` fuer das Zusammenfuehren mit den Zuschlaegen. Und das
   * bei Daten, die sich einmal am Tag aendern.
   *
   * Der ETag deckt BEIDE Quellen ab. Nur die Leads zu betrachten hiesse: ein frischer
   * Zuschlag erscheint erst, wenn sich zufaellig auch die Leaddatei bewegt hat. */
  const [markeLeads, markeAwards] = await Promise.all([
    dateiMarke(`leads-${branche}.json`),
    dateiMarke(`awards-${branche}.json`),
  ]);
  // Ohne Marke kein ETag: eine Kennung, die stehen bleibt, waehrend sich die Daten bewegen,
  // waere schlimmer als gar keine (s. `dateiMarke` und `lib/etag.js`).
  const etag = etagAus(branche, [markeLeads, markeAwards]);
  if (unveraendert(etag, req.headers.get("if-none-match"))) {
    return new NextResponse(null, { status: 304, headers: { etag: etag!, "cache-control": CACHE } });
  }

  const json = await loadDataFile(`leads-${branche}.json`);
  if (!json) {
    return NextResponse.json({ error: "keine Daten — export_web_leads.py laufen lassen" }, { status: 503 });
  }
  // #24 Zuschlagsphase: frische Zuschläge (src='award') derselben Branche in dieselbe Liste
  // einspeisen — kein eigener Bereich, eine Phase neben offen/auslaufend. Fehlt die Datei
  // (Award-Export nicht gelaufen), bleibt die Liste einfach ohne Zuschläge.
  const awardsRaw = await loadDataFile(`awards-${branche}.json`);
  if (awardsRaw) {
    try {
      const leads = JSON.parse(json);
      const awards = JSON.parse(awardsRaw);
      if (Array.isArray(leads) && Array.isArray(awards)) {
        return NextResponse.json([...awards, ...leads], {
          headers: { "cache-control": CACHE, ...(etag ? { etag } : {}) },
        });
      }
    } catch { /* fällt auf reine Leads zurück */ }
  }
  return new NextResponse(json, {
    headers: { "content-type": "application/json", "cache-control": CACHE,
               ...(etag ? { etag } : {}) },
  });
}
