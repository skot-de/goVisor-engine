import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";

// PLZ→Koordinate, country-verschachtelt {DE:{plz:[lat,lon,ort]},CH:{…},AT:{…}} für die echte
// Umkreissuche. Geladen über den konfigurierbaren Daten-Loader (lokal oder Object-Storage).
export async function GET() {
  const json = await loadDataFile("plz-geo.json");
  return new NextResponse(json ?? "{}", {
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}
