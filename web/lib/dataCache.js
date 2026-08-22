/* Ein kleiner Zwischenspeicher für die Datendateien: begrenzt, mit Verfallszeit.
 *
 * WARUM. `loadDataFile` holte jede Datei bei JEDER Anfrage neu (`cache: "no-store"`).
 * Lokal ist das ein Plattenzugriff und folgenlos. Aus einem Objektspeicher sind es 42 MB
 * für `leads-bau.json` und 30 MB für `detail-bau.json` — pro Branchenwechsel im Explorer,
 * pro Nutzer. Das kostet Ladezeit beim Nutzer und Datenverkehr auf der Rechnung.
 *
 * ⚠ WARUM BEGRENZT UND NICHT EINFACH EIN Map. Alle Branchen zusammen sind über 100 MB, mit
 * den Detaildateien deutlich mehr. Ein unbegrenzter Speicher wächst still, bis die Instanz
 * am Speicherlimit stirbt — und zwar nicht bei der Datei, die zu viel war, sondern bei der
 * nächsten harmlosen Anfrage. Deshalb ein Byte-Budget und Verdrängung des am längsten
 * ungenutzten Eintrags.
 *
 * ⚠ WARUM MIT VERFALLSZEIT. Die Exporte laufen nachts. Ein Speicher ohne Verfall liefert bis
 * zum nächsten Neustart die Zahlen von gestern — und niemand sieht es, denn alte Daten sehen
 * aus wie frische. Genau so hat `export_doc_text` hier monatelang den Anschluss verloren.
 *
 * ⚠ BEWUSST PLAIN JS (wie netzMatch.js, s3sign.js): so prüft
 * `scripts/pruefe-datacache.mjs` die ECHTE Verdrängung mit blossem `node`.
 */

/**
 * @param {{maxBytes?: number, ttlMs?: number, jetzt?: () => number}} [opt]
 */
export function erstelleCache(opt = {}) {
  const maxBytes = opt.maxBytes ?? 256 * 1024 * 1024;
  const ttlMs = opt.ttlMs ?? 10 * 60 * 1000;
  const jetzt = opt.jetzt ?? (() => Date.now());
  /** @type {Map<string, {wert: unknown, bytes: number, bis: number}>} */
  const eintraege = new Map();      // Einfügereihenfolge = Nutzungsreihenfolge (s. hole)
  let belegt = 0;

  function entferne(name) {
    const e = eintraege.get(name);
    if (!e) return;
    belegt -= e.bytes;
    eintraege.delete(name);
  }

  return {
    /** Wert oder `undefined`. Ein Treffer wandert ans Ende — das macht die Map zur LRU-Liste. */
    hole(name) {
      const e = eintraege.get(name);
      if (!e) return undefined;
      if (e.bis <= jetzt()) { entferne(name); return undefined; }
      eintraege.delete(name);
      eintraege.set(name, e);
      return e.wert;
    },
    /** Legt ab und verdrängt, bis das Budget wieder passt.
     *  Was allein schon zu gross ist, wird gar nicht erst aufgenommen: sonst räumt eine
     *  einzige Datei den ganzen Speicher leer und liegt danach trotzdem nicht drin. */
    setze(name, wert, bytes) {
      entferne(name);
      if (bytes > maxBytes) return;
      eintraege.set(name, { wert, bytes, bis: jetzt() + ttlMs });
      belegt += bytes;
      for (const alt of eintraege.keys()) {
        if (belegt <= maxBytes) break;
        if (alt !== name) entferne(alt);
      }
    },
    leere() { eintraege.clear(); belegt = 0; },
    stand() { return { eintraege: eintraege.size, belegt, maxBytes, ttlMs }; },
  };
}
