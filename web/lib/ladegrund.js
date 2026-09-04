/* Warum kam nichts zurück — „gibt es nicht" oder „ich komme nicht dran"?
 *
 * WARUM DAS EINE EIGENE DATEI IST, UND WARUM PLAIN JS. Dieselbe Begründung wie bei
 * `etag.js`: `dataSource.ts` trägt `server-only` und ist für `node` unladbar. Eine Regel,
 * die dort steht, kann `web/scripts/pruefe-ladegrund.mjs` nicht prüfen — und ein Test gegen
 * eine Abschrift geht grün, während die benutzte Fassung falsch ist.
 *
 * ⚠ WORUM ES GEHT. `loadDataFile` gab für JEDEN Fehlschlag `null` zurück: Datei nicht da,
 * S3 antwortet 500, Netz weg, Signatur abgelehnt. Die Aufrufer konnten das nicht
 * unterscheiden und machten daraus durchweg ein leeres Ergebnis mit HTTP 200 —
 *
 *     /api/branchen    jede Branche zeigt 0 Leads
 *     /api/plz-geo     die Umkreissuche findet nichts
 *     /api/markt       Marktblöcke leer
 *     /api/strategie   ausdrücklich `{ status: 200 }`
 *     /api/kalender    keine Fristen, für alle Leads
 *
 * Bei unerreichbarem Speicher sieht das Produkt damit aus, als gäbe es nichts zu finden.
 * Das ist die Umkehrung des eigenen Versprechens („Unbekanntes bleibt sichtbar, statt
 * plausibel erfunden zu werden") — und es trifft ausgerechnet die Fristen, nach denen
 * jemand seinen Kalender richtet. Der Kommentar in `dataSource.ts` fordert seit jeher genau
 * diese Unterscheidung; sie war nur nie an den Aufrufer weitergereicht.
 */

/** @typedef {"ok"|"fehlt"|"stoerung"} Ladegrund */

export const OK = "ok";
export const FEHLT = "fehlt";
export const STOERUNG = "stoerung";

/**
 * Der Grund, aus einem Protokoll des Ladeversuchs.
 *
 * ⚠ ZWEI FALLEN, BEIDE IN DIE TEURE RICHTUNG:
 *
 * 1. **404 IST KEINE STÖRUNG.** Der Speicher hat geantwortet, die Datei gibt es dort nicht.
 *    Wer das als Störung wertet, macht aus jedem Lead ohne Kalenderdatei einen Ausfall —
 *    und eine Fehlermeldung, die immer kommt, liest bald niemand mehr.
 * 2. **EIN TREFFER AUF DER PLATTE LÖSCHT DIE STÖRUNG.** Der Rückfall auf die lokale Platte
 *    ist ja der Sinn der Kette. Ist die Datei am Ende da, war der entfernte Fehlschlag
 *    folgenlos — dann `ok`, nicht `stoerung`.
 *
 * @param {{ferngriff?: boolean, status?: number|null, ausnahme?: boolean, platte?: boolean}} p
 *   `ferngriff` — wurde ein entfernter Speicher überhaupt versucht?
 *   `status`    — HTTP-Status der Antwort, `null` wenn keine kam
 *   `ausnahme`  — `fetch` selbst geworfen (Netz, DNS, Zeitgrenze)
 *   `platte`    — hat der Rückfall auf die lokale Platte geliefert?
 * @returns {Ladegrund}
 */
export function grundAus(p) {
  if (p && p.platte) return OK;
  if (!p || !p.ferngriff) return FEHLT;          // reiner Plattenbetrieb: nichts da heisst nichts da
  if (p.ausnahme) return STOERUNG;
  if (p.status === 404) return FEHLT;
  if (typeof p.status === "number" && p.status >= 200 && p.status < 300) return OK;
  if (typeof p.status === "number") return STOERUNG;
  return STOERUNG;                                // kein Status und keine Ausnahme: unerklärt
}

/** Darf der Aufrufer daraus ein leeres Ergebnis machen? Nur wenn es wirklich leer IST. */
export function darfLeerAntworten(grund) {
  return grund !== STOERUNG;
}

/** Einheitlicher Rumpf für den Störfall — überall derselbe Wortlaut. */
export const STOERUNG_ANTWORT = {
  error: "datenspeicher-nicht-erreichbar",
  hinweis: "Die Daten sind gerade nicht abrufbar. Das ist eine Störung, kein leeres Ergebnis.",
};
