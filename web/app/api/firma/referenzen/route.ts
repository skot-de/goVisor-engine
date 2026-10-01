import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { createClient } from "@/lib/supabase/server";

/**
 * Referenzliste der EIGENEN Firma — ihre gewonnenen TED-Zuschlaege (scripts/firma_referenzen.py).
 *
 * ⚠ NUR die eigene, bestaetigte Identitaet des Nutzers (aktives Profil → profiles.identity_id).
 * Bewusst KEIN beliebiges `id` aus der Anfrage: die volle Zuschlags-Historie einer fremden Firma
 * waere Wettbewerbs-Intelligenz und gehoert hinter die Premium-Redaktion, nicht in einen offenen
 * Endpunkt. Hier geht es um „eure Referenzen fuer euer Angebot".
 *
 * ⚠ ON-DEMAND (spawnt Python/DuckDB) — wie /api/firma-Fallback, nicht serverless-ready. Hinter
 * dem Anmeldetor (middleware.ts).
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ROOT = path.resolve(process.cwd(), "..");
const ID_RE = /^(grp|solo):[0-9A-Za-zäöüÄÖÜß:._/-]{1,120}$/;

export async function GET() {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });

  // Eigene Identitaet ueber das aktive Profil aufloesen (wie loadAccount).
  const { data: up } = await sb.from("user_profiles").select("active_profile_id").eq("id", user.id).single();
  const aktiv = (up as { active_profile_id?: string | null } | null)?.active_profile_id ?? null;
  let identity: string | null = null;
  if (aktiv) {
    const { data: p } = await sb.from("profiles").select("identity_id").eq("id", aktiv).single();
    identity = (p as { identity_id?: string | null } | null)?.identity_id ?? null;
  }
  if (!identity || !ID_RE.test(identity)) {
    return NextResponse.json({ referenzen: [], gesamt: 0, grund: "keine bestätigte Firma zugeordnet" });
  }

  const daten = await new Promise<Record<string, unknown>>((resolve, reject) => {
    const proc = spawn("python3", ["scripts/firma_referenzen.py", "--id", identity!], { cwd: ROOT });
    let out = "", err = "";
    proc.stdout.on("data", (d) => (out += d));
    proc.stderr.on("data", (d) => (err += d));
    proc.on("error", reject);
    const t = setTimeout(() => { proc.kill("SIGKILL"); reject(new Error("Zeitgrenze")); }, 60_000);
    proc.on("close", (code) => {
      clearTimeout(t);
      if (code !== 0) return reject(new Error(err.slice(-200) || `exit ${code}`));
      try { resolve(JSON.parse(out.trim().split("\n").filter(Boolean).pop() || "{}")); }
      catch { reject(new Error("Ausgabe nicht lesbar")); }
    });
  }).catch((e) => ({ referenzen: [], fehler: String((e as Error).message).slice(0, 200) }));

  return NextResponse.json(daten, { headers: { "cache-control": "no-store" } });
}
