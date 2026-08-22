import { loadDataFile, ausSpeicher, inSpeicher } from "@/lib/dataSource";

/* Feature #25 — vorberechnete Firmenprofile (scripts/export_firma_profiles.py).
 * Serverless-fähig: eine statische, nach identity_id verschlüsselte JSON, einmal geladen
 * und gecacht. Ersetzt im Deploy das On-Demand-Python (firma_profil.py). */

type Profile = Record<string, unknown>;
/* ⚠ KEIN EWIGER SPEICHER MEHR. Vorher hielt eine Modulvariable die geparste Datei bis zum
   Neustart der Instanz fest. Lokal harmlos, im Betrieb aber falsch: die Exporte laufen
   nachts, und eine laufende Instanz hätte bis zum nächsten Deployment die Zahlen von gestern
   ausgeliefert — ohne dass es jemand sieht, denn alte Daten sehen aus wie frische.
   Jetzt unter demselben Regime wie die Rohdateien (Verfallszeit + Byte-Budget). Gespeichert
   wird das GEPARSTE Ergebnis: das Parsen von 39 MB JSON ist teurer als der Abruf. */
export async function loadFirmaProfiles(): Promise<Record<string, Profile>> {
  const fertig = ausSpeicher<Record<string, Profile>>("firma-profiles:geparst");
  if (fertig) return fertig;
  try {
    const raw = await loadDataFile("firma-profiles.json");
    return inSpeicher("firma-profiles:geparst",
                      raw ? (JSON.parse(raw) as Record<string, Profile>) : {}, raw?.length ?? 0);
  } catch {
    return {};
  }
}
