import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

/**
 * Zielliste (Admin-Portal, Bereich 4). Liest die Batch-Ausgabe `data/zielliste.csv`
 * (scripts/zielliste.py, Schmerz-Priorisierung S1/S2) direkt per fs — reines Lesen, kein
 * Python-Spawn, kein Schreiben (also keine laeuft_was-Sperre noetig).
 *
 * ⚠ Enthaelt keine Kontaktdaten (die stehen in firmen_suche/Detail); dennoch internes Tool.
 * Gleiche Sperre wie die uebrigen /api/intern-Routen (Middleware istAdmin + Prod-Riegel).
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ROOT = path.resolve(process.cwd(), "..");
const CSV = path.join(ROOT, "data", "zielliste.csv");
function gesperrt() {
  return process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1";
}

function parseCsv(text: string): string[][] {
  const rows: string[][] = []; let row: string[] = [], f = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true;
    else if (c === ",") { row.push(f); f = ""; }
    else if (c === "\r") { /* skip */ }
    else if (c === "\n") { row.push(f); rows.push(row); row = []; f = ""; }
    else f += c;
  }
  if (f.length || row.length) { row.push(f); rows.push(row); }
  return rows;
}

const ZAHL = new Set([
  "score", "wins36", "avg_wert", "volumen_36m", "verlorene_12m", "verlust_volumen",
  "auslauf_n", "auslauf_volumen_6_18m", "s3_unterperformance", "s4_wachstum", "s5_feldbreite",
]);
const SAFE = /^[0-9A-Za-zäöüÄÖÜß .,&'/+-]{1,60}$/;

export async function GET(req: Request) {
  if (gesperrt()) return NextResponse.json({ error: "not found" }, { status: 404 });
  const u = new URL(req.url).searchParams;

  let raw: string;
  try { raw = fs.readFileSync(CSV, "utf8"); }
  catch { return NextResponse.json({ zeilen: [], gesamt: 0, fehlt: true, hinweis: "data/zielliste.csv fehlt, scripts/zielliste.py laufen lassen." }); }

  const grid = parseCsv(raw).filter((r) => r.some((c) => c !== ""));
  if (!grid.length) return NextResponse.json({ zeilen: [], gesamt: 0 });
  const kopf = grid[0];
  let zeilen = grid.slice(1).map((r) => {
    const o: Record<string, string | number> = {};
    kopf.forEach((h, i) => { const v = r[i] ?? ""; o[h] = ZAHL.has(h) && v !== "" ? Number(v) : v; });
    return o;
  });
  const gesamt = zeilen.length;

  const region = (u.get("region") || "").trim().toUpperCase();
  if (region) { if (!/^[A-Z0-9]{1,5}$/.test(region)) return NextResponse.json({ error: "region ungültig" }, { status: 400 }); zeilen = zeilen.filter((z) => String(z.haupt_nuts1 || "").toUpperCase().startsWith(region)); }
  const signal = (u.get("signal") || "").trim();
  if (signal) { if (!/^S[1-5]_[a-z]+$/.test(signal)) return NextResponse.json({ error: "signal ungültig" }, { status: 400 }); zeilen = zeilen.filter((z) => z.dominant_signal === signal); }
  const q = (u.get("q") || "").trim();
  if (q) { if (!SAFE.test(q)) return NextResponse.json({ error: "q ungültig" }, { status: 400 }); const ql = q.toLowerCase(); zeilen = zeilen.filter((z) => String(z.firmenname || "").toLowerCase().includes(ql)); }

  zeilen.sort((a, b) => Number(b.score || 0) - Number(a.score || 0));
  const limit = Math.min(500, Math.max(1, Number(u.get("limit") || 100)));
  const gefiltert = zeilen.length;
  zeilen = zeilen.slice(0, limit);

  // Signal-Verteilung (fuer die Kopf-Kacheln) ueber die gefilterte Menge.
  const verteilung: Record<string, number> = {};
  for (const z of zeilen) { const s = String(z.dominant_signal || "?"); verteilung[s] = (verteilung[s] || 0) + 1; }

  return NextResponse.json(
    { zeilen, gesamt, gefiltert, verteilung, spalten: kopf },
    { headers: { "cache-control": "no-store" } },
  );
}
