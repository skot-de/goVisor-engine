import "server-only";

/**
 * Preis der ERWEITERUNG — Preismodell v1.9 §5.2.
 *
 * ⚠ HIER STAND `0` MIT DER BEGRUENDUNG „das Kostenmodell ist offen (Sven, 2026-09-30)". v1.9
 * traegt genau dieses Datum und legt den Preis fest; die Datei wurde geschrieben, bevor die
 * Entscheidung im Dokument stand, und niemand hat sie nachgezogen. Sven am 2026-10-01:
 * „warum ist der seat und profil preis nicht gesetzt? der steht doch im dokument."
 *
 * ⚠ EINE POSITION, NICHT ZWEI. §5.2: „Erweiterung — weiterer Nutzer ODER weiteres
 * Unternehmensprofil", 29 € im Monat, 299 € im Jahr, „gleicher Preis in beiden Paketstufen,
 * linear, keine Staffel". Hier standen ZWEI getrennte Preise (`seat`, `profile`), was die
 * Preistafel von v1.7 war. `art` bleibt im Aufruf erhalten, obwohl der Preis nicht davon
 * abhaengt — die Rechnung zeigt laut §5.2 bewusst ZWEI ZEILEN („3 × weiterer Nutzer",
 * „2 × weiteres Unternehmensprofil") mit demselben Einzelpreis, „damit erkennbar ist, was er
 * freigibt". Abrechnungsseitig ist es ein Preisobjekt mit Menge.
 *
 * ⚠ DER JAHRESPREIS IST KEINE RUNDE ZAHL, SONDERN GERECHNET. §13: Jahrespreis = 10,25 ×
 * Monatspreis, aufgerundet auf 9er-Endung. 10,25 × 29 = 297,25 → 299. Das deckt sich mit der
 * Tafel in §5.2; wer den Monatspreis aendert, rechnet den Jahrespreis mit, statt ihn zu raten.
 *
 * ⚠ KONFIGURIERBAR HEISST UEBERSCHREIBBAR, NICHT UNGESETZT. §13 verlangt „Einzelpreis
 * konfigurierbar, nicht hart codiert". Der Listenpreis aus §5.2 ist deshalb die VORGABE und
 * die Umgebungsvariable die Ausnahme — nicht umgekehrt. Mit `0` als Vorgabe war der Preis
 * nirgends gesetzt (weder in `.env.local` noch dokumentiert) und jeder Kauf scheiterte an
 * einer Meldung, die auf das falsche Hindernis zeigte.
 *
 * ⛔ DAS SETZEN DES PREISES ERMOEGLICHT KEINEN KAUF. `/api/kauf/checkout` antwortet weiter mit
 * 503, jetzt aber an der richtigen Stelle: Stripe ist nicht konfiguriert (kein Schluessel,
 * `stripeEnabled === false`) und die Checkout-Session ist nicht implementiert. Der Preis war
 * das erste von drei Hindernissen, nicht das einzige.
 */

/** Was eine Erweiterung ist. Beide kosten dasselbe (§5.2), die Unterscheidung dient der Rechnung. */
export type Erweiterung = "seat" | "profile";

/** Zahlungstakt. Der Jahrespreis ist der rabattierte (§5.5: 10,25 Monate). */
export type Takt = "monat" | "jahr";

const MONAT_CENTS = Number(process.env.PREIS_ERWEITERUNG_MONAT_CENTS ?? 2900);   // 29,00 €
const JAHR_CENTS = Number(process.env.PREIS_ERWEITERUNG_JAHR_CENTS ?? 29900);    // 299,00 €

export const ERWEITERUNG_CENTS: Record<Takt, number> = {
  monat: Number.isFinite(MONAT_CENTS) && MONAT_CENTS >= 0 ? MONAT_CENTS : 0,
  jahr: Number.isFinite(JAHR_CENTS) && JAHR_CENTS >= 0 ? JAHR_CENTS : 0,
};

/**
 * Einzelpreis in Cent. `art` wird absichtlich NICHT ausgewertet (§5.2: gleicher Preis) und
 * steht nur da, damit der Aufrufer die Rechnungszeile benennen kann.
 */
export function preisCents(art: Erweiterung, takt: Takt = "monat"): number {
  void art;
  return ERWEITERUNG_CENTS[takt];
}

/** Ist ein Preis gesetzt? Bleibt als Riegel, damit ein versehentliches `0` keinen Kauf ueber
 *  0 € buchen kann — nur ist die Vorgabe jetzt der Listenpreis und nicht null. */
export function preisOk(art: Erweiterung, takt: Takt = "monat"): boolean {
  return preisCents(art, takt) > 0;
}

/** Rechnungsbetrag fuer eine Menge, §5.2 „linear, keine Staffel". */
export function betragCents(art: Erweiterung, menge: number, takt: Takt = "monat"): number {
  const n = Math.floor(menge);
  return n > 0 ? preisCents(art, takt) * n : 0;
}
