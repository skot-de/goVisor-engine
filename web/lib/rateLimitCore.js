/* Der Zähler hinter jeder Ratenbremse — festes Zeitfenster, im Arbeitsspeicher.
 *
 * WARUM EINE EIGENE DATEI, UND WARUM PLAIN JS. `rateLimit.ts` trägt `server-only` und ist
 * für `node` unladbar; ein Test müsste die Zählregel abschreiben. Wie bei `clientIp.js` und
 * `s3sign.js` daneben liegt sie deshalb hier, damit
 * `web/scripts/pruefe-ratenbremse.mjs` die ECHTE Fassung prüft.
 *
 * ⚠ WAS DIESER ZÄHLER NICHT IST. Er lebt im Speicher EINER Instanz. Auf mehreren
 * Serverless-Instanzen gilt jedes Limit entsprechend mehrfach, und ein Neustart setzt ihn
 * zurück. Das ist eine Schwelle gegen Schleifen, keine Mauer gegen einen entschlossenen
 * Abgriff. Wer die braucht, braucht einen geteilten Zähler.
 */

/** @type {Map<string, {count: number, resetAt: number}>} */
const store = new Map();

/**
 * Nachsehen, OHNE zu verbrauchen.
 *
 * ⚠ WARUM ES DAS BRAUCHT. `/api/lead-docs` prüfte die Quote ganz am Anfang — vor dem
 * Einlesen der Datei, vor jeder Gültigkeitsprüfung. Eine Anfrage ohne Datei, mit falschem
 * Dateityp oder zu grosser Datei wurde mit 400 abgelehnt und hatte den Zähler trotzdem
 * verbraucht. Weil dort neben der IP-Quote ein GLOBALER Deckel steht (40 Analysen je
 * 10 Minuten), konnte ein angemeldeter Nutzer mit 40 leeren Anfragen die Dokumentanalyse
 * für ALLE anderen zehn Minuten lang sperren — ohne eine einzige Analyse auszulösen.
 *
 * Ein kaputter Client, der stur wiederholt, richtet dasselbe an, ohne es zu wollen.
 *
 * Die Regel dahinter: gezählt wird, was man schützen will. Geschützt wird der teure Lauf,
 * nicht die Anfrage.
 */
export function darfNoch(key, limit) {
  const b = store.get(key);
  if (!b || Date.now() >= b.resetAt) return { ok: true, retryAfter: 0 };
  if (b.count >= limit) {
    return { ok: false, retryAfter: Math.ceil((b.resetAt - Date.now()) / 1000) };
  }
  return { ok: true, retryAfter: 0 };
}

/** Nachsehen UND verbrauchen. Gehört an die Stelle, an der die teure Arbeit beginnt. */
export function rateLimit(key, limit, windowMs) {
  const now = Date.now();
  const b = store.get(key);
  if (!b || now >= b.resetAt) {
    store.set(key, { count: 1, resetAt: now + windowMs });
    return { ok: true, retryAfter: 0 };
  }
  if (b.count >= limit) return { ok: false, retryAfter: Math.ceil((b.resetAt - now) / 1000) };
  b.count++;
  return { ok: true, retryAfter: 0 };
}

/** Nur für Tests: den Zähler leeren. Im Betrieb ruft das niemand. */
export function _leeren() {
  store.clear();
}
