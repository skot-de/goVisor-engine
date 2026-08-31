"use client";

/* Übergabe vom Eignungs-Check ins Onboarding.
 *
 * WARUM ES DIESE DATEI GIBT. Am 2026-08-31 den Weg abgegangen: der Eignungs-Check auf der
 * Startseite fragt sechs Dinge ab (Auftragsgrösse, Betriebshaftpflicht, Referenzen,
 * Jahresumsatz, Präqualifikation, ISO 9001), rechnet daraus eine Auswertung — und der Aufruf
 * „N passende offene Vergaben ansehen" war ein blankes `<a href="/onboarding">`. Gemessen:
 * `localStorage` und `sessionStorage` leer, `app/onboarding/page.tsx` hatte NULL Treffer für
 * `buergschaft`, `iso_9001`, `praequalifikation`, `referenz`. Alles weg.
 *
 * ⚠ Teuer ist das, weil genau diese Angaben NICHT aus Vergabedaten ableitbar sind. Das
 * Onboarding baut das Profil aus den Zuschlägen, aber eine Haftpflichtsumme steht in keiner
 * Zuschlagsbekanntmachung. `buergschaft` blieb `null`, und `profileEngine.matchLead` sagte
 * dem Nutzer später „hinterlegt euren Rahmen, dann prüfen wir das" — nach Daten, die er fünf
 * Minuten vorher eingegeben hatte.
 *
 * EINE DATEI FÜR BEIDE SEITEN, damit Schlüssel und Form nicht auseinanderlaufen. Der Check
 * schreibt, das Onboarding liest und verwirft danach.
 */

const SCHLUESSEL = "gv_check_v1";

/** Wie lange eine Antwort gilt. Danach lieber gar nichts übernehmen als etwas Altes:
 *  eine stillschweigend vorbelegte Bürgschaftssumme von letztem Monat ist schlechter als
 *  ein leeres Feld, weil niemand sie mehr hinterfragt. */
const HALTBAR_TAGE = 7;

export type CheckAngaben = {
  v: 1;
  stand: string;                 // ISO-Zeitpunkt der Eingabe
  fach: string | null;           // Fachgebiet-Schlüssel
  region: string;                // Regions-Schlüssel
  volMin: number | null;         // Auftragsgrösse, untere Kante
  volMax: number | null;         // obere Kante; null = nach oben offen
  haftpflicht: number | null;    // Betriebshaftpflicht in €
  referenzen: number | null;     // Anzahl vergleichbarer Referenzen
  umsatz: number | null;         // Jahresumsatz in €
  pq: boolean;
  iso9001: boolean;
  iso14001: boolean;
  /** Welche Nachweisfragen ueberhaupt GESTELLT wurden.
   *
   * ⚠ Der Check zeigt nur die Nachweise, die im gewaehlten Fachgebiet vorkommen — nach
   * ISO 14001 zu fragen, wo es in 0,2 % der Unterlagen steht, waere Zeitraub. Eine nicht
   * gestellte Frage steht oben trotzdem als `false` da, weil das der Vorgabewert ist.
   *
   * Ohne diese Liste wuerde die Uebernahme daraus ein „nein" machen und es als Antwort ins
   * Firmenprofil schreiben. Das legt dem Nutzer Worte in den Mund, und `coverage()` zaehlt
   * es als beantwortet — die Abdeckung stiege, ohne dass jemand etwas gesagt hat. */
  gefragt: string[];
};

export function speichern(a: Omit<CheckAngaben, "v" | "stand">): void {
  try {
    const satz: CheckAngaben = { ...a, v: 1, stand: new Date().toISOString() };
    localStorage.setItem(SCHLUESSEL, JSON.stringify(satz));
  } catch { /* Quota oder privater Modus: die Übergabe ist eine Bequemlichkeit, kein Muss */ }
}

export function lesen(): CheckAngaben | null {
  try {
    const roh = localStorage.getItem(SCHLUESSEL);
    if (!roh) return null;
    const a = JSON.parse(roh) as CheckAngaben;
    // Version prüfen, nicht raten: ein altes Format hier durchzulassen hiesse, mit Feldern
    // zu rechnen, die etwas anderes bedeuten als ihr Name sagt.
    if (a?.v !== 1 || !a.stand) return null;
    const alter = (Date.now() - Date.parse(a.stand)) / 86_400_000;
    if (!(alter >= 0) || alter > HALTBAR_TAGE) return null;
    return a;
  } catch { return null; }
}

export function verwerfen(): void {
  try { localStorage.removeItem(SCHLUESSEL); } catch { /* egal */ }
}

/** Was davon das Profil heute tragen kann — Eingabe für `buildProfile`.
 *
 * ⚠ ES GIBT ZWEI PROFILE, und das ist der Grund, warum diese Funktion so wenig tut.
 * `buildProfile` (profileEngine) traegt `volMin`/`volMax` und faehrt die Relevanz-Stufe;
 * das FIRMENPROFIL (`lib/supabase/unternehmen.ts`) traegt `attributes` und ist das, was
 * `recommendation.js` liest. Hier wird nur das erste bedient.
 *
 * ⚠ `capabilities` liest heute NIEMAND. Beim ersten Anlauf stand hier, die Schluessel
 * seien die aus `REQUIRED_KEYS` von `recommendation.js` — das stimmt dem Namen nach und
 * der Sache nach nicht: `recommendation.js` liest `profile.attributes`, nicht
 * `capabilities`. Der Eintrag bleibt trotzdem, weil er nichts kostet und richtig ist,
 * sobald jemand das Feld verdrahtet; die WIRKSAME Uebernahme der Nachweise laeuft ueber
 * `unternehmen.uebernimmCheck`.
 *
 * Fuer die HOEHE der Haftpflicht, die Referenzanzahl und den Umsatz gibt es im
 * Onboarding-Profil kein Feld. Sie gehen als `checkAngaben` mit, damit niemand ein zweites
 * Mal gefragt werden muss. Nichts wegwerfen, was jemand schon getippt hat. */
export function alsProfilfelder(a: CheckAngaben): {
  volMin: number | null; volMax: number | null; capabilities: string[];
} {
  const capabilities: string[] = [];
  if (a.pq) capabilities.push("praequalifikation");
  if (a.iso9001) capabilities.push("iso_9001");
  if (a.iso14001) capabilities.push("iso_14001");
  if (a.haftpflicht && a.haftpflicht > 0) capabilities.push("berufshaftpflicht");
  return { volMin: a.volMin, volMax: a.volMax, capabilities };
}
