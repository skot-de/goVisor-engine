import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";

// Echte Leads aus der Gold-Schicht (per scripts/export_web_leads.py als JSON abgelegt), geladen
// über den konfigurierbaren Daten-Loader (lokal oder Object-Storage via DATA_BASE_URL).
// `ohne` = Vergaben, deren Quelle keinen CPV-Code führt (NetServer-Trefferlisten, Teile
// von DÖE). Seit die CPV-Pflicht aus dem Lead-Bau raus ist, sind sie im Bestand — ohne
// diesen Eintrag antwortet die Route auf sie mit HTTP 400 und die Leads wären zwar
// exportiert, aber für die App unerreichbar. Ein Grundraum ist erst durchgängig, wenn
// Export, Route UND Anzeige ihn kennen.
const BRANCHEN = new Set(["it", "bau", "medizin", "beratung", "sicherheit", "energie",
                          "ohne"]);

export async function GET(req: Request) {
  const branche = new URL(req.url).searchParams.get("branche") || "it";
  if (!BRANCHEN.has(branche)) {
    return NextResponse.json({ error: "unbekannter Grundraum" }, { status: 400 });
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
          headers: { "cache-control": "no-store" },
        });
      }
    } catch { /* fällt auf reine Leads zurück */ }
  }
  return new NextResponse(json, {
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}
