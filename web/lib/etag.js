/* Wie aus Datei-Marken ein `ETag` wird.
 *
 * WARUM EINE EIGENE DATEI, UND WARUM PLAIN JS. Die Regel ist kurz und hat genau eine Falle,
 * die teuer ist (s. u.). `dataSource.ts` trägt `server-only` und ist für `node` unladbar;
 * eine Regel, die dort steht, kann `web/scripts/pruefe-etag.mjs` nicht prüfen — und ein Test
 * gegen eine Abschrift geht grün, während die benutzte Fassung falsch ist.
 */

/**
 * Ein `ETag` aus mehreren Quell-Marken, oder `null`.
 *
 * ⚠ DIE FALLE: eine fehlende Marke darf NICHT durch einen festen Ersatzwert gefüllt werden,
 * wenn sie die FÜHRENDE Quelle betrifft. Sonst entsteht eine Kennung, die stehen bleibt,
 * während sich die Daten bewegen — der Browser bekäme dann dauerhaft `304` und zeigte alte
 * Zahlen als frisch. Bei einem Produkt, das mit Fristen wirbt, ist das der schlimmste
 * denkbare Fehler dieser Ecke.
 *
 * Deshalb: fehlt die erste Marke, gibt es keinen ETag. Eine fehlende NEBEN-Quelle (die
 * Zuschläge etwa, die es nicht für jeden Grundraum gibt) ist dagegen ein legitimer Zustand
 * und wird als `0` mitgeführt — sie muss im ETag stehen, damit ein erster Zuschlag den
 * Zwischenspeicher bricht.
 *
 * @param {string} raum   Kennung des Grundraums, damit zwei Branchen nie denselben ETag haben
 * @param {(string|null|undefined)[]} marken  führende Marke zuerst
 * @returns {string|null}
 */
export function etagAus(raum, marken) {
  if (!Array.isArray(marken) || marken.length === 0) return null;
  const [fuehrend, ...weitere] = marken;
  if (!fuehrend) return null;
  const teile = [raum, fuehrend, ...weitere.map((m) => m || "0")];
  return `"${teile.join("-")}"`;
}

/** Darf mit `304` geantwortet werden? Nur bei einem ETag, der auch wirklich einer ist. */
export function unveraendert(etag, ifNoneMatch) {
  if (!etag || !ifNoneMatch) return false;
  // ⚠ Ein Client darf mehrere senden, und ein Proxy darf ein `W/` voranstellen. Beides
  // ignorieren waere ein stiller Cache-Verlust: der Browser haette die Daten, bekaeme sie
  // aber trotzdem noch einmal.
  return ifNoneMatch
    .split(",")
    .map((s) => s.trim().replace(/^W\//, ""))
    .includes(etag);
}
