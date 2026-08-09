import { NextResponse } from "next/server";
import path from "node:path";
import { spawn } from "node:child_process";

/* #28 §2 — öffentliche Bilanz-Grundlage (On-Demand-Python wie /api/firma). Sichtbare Gewinne +
 * berechnetes Volumen je Jahr + bearbeitete Vergabestellen. Auf Vercel-Serverless nicht verfügbar. */
export const runtime = "nodejs";
export const maxDuration = 30;

const ROOT = path.resolve(process.cwd(), "..");
const ID_RE = /^(grp|solo):[0-9A-Za-z:._-]{1,120}$/;

function py(id: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/bilanz_public.py", id], { cwd: ROOT });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", reject);
    p.on("close", (code) => {
      if (code !== 0) return reject(new Error(err.slice(-200) || `exit ${code}`));
      try { resolve(JSON.parse(out.trim().split("\n").filter(Boolean).pop() || "{}")); }
      catch { reject(new Error("Ausgabe nicht lesbar")); }
    });
  });
}

export async function GET(req: Request) {
  const id = new URL(req.url).searchParams.get("id") || "";
  if (!ID_RE.test(id)) return NextResponse.json({ error: "ungültige Identität" }, { status: 400 });
  try { return NextResponse.json(await py(id)); }
  catch (e) { return NextResponse.json({ error: String((e as Error).message).slice(0, 200) }, { status: 500 }); }
}
