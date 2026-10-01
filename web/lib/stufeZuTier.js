/**
 * Die vier Stufen (Preismodell v1.9 §2) auf die Zugangsstufe abbilden, plus die zwei Fragen,
 * die der Rest des Codes an sie stellt.
 *
 * ⚠ WARUM DAS HIER IN REINEM JS STEHT UND NICHT IN tier.ts. Nach dem Hausmuster
 * (`filterMarken.js`, `filterMischen.js`): sicherheitskritische Logik gehoert dorthin, wo ein
 * `.mjs`-Waechter die ECHTE Funktion aufrufen kann. Die Alternative waere ein Waechter, der
 * den Quelltext von `tier.ts` mit Regex abtastet — und genau das schlaegt an den eigenen
 * Kommentaren fehl (siehe die Lehre „Waechter messen Prosa statt Code", fuenfmal an einem Tag).
 *
 * ⚠ HIER STAND BIS ZUM 2026-10-01 EINE ABBILDUNG AUF `free|pro`, UND DAS KOSTETE GELD.
 * `redact.ts` prueffte durchgehend `if (tier === "pro") return map` — eine einzige Schwelle fuer
 * zwei bezahlte Stufen. Wer Analyse fuer 99 € kaufte, bekam damit Strategie fuer 349 € mit,
 * obwohl §3.6 den ganzen Strategie-Bereich auf `++` legt („Keine Ausnahme, kein
 * Free-Kontingent"). 250 € Unterschied je Kunde und Monat, unsichtbar, weil kein Test die
 * Stufen unterscheiden KONNTE.
 *
 * ⚠ FAIL-CLOSED. Jeder unbekannte, fehlende oder unlesbare Wert ergibt 'free'. Diese Funktion
 * entscheidet, ob echte Premium-Werte den Server verlassen; im Zweifel verlassen sie ihn nicht.
 */

/**
 * @param {{tier?: string, abo_status?: string, plan_until?: string|null,
 *          trial_ends_at?: string|null} | null | undefined} org
 * @param {number} [jetzt] Vergleichszeitpunkt in ms. Nur fuer Tests; Standard ist jetzt.
 * @returns {'free'|'analyse'|'strategie'}
 */
export function stufeZuTier(org, jetzt = Date.now()) {
  if (!org || typeof org !== "object") return "free";

  const inZukunft = (wert) => {
    if (!wert) return false;
    const t = Date.parse(wert);
    return Number.isFinite(t) && t > jetzt;
  };

  // Testphase: vier Wochen KOMPLETTER Zugang, „alle Funktionen beider Stufen" (§3a) — also
  // 'strategie', nicht 'analyse'. Danach FAELLT der Account auf Free, ohne Sperre. Ohne Datum
  // gilt sie als abgelaufen; wir wissen dann nichts Besseres.
  if (org.tier === "trial") return inZukunft(org.trial_ends_at) ? "strategie" : "free";

  if (org.tier === "analyse" || org.tier === "strategie") {
    // Gekuendigt heisst nicht sofort gesperrt: wer am 2. des Monats kuendigt, hat den Monat
    // bezahlt. `plan_until` (0015) traegt das Ende des bezahlten Zeitraums. ⚠ Die STUFE bleibt
    // dabei erhalten — ein gekuendigtes Strategie-Konto faellt nicht auf Analyse, sondern
    // behaelt bis zum Ende, wofuer es bezahlt hat.
    if (org.abo_status === "gekuendigt") return inZukunft(org.plan_until) ? org.tier : "free";
    return org.tier;
  }
  return "free";                                   // 'free' und alles Unbekannte
}

/**
 * Darf diese Stufe die Analyse-Inhalte sehen (§3.2 Lead-Detail „Markt"/„Vergabestelle",
 * §3.5 Firmenprofil-Uebersicht)? Jede bezahlte Stufe darf, Free nicht.
 * @param {string|null|undefined} tier
 */
export function darfAnalyse(tier) {
  return tier === "analyse" || tier === "strategie";
}

/**
 * Darf diese Stufe die Strategie-Inhalte sehen (§3.6 ganzer Strategie-Bereich, §3.5
 * Firmenprofil-Tab „Angriffspunkte", §3.3 Zuschlag-Bereich)?
 *
 * ⛔ NUR 'strategie'. Das ist der ganze Zweck dieser Datei: `darfAnalyse` und `darfStrategie`
 * sind NICHT dasselbe, und wer sie gleichsetzt, verschenkt die teurere Stufe.
 * @param {string|null|undefined} tier
 */
export function darfStrategie(tier) {
  return tier === "strategie";
}
