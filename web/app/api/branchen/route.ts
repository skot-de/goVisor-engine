import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

// Lead-Zahl je Grundraum (voller Bestand, nicht nur die geladenen) — für den Workspace-Zähler.
export async function GET() {
  try {
    const file = path.join(process.cwd(), "data", "branchen.json");
    const json = await readFile(file, "utf-8");
    return new NextResponse(json, {
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  } catch {
    return NextResponse.json({}, { status: 200 });
  }
}
