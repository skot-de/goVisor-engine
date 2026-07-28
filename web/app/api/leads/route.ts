import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

// Echte Leads aus der lokalen Gold-Schicht (per scripts/export_web_leads.py als JSON
// abgelegt). Dünnes Backend — später durch eine Live-DuckDB-/Supabase-Query ersetzbar,
// ohne dass der Client sich ändert.
const BRANCHEN = new Set(["it", "bau", "medizin", "beratung", "sicherheit", "energie"]);

export async function GET(req: Request) {
  const branche = new URL(req.url).searchParams.get("branche") || "it";
  if (!BRANCHEN.has(branche)) {
    return NextResponse.json({ error: "unbekannter Grundraum" }, { status: 400 });
  }
  try {
    const file = path.join(process.cwd(), "data", `leads-${branche}.json`);
    const json = await readFile(file, "utf-8");
    return new NextResponse(json, {
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  } catch {
    return NextResponse.json({ error: "keine Daten — export_web_leads.py laufen lassen" }, { status: 503 });
  }
}
