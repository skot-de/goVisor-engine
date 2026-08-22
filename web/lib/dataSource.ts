import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { signierterGet } from "@/lib/s3sign";
import { erstelleCache } from "@/lib/dataCache";

/**
 * Lädt eine Web-Daten-Datei (leads-<branche>.json, suppliers.json, doc-text/…) aus dem
 * Objektspeicher ODER von der lokalen Platte. Drei Wege, in dieser Reihenfolge:
 *
 *   1. PRIVATER Speicher — `DATA_S3_ENDPOINT` + Bucket + Schlüssel gesetzt: jeder GET wird
 *      signiert (lib/s3sign.ts). Das ist der empfohlene Betrieb.
 *   2. Öffentliche Basis-URL — nur `DATA_BASE_URL` gesetzt: blankes `fetch`.
 *   3. Lokale Platte — Entwicklung auf diesem Rechner.
 *
 * ⚠ WARUM WEG 2 NICHT DIE VORGABE IST. Unter dieser Basis liegt `suppliers.json` mit den
 * Kontaktdomains von 16.454 Firmen — Felder, die `lib/suppliers.ts` ausdrücklich als „NUR
 * SERVERSEITIG" führt, „sonst sind die Kontaktdomains aller Firmen abgreifbar". Dazu 6.563
 * Dokumentvolltexte und 253 MB LLM-Auswertungen. Ein offener Bucket macht die Ratenbremse
 * auf `/api/entity-search` gegenstandslos: ein einziger GET liefert den ganzen Bestand.
 * Weg 2 bleibt nur, um einen bestehenden offenen Bucket nicht zu brechen.
 *
 * Wer hochlädt: `scripts/upload_web_data.py` (dieselbe Signatur, dort in Python).
 */
/** Zugangsdaten aus der Umgebung, oder `null` wenn kein privater Speicher eingerichtet ist.
 *  Steht hier und nicht in `s3sign.js`, weil DIESE Datei `server-only` trägt: ein Import aus
 *  einer Client-Komponente bricht damit den Build, statt still `undefined` einzusetzen. */
function s3Zugang() {
  const endpunkt = process.env.DATA_S3_ENDPOINT, bucket = process.env.DATA_S3_BUCKET;
  const keyId = process.env.DATA_S3_KEY_ID, secret = process.env.DATA_S3_SECRET;
  if (!endpunkt || !bucket || !keyId || !secret) return null;
  return { endpunkt, bucket, keyId, secret, region: process.env.DATA_S3_REGION || "auto" };
}

/* Zwischenspeicher für den ENTFERNTEN Weg. Der Plattenzugriff bleibt ungepuffert: er ist
   billig, und in der Entwicklung will man nach einem Export sofort die neuen Zahlen sehen,
   nicht zehn Minuten die alten. */
const speicher = erstelleCache({
  maxBytes: Number(process.env.DATA_CACHE_MAX_BYTES) || 256 * 1024 * 1024,
  ttlMs: Number(process.env.DATA_CACHE_TTL_MS) || 10 * 60 * 1000,
});

/** Beliebigen abgeleiteten Wert unter demselben Regime halten (geparste JSON etwa).
 *  `bytes` ist das Gewicht fürs Budget, üblicherweise die Länge des Rohtexts. */
export function ausSpeicher<T>(schluessel: string): T | undefined {
  return speicher.hole(schluessel) as T | undefined;
}
export function inSpeicher<T>(schluessel: string, wert: T, bytes: number): T {
  speicher.setze(schluessel, wert, bytes);
  return wert;
}

export async function loadDataFile(name: string): Promise<string | null> {
  const zugang = s3Zugang();
  if (zugang) {
    const gepuffert = speicher.hole(name);
    if (typeof gepuffert === "string") return gepuffert;
    try {
      const praefix = process.env.DATA_S3_PREFIX?.replace(/^\/+|\/+$/g, "");
      const { url, kopf } = await signierterGet(zugang, praefix ? `${praefix}/${name}` : name);
      const res = await fetch(url, { headers: kopf, cache: "no-store" });
      if (res.ok) {
        const text = await res.text();
        speicher.setze(name, text, text.length);
        return text;
      }
      // 404 ist eine Antwort, kein Fehler: die Datei gibt es dort nicht. Alles andere ist
      // eine Störung, die man sehen muss — sonst fällt sie stumm auf die Platte zurück und
      // ein Deployment liefert alte oder gar keine Daten, ohne dass es jemand merkt.
      if (res.status !== 404) console.error(`[data] ${name}: HTTP ${res.status} vom Speicher`);
    } catch (e) {
      console.error(`[data] ${name}: Speicher nicht erreichbar —`,
                    e instanceof Error ? e.message : e);
    }
  } else {
    const base = process.env.DATA_BASE_URL?.replace(/\/$/, "");
    if (base) {
      const gepuffert = speicher.hole(name);
      if (typeof gepuffert === "string") return gepuffert;
      try {
        const res = await fetch(`${base}/${name}`, { cache: "no-store" });
        if (res.ok) {
          const text = await res.text();
          speicher.setze(name, text, text.length);
          return text;
        }
      } catch {
        /* Netz-/Storage-Fehler → auf Disk-Fallback ausweichen */
      }
    }
  }
  try {
    return await readFile(path.join(process.cwd(), "data", name), "utf-8");
  } catch {
    return null;
  }
}
