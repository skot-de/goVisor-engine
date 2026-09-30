import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";

/**
 * Datenqualitaet (Admin-Portal, Bereich 2). Kompakte Uebersicht aus den Gold-QA-Parquets —
 * Review-Queue, Quality-Flags, Entity-Merges, Dubletten. Die Web-App hat kein DuckDB, deshalb
 * spawnt die Route den Python-Helfer `scripts/qa_uebersicht.py` (nur lesend, nur Aggregate).
 *
 * ⚠ Gleiche Sperre wie die uebrigen /api/intern-Routen (Middleware istAdmin + Prod-Riegel).
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ROOT = path.resolve(process.cwd(), "..");
const LAND = /^[A-Z]{2,3}$/;

export async function GET(req: Request) {
  if (process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1") {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const sp = new URL(req.url).searchParams;
  const land = (sp.get("country") || "DE").toUpperCase();
  if (!LAND.test(land)) return NextResponse.json({ error: "country ungültig" }, { status: 400 });
  // ?merges=N: statt der Uebersicht die Merge-Kandidatenliste (fuer die Buttons in Bereich 2).
  const args = ["scripts/qa_uebersicht.py", "--country", land];
  const mRaw = sp.get("merges");
  if (mRaw !== null) {
    const n = Number(mRaw);
    if (!Number.isInteger(n) || n < 1 || n > 500) return NextResponse.json({ error: "merges 1..500" }, { status: 400 });
    args.push("--merges", String(n));
  }

  const daten = await new Promise<Record<string, unknown>>((resolve, reject) => {
    const p = spawn("python3", args, { cwd: ROOT });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", reject);
    const t = setTimeout(() => { p.kill("SIGKILL"); reject(new Error("Zeitgrenze")); }, 60_000);
    p.on("close", (code) => {
      clearTimeout(t);
      if (code !== 0) return reject(new Error(err.slice(-300) || `exit ${code}`));
      try { resolve(JSON.parse(out.trim().split("\n").filter(Boolean).pop() || "{}")); }
      catch { reject(new Error("Ausgabe nicht lesbar")); }
    });
  }).catch((e) => ({ fehler: String((e as Error).message).slice(0, 200) }));

  return NextResponse.json(daten, { headers: { "cache-control": "no-store" } });
}
