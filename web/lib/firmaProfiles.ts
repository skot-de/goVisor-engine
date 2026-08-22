import { loadDataFile } from "@/lib/dataSource";

/* Feature #25 — vorberechnete Firmenprofile (scripts/export_firma_profiles.py).
 * Serverless-fähig: eine statische, nach identity_id verschlüsselte JSON, einmal geladen
 * und gecacht. Ersetzt im Deploy das On-Demand-Python (firma_profil.py). */

type Profile = Record<string, unknown>;
let CACHE: Record<string, Profile> | null = null;

export async function loadFirmaProfiles(): Promise<Record<string, Profile>> {
  if (CACHE) return CACHE;
  try {
    const raw = await loadDataFile("firma-profiles.json");
    CACHE = raw ? (JSON.parse(raw) as Record<string, Profile>) : {};
  } catch {
    CACHE = {};
  }
  return CACHE;
}
