import { NextResponse } from "next/server";
import path from "node:path";
import { spawn } from "node:child_process";
import { loadFirmaProfiles } from "@/lib/firmaProfiles";

// Feature #25 — Firmenprofil je Identität. Serverless-Pfad: aus der vorberechneten, statischen
// firma-profiles.json (scripts/export_firma_profiles.py). Lokaler Fallback: On-Demand-Python
// (firma_profil.py) — greift nur, wenn die statische Datei fehlt (Dev ohne Vorberechnung).
export const runtime = "nodejs";
export const maxDuration = 30;

const ROOT = path.resolve(process.cwd(), "..");
const ID_RE = /^(grp|solo):[0-9A-Za-z:._-]{1,120}$/;

function profilPython(id: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/firma_profil.py", id], { cwd: ROOT });
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
  if (!ID_RE.test(id)) return NextResponse.json({ error: "ungültige Firmen-ID" }, { status: 400 });

  const profiles = await loadFirmaProfiles();
  const hit = profiles[id];
  if (hit) return NextResponse.json(hit);

  // Statische Datei vorhanden, aber Firma nicht dabei → nicht im erreichbaren Set (keine Zuschläge).
  if (Object.keys(profiles).length > 0) {
    return NextResponse.json({ error: "kein Profil (keine belegten Zuschläge)", id }, { status: 404 });
  }

  // Kein Vorberechnungs-Cache (lokale Entwicklung) → On-Demand-Python.
  try {
    return NextResponse.json(await profilPython(id));
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 200) }, { status: 500 });
  }
}
