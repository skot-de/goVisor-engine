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

/** Wie viele Zeichen des Hashes den Bündelnamen bilden: 3 → 16³ = 4.096 Bündel.
 *  ⚠ MUSS mit `export_firma_profiles.BUENDEL_STELLEN` übereinstimmen. Laufen die beiden
 *  auseinander, findet diese Datei gar nichts mehr — und zwar LAUTLOS, weil eine fehlende
 *  Datei genauso aussieht wie eine unbekannte Firma. */
const BUENDEL_STELLEN = 3;

/** Ein Profil. `null`, wenn es die Firma nicht gibt.
 *
 * ⚠ DRITTE FORM, UND BEIDE VORGÄNGER SIND GESCHEITERT. Erst lag alles in EINER Datei
 * `firma-profiles.json`: 67 MB laden, um im Median 1,6 KB zu liefern. Dann eine Datei je
 * Firma: 48.634 Stück, dazu 48.194 unter `suppliers/` — zusammen 64 % von 151.769 Dateien
 * unter `web/data`, für magere 385 MB. `next build` geht den Projektbaum ab und ist bei rund
 * 156.000 Dateien im Node-Heap gestorben (SIGABRT, Stapel in `node::fs::AfterStat`); am
 * 2026-10-05 war die Reserve auf 4.231 Dateien geschrumpft, bei ~16.800 neuen Firmen im Jahr.
 * Seitdem 4.096 Bündel — dieselbe Form und dieselbe Zahl wie in `vorgangsakte.ts`.
 *
 * ⚠ Das Verzeichnis in `loadDataFile` bleibt WÖRTLICH `firma/`. Nie eine Variable daraus
 * machen: `pruefe_verdrahtung.sonde_nutzlast` baut ihre Lesermuster aus diesen Vorlagen und
 * wird sonst blind für jedes tote Ausliefergut. */
export async function loadFirmaProfil(id: string): Promise<Profile | null> {
  if (!id) return null;
  const schluessel = `firma:${id}`;
  const fertig = ausSpeicher<Profile | null>(schluessel);
  if (fertig !== undefined) return fertig;
  try {
    const hash = firmaDateiname(id);
    const roh = await loadDataFile(`firma/${hash.slice(0, BUENDEL_STELLEN)}.json`);
    if (roh) {
      const buendel = JSON.parse(roh) as Record<string, Profile>;
      const p = buendel[hash];
      if (p) return inSpeicher(schluessel, p, roh.length);
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
