import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

/**
 * Betriebs-Cockpit — die zwei Dinge, die `/api/intern/lauf` nicht abdeckt:
 * die Sonden-Ampel (aus dem neuesten Waechter-Log) und der LLM-Guthaben-Stand.
 *
 * ⚠ GLEICHE SPERRE wie die uebrigen /api/intern-Routen: enthaelt Betriebswissen
 * (Sondennamen, Guthaben, Pfade) und gehoert nicht ins offene Netz.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const WURZEL = path.resolve(process.cwd(), "..");
const WLOGS = path.join(process.env.HOME || "", "Library", "Logs");

function neuestesWaechterLog(): string | null {
  let dateien: string[];
  try {
    dateien = fs.readdirSync(WLOGS).filter((f) => /^govisor-waechter-.*\.log$/.test(f));
  } catch { return null; }
  if (!dateien.length) return null;
  dateien.sort();
  return path.join(WLOGS, dateien[dateien.length - 1]);
}

/** Die letzte Sonden-Zusammenfassung: „N von M Sonden melden Befunde" + betroffene. */
function sonden() {
  const datei = neuestesWaechterLog();
  if (!datei) return null;
  let zeilen: string[];
  let mtime = 0;
  try {
    zeilen = fs.readFileSync(datei, "utf8").split("\n");
    mtime = fs.statSync(datei).mtimeMs;
  } catch { return null; }
  const kopf = /──\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+(\d+) von (\d+) Sonden melden Befunde/;
  let idx = -1; let m: RegExpMatchArray | null = null;
  for (let i = zeilen.length - 1; i >= 0; i--) {
    const t = zeilen[i].match(kopf);
    if (t) { idx = i; m = t; break; }
  }
  if (idx < 0 || !m) return null;
  const betroffen: string[] = [];
  for (let i = idx + 1; i < zeilen.length; i++) {
    const b = zeilen[i].match(/^\s*⚠\s+(\S+)\s+—/);
    if (b) betroffen.push(b[1]);
    else if (zeilen[i].trim() && !zeilen[i].includes("Protokoll:")) break;
  }
  return { zeit: m[1], gesamt: Number(m[3]), befunde: Number(m[2]),
           ok: Number(m[3]) - Number(m[2]), betroffen, mtimeMs: mtime };
}

function guthaben() {
  try {
    const d = JSON.parse(fs.readFileSync(path.join(WURZEL, "data", ".llm_stand.json"), "utf8"));
    return {
      zeit: d.zeit ?? null, erschoepft: !!d.erschoepft, halt: d.halt ?? null,
      haltGrund: d.halt_grund ?? null, wartend: d.wartend ?? null, fertig: d.fertig ?? null,
      anbieter: (d.anbieter ?? []).map((a: { name: string; modell: string; frei: number }) =>
        ({ name: a.name, modell: a.modell, frei: a.frei })),
    };
  } catch { return null; }
}

export async function GET() {
  if (process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1") {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ erzeugt: new Date().toISOString(), sonden: sonden(), guthaben: guthaben() },
    { headers: { "cache-control": "no-store" } });
}
