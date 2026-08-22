/* Die Auswahlregel der Partnersuche, als reine Funktion — damit sie prüfbar ist, ohne
 * Datenbank und ohne Sitzung. Der Endpunkt (`app/api/netz/route.ts`) reichert das Ergebnis
 * danach nur noch an (Feld, Größenklasse, Name/Kontakt bei beidseitiger Freigabe).
 *
 * ⚠ BEWUSST PLAIN JS statt TypeScript: so kann `scripts/pruefe-netzmatch.mjs` die Regeln
 * direkt mit `node` durchspielen, ohne Bundler und ohne dass dieses Projekt einen
 * JS-Testläufer bekommt, den es sonst nirgends braucht. Die Regeln sind der Wert dieser
 * Datei, nicht die Sortierung — sie gehören unter einen laufenden Test, nicht unter eine
 * Zusicherung auf den Quelltext.
 *
 * @typedef {{user_id: string, identity_id: string|null, lose: number[],
 *            freigabe: boolean, created_at: string}} NetzZeile
 */

/**
 * @param {NetzZeile} meins
 * @param {NetzZeile[]} alle
 * @returns {{zeile: NetzZeile, ergaenzt: number[]}|null}
 */
export function besterPartner(meins, alle) {
  const meineLose = new Set(meins.lose || []);
  const kandidaten = (alle || [])
    .filter((a) => a.user_id !== meins.user_id)          // man selbst ist kein Partner
    // Gleiche Firmengruppe ist keine Ergänzung. Nur greifen, wenn BEIDE eine Identität
    // tragen — sonst schlösse ein fehlender Wert wildfremde Firmen aus.
    .filter((a) => !(a.identity_id && meins.identity_id && a.identity_id === meins.identity_id))
    .map((a) => ({ zeile: a, ergaenzt: (a.lose || []).filter((n) => !meineLose.has(n)) }))
    // Wer dieselben Lose abdeckt wie ich, ist Wettbewerber, nicht Partner.
    .filter((x) => x.ergaenzt.length > 0)
    // Meiste Ergänzung zuerst; bei Gleichstand die ältere Meldung (wer zuerst da war).
    .sort((x, y) => y.ergaenzt.length - x.ergaenzt.length
      || String(x.zeile.created_at).localeCompare(String(y.zeile.created_at)));
  return kandidaten[0] || null;
}
