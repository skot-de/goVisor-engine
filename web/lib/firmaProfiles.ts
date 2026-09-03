import { createHash } from "crypto";
import { loadDataFile, ausSpeicher, inSpeicher } from "@/lib/dataSource";

/* Feature #25 — vorberechnete Firmenprofile (scripts/export_firma_profiles.py).
 *
 * ⚠ EIN PROFIL JE DATEI, NICHT EINE SAMMELDATEI.
 *
 * Bis zum 2026-08-25 lud diese Datei `firma-profiles.json` KOMPLETT — 67 MB, 38.307
 * Profile — und beide Verbraucher holten daraus GENAU EINES heraus:
 * `/api/firma` per `profiles[id]`, `/api/netz` per `profile[a.identity_id]`. Im Median ist
 * ein Profil 1,6 KB gross. Es wurde also rund das Vierzigtausendfache dessen geladen, was
 * gebraucht wurde, und zwar bei jedem Kaltstart einer Instanz.
 *
 * Dieselbe Form wie `doc-analysis/<id>.json`, das am 2026-08-22 aus demselben Grund
 * aufgeteilt wurde. */

type Profile = Record<string, unknown>;

/** Firmenschlüssel → Dateiname. MUSS mit `export_firma_profiles.dateiname` übereinstimmen.
 *
 * ⚠ Hash statt der sonst üblichen Säuberung `[^A-Za-z0-9_-]` → "". Firmenschlüssel sehen so
 * aus: `solo:id:112.766h` und `solo:id:112766h` — gesäubert wären BEIDE `soloid112766h`.
 * Gemessen über 38.307 Schlüssel: drei solche Kollisionen, sechs Firmen betroffen. Eine
 * hätte die andere überschrieben, und zwar lautlos. */
export function firmaDateiname(id: string): string {
  return createHash("sha1").update(id, "utf8").digest("hex");
}

/** Ein Profil. `null`, wenn es die Firma nicht gibt. */
export async function loadFirmaProfil(id: string): Promise<Profile | null> {
  if (!id) return null;
  const schluessel = `firma:${id}`;
  const fertig = ausSpeicher<Profile | null>(schluessel);
  if (fertig !== undefined) return fertig;
  try {
    const roh = await loadDataFile(`firma/${firmaDateiname(id)}.json`);
    if (roh) {
      const p = JSON.parse(roh) as Profile;
      return inSpeicher(schluessel, p, roh.length);
    }
  } catch {
    /* faellt auf null zurueck — die Route unterscheidet das ueber `firmaBestand` */
  }
  return null;
}

/* ⚠ HIER STAND EIN RUECKFALL AUF `firma-profiles.json`, ENTFERNT AM 2026-09-03.
 *
 * Er sollte den Uebergang absichern, solange im Objektspeicher noch keine `firma/`-Dateien
 * lagen — und kostete dafuer 67,6 MB, die jede Nacht geschrieben und hochgeladen wurden.
 * Gemessen an diesem Tag: `firma/` fuehrt alle 38.386 Profile, KEIN einziges stand nur in
 * der Sammeldatei. Der Uebergang war vorbei, das Netz darunter nicht mehr.
 *
 * Was an seine Stelle tritt, ist keine Luecke: fehlt eine Datei, liefert `loadFirmaProfil`
 * `null`, und `/api/firma` unterscheidet ueber `firmaBestand()` weiter zwischen „diese
 * Firma hat kein Profil" (404) und „die Profile sind gar nicht geladen" (503). Genau diese
 * Unterscheidung war der Grund, aus dem `firma-stand.json` eingefuehrt wurde. */

/** Wie viele Profile der Datenspeicher fuehrt — `null`, wenn er sie gar nicht hat.
 *
 * Trennt „diese Firma hat kein Profil" von „die Profile fehlen". Kostet 100 Byte statt der
 * 67 MB, die dieselbe Frage vorher beantwortet haben. */
export async function firmaBestand(): Promise<number | null> {
  const gepuffert = ausSpeicher<number | null>("firma:bestand");
  if (gepuffert !== undefined) return gepuffert;
  try {
    const roh = await loadDataFile("firma-stand.json");
    const n = roh ? (JSON.parse(roh) as { n?: number }).n ?? null : null;
    return inSpeicher("firma:bestand", n, 32);
  } catch {
    return null;
  }
}
