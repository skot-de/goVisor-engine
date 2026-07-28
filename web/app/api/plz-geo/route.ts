import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

// PLZ→Koordinate-Tabelle {plz: [lat, lon, ort]} für die echte Umkreissuche. Einmal vom
// Client geladen und dort gehalten; die getippte PLZ wird nachgeschlagen, dann filtert
// das Frontend die Leads per Haversine gegen ihre lat/lon. ~10.813 Einträge, ~450 KB.
export async function GET() {
  try {
    const file = path.join(process.cwd(), "data", "plz-geo.json");
    return new NextResponse(await readFile(file, "utf-8"), {
      headers: { "content-type": "application/json", "cache-control": "public, max-age=86400" },
    });
  } catch {
    return NextResponse.json({}, { status: 200 });
  }
}
