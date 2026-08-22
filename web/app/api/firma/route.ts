import { NextResponse } from "next/server";
import path from "node:path";
import { spawn } from "node:child_process";
import { loadFirmaProfiles } from "@/lib/firmaProfiles";
import { getTier } from "@/lib/tier";
import { redactFirma } from "@/lib/redact";

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

  const tier = await getTier();   // Free → Pro-Sektion „Was ausläuft" server-seitig entfernen
  const profiles = await loadFirmaProfiles();
  const hit = profiles[id];
  if (hit) return NextResponse.json(redactFirma(hit, tier));

  // ⚠ AUF EINEM DEPLOYMENT NIE PYTHON. Die Bedingung hatte bis zum 2026-08-22 ein Loch:
  // sie verlangte `Object.keys(profiles).length > 0`. Fehlt die vorberechnete Datei — genau
  // der Fall auf einem Deployment ohne Objektspeicher — ist die Menge LEER, die Bedingung
  // damit falsch, und die Route fiel auf `spawn("python3")` zurück. Dort gibt es kein
  // Python: aus einem Datenproblem wurde ein Exec-Fehler, der wie ein Codefehler aussieht.
  if (process.env.NODE_ENV === "production") {
    return NextResponse.json(
      Object.keys(profiles).length
        ? { error: "kein Profil (keine belegten Zuschläge)", id }
        : { error: "Firmenprofile nicht geladen — DATA_BASE_URL prüfen (docs/web-data-storage.md)" },
      { status: Object.keys(profiles).length ? 404 : 503 });
  }

  try {
    return NextResponse.json(redactFirma(await profilPython(id), tier));
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 200) }, { status: 500 });
  }
}
