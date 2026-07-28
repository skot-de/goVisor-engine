import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

// Strategie-Aggregate (Ticket #10). Vorberechnet via scripts/export_strategie.py,
// nicht live aus den Rohdaten — Ladezeit je Sektion < 800 ms (Akzeptanzkriterium #14).
export async function GET() {
  try {
    const file = path.join(process.cwd(), "data", "strategie.json");
    const json = await readFile(file, "utf-8");
    return new NextResponse(json, {
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  } catch {
    return NextResponse.json({}, { status: 200 });
  }
}
