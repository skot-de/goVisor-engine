import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

// Marktblöcke je Grundraum (aktivste Vergabestellen + einstiegsfreundliche offene
// Ausschreibungen + Eckzahlen) für den Chancen-Tab. Branche-weit, ohne Firmenprofil.
export async function GET() {
  try {
    const file = path.join(process.cwd(), "data", "markt.json");
    const json = await readFile(file, "utf-8");
    return new NextResponse(json, {
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  } catch {
    return NextResponse.json({}, { status: 200 });
  }
}
