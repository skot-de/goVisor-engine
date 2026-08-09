import { NextResponse } from "next/server";
import path from "node:path";
import { spawn } from "node:child_process";

/* #27 §7.1 — Profil-Vorbefüllung aus den eigenen Zuschlägen (On-Demand-Python).
 * Wie /api/firma serverseitig lokal: liest die Gold-Parquets über scripts/profil_vorbefuellung.py.
 * Auf Vercel-Serverless (kein Python) nicht verfügbar — dort bleibt das Formular manuell befüllbar. */
export const runtime = "nodejs";
export const maxDuration = 30;

const ROOT = path.resolve(process.cwd(), "..");
const ID_RE = /^(grp|solo):[0-9A-Za-z:._-]{1,120}$/;

function prefillPython(id: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/profil_vorbefuellung.py", id], { cwd: ROOT });
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
  try {
    return NextResponse.json(await prefillPython(id));
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 200) }, { status: 500 });
  }
}
