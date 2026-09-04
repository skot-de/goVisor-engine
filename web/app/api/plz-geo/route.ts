import { NextResponse } from "next/server";
import { ladeMitGrund, DATEN_STOERUNG } from "@/lib/dataSource";
import { STOERUNG_ANTWORT } from "@/lib/ladegrund.js";

// PLZ→Koordinate, country-verschachtelt {DE:{plz:[lat,lon,ort]},CH:{…},AT:{…}} für die echte
// Umkreissuche. Geladen über den konfigurierbaren Daten-Loader (lokal oder Object-Storage).
export async function GET() {
  // ⚠ `?? "{}"` WAR HIER DAS TEUERSTE ZEICHEN. Ohne diese Datei liefert die Umkreissuche
  // keine Treffer — und das sah aus wie „in eurem Umkreis gibt es nichts", nicht wie ein
  // Ausfall. Ein leeres Ergebnis ist eine AUSSAGE; die darf nur stehen, wenn sie stimmt.
  const { text, grund } = await ladeMitGrund("plz-geo.json");
  if (grund === DATEN_STOERUNG) {
    return NextResponse.json(STOERUNG_ANTWORT, { status: 503 });
  }
  return new NextResponse(text ?? "{}", {
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}
