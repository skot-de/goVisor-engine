import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

// Schwere Felder eines Leads (Beschreibung + Vergabestellen-Profil), erst beim Öffnen
// geladen. Hält die Listen-Ladung schlank. Detail-Dateien werden nach Grundraum gecacht.
const BRANCHEN = new Set(["it", "bau", "medizin", "beratung", "sicherheit", "energie"]);
const cache = new Map<string, Record<string, unknown>>();

async function load(branche: string) {
  if (cache.has(branche)) return cache.get(branche)!;
  const file = path.join(process.cwd(), "data", `detail-${branche}.json`);
  const data = JSON.parse(await readFile(file, "utf-8")) as Record<string, unknown>;
  cache.set(branche, data);
  return data;
}

export async function GET(req: Request) {
  const u = new URL(req.url);
  const branche = u.searchParams.get("branche") || "";
  const id = u.searchParams.get("id") || "";
  if (!BRANCHEN.has(branche) || !id) {
    return NextResponse.json({ error: "branche/id fehlt" }, { status: 400 });
  }
  try {
    const all = await load(branche);
    return NextResponse.json(all[id] ?? {});
  } catch {
    return NextResponse.json({ error: "keine Detaildaten" }, { status: 503 });
  }
}
