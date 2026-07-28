import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";

// Marktblöcke je Grundraum (aktivste Vergabestellen + einstiegsfreundliche offene
// Ausschreibungen + Eckzahlen) für den Chancen-Tab. Geladen über den konfigurierbaren Loader.
export async function GET() {
  const json = await loadDataFile("markt.json");
  return new NextResponse(json ?? "{}", {
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}
