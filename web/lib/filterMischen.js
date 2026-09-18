/* Einen gespeicherten Zustand auf die heutige Form bringen.
 *
 * ⚠ REINES JS, DAMIT EIN WAECHTER DIE ECHTE FUNKTION FAHREN KANN. Dieselbe Begruendung wie
 * bei `filterMarken.js`: eine Wortpruefung auf TypeScript-Quelltext waere wertlos, weil sie
 * gruen bleibt, wenn die Logik daneben kaputtgeht. `web/scripts/pruefe-filtermischen.mjs`
 * ruft diese Datei auf.
 *
 * ⚠ WOZU ES DIESE FUNKTION UEBERHAUPT GIBT. `Adv` waechst — allein am 2026-09-18 kamen
 * Facettenzaehler und das Ausblenden dazu. Ein Filter, den jemand heute speichert, muss in
 * sechs Monaten noch laden. Ohne Mischung passiert das Schlimmste, was passieren kann: der
 * Filter laedt SCHEINBAR sauber und filtert anders. Kein Fehler, keine Meldung.
 *
 * Drei Regeln, und alle drei sind Ablehnungen:
 *   1. Ein Schluessel, den die Vorgabe nicht kennt, wird verworfen (entfernte Facette).
 *   2. Ein Schluessel, der fehlt, behaelt seinen Vorgabewert (neue Facette).
 *   3. Ein Schluessel mit anderem Typ wird verworfen (umgebaute Facette: aus `string`
 *      wurde `string[]`). Der faellt sonst erst beim Rendern auf. */
export function mischen(vorgabe, gespeichert) {
  if (!gespeichert || typeof gespeichert !== "object") return { ...vorgabe };
  const raus = { ...vorgabe };
  for (const k of Object.keys(vorgabe)) {
    if (!(k in gespeichert)) continue;                    // Regel 2
    const alt = vorgabe[k], neu = gespeichert[k];
    if (Array.isArray(alt) !== Array.isArray(neu)) continue;   // Regel 3
    if (!Array.isArray(alt) && alt !== null && neu !== null && typeof alt !== typeof neu) continue;
    raus[k] = neu;
  }
  return raus;                                            // Regel 1 ergibt sich: nur bekannte Schluessel
}
