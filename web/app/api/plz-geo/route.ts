import { NextResponse } from "next/server";
import { ladeMitGrund, DATEN_STOERUNG } from "@/lib/dataSource";
import { STOERUNG_ANTWORT } from "@/lib/ladegrund.js";
import { komprimiert } from "@/lib/komprimiert";

// PLZ→Koordinate, country-verschachtelt {DE:{plz:[lat,lon,ort]},CH:{…},AT:{…}} für die echte
// Umkreissuche. Geladen über den konfigurierbaren Daten-Loader (lokal oder Object-Storage).
export async function GET(req: Request) {
  // ⚠ `?? "{}"` WAR HIER DAS TEUERSTE ZEICHEN. Ohne diese Datei liefert die Umkreissuche
  // keine Treffer — und das sah aus wie „in eurem Umkreis gibt es nichts", nicht wie ein
  // Ausfall. Ein leeres Ergebnis ist eine AUSSAGE; die darf nur stehen, wenn sie stimmt.
  const { text, grund } = await ladeMitGrund("plz-geo.json");
  if (grund === DATEN_STOERUNG) {
    return NextResponse.json(STOERUNG_ANTWORT, { status: 503 });
  }
  // ⚠ Komprimiert, weil Next Route-Handler NICHT komprimiert (gemessen 2026-09-18,
  // s. Kopf von `lib/komprimiert.ts`). 1,46 MB gingen bisher roh raus, und zwar bei
  // jedem Seitenaufruf — die Tabelle wird beim Laden des Explorers einmal geholt.
  //
  // OHNE Zwischenspeicher-Marke: diese Route traegt keinen ETag, und ein Schluessel, der
  // die Daten nicht eindeutig benennt, liefert irgendwann den Stand von gestern aus.
  // Lieber jedes Mal rechnen — bei 1,46 MB sind das wenige Millisekunden.
  return komprimiert(req, text ?? "{}",
    { "content-type": "application/json", "cache-control": "no-store" }, null);
}
