import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";

/**
 * Lädt eine Web-Daten-Datei (leads-<branche>.json, branchen.json, plz-geo.json, markt.json,
 * detail-<branche>.json) — aus einem konfigurierbaren Object-Storage ODER von der lokalen Platte.
 *
 * Ziel: die ~88 MB web/data aus Git rausholen. Ist `DATA_BASE_URL` gesetzt (z. B. Vercel Blob,
 * Supabase Storage, S3/CDN-Basis-URL), werden die JSONs von dort geladen; sonst vom lokalen
 * `web/data/`-Verzeichnis (heutiges Verhalten, Fallback). So ist der Umzug zu beliebigem Storage
 * eine Env-Var + ein Upload — kein Code-Wechsel, keine Bindung an einen Anbieter.
 *
 * Migration: 1) web/data zu Storage hochladen, 2) DATA_BASE_URL setzen, 3) web/data gitignoren.
 */
export async function loadDataFile(name: string): Promise<string | null> {
  const base = process.env.DATA_BASE_URL?.replace(/\/$/, "");
  if (base) {
    try {
      const res = await fetch(`${base}/${name}`, { cache: "no-store" });
      if (res.ok) return await res.text();
    } catch {
      /* Netz-/Storage-Fehler → auf Disk-Fallback ausweichen */
    }
  }
  try {
    return await readFile(path.join(process.cwd(), "data", name), "utf-8");
  } catch {
    return null;
  }
}
