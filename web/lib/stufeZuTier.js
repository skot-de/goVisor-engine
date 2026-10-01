/**
 * Vier Stufen (Preismodell v1.9 §2) auf die zwei Ebenen der Redaktion abbilden.
 *
 * ⚠ WARUM DAS HIER IN REINEM JS STEHT UND NICHT IN tier.ts. Nach dem Hausmuster
 * (`filterMarken.js`, `filterMischen.js`): sicherheitskritische Logik gehoert dorthin, wo ein
 * `.mjs`-Waechter die ECHTE Funktion aufrufen kann. Die Alternative waere ein Waechter, der
 * den Quelltext von `tier.ts` mit Regex abtastet — und genau das schlaegt an den eigenen
 * Kommentaren fehl (siehe die Lehre „Waechter messen Prosa statt Code", fuenfmal an einem Tag).
 *
 * ⚠ FAIL-CLOSED. Jeder unbekannte, fehlende oder unlesbare Wert ergibt 'free'. Diese Funktion
 * entscheidet, ob echte Premium-Werte den Server verlassen; im Zweifel verlassen sie ihn nicht.
 *
 * @param {{tier?: string, abo_status?: string, plan_until?: string|null,
 *          trial_ends_at?: string|null} | null | undefined} org
 * @param {number} [jetzt] Vergleichszeitpunkt in ms. Nur fuer Tests; Standard ist jetzt.
 * @returns {'free'|'pro'}
 */
export function stufeZuTier(org, jetzt = Date.now()) {
  if (!org || typeof org !== "object") return "free";

  const inZukunft = (wert) => {
    if (!wert) return false;
    const t = Date.parse(wert);
    return Number.isFinite(t) && t > jetzt;
  };

  // Testphase: vier Wochen kompletter Zugang (§3a), danach FAELLT der Account auf Free, ohne
  // Sperre. Ohne Datum gilt sie als abgelaufen — wir wissen dann nichts Besseres.
  if (org.tier === "trial") return inZukunft(org.trial_ends_at) ? "pro" : "free";

  if (org.tier === "analyse" || org.tier === "strategie") {
    // Gekuendigt heisst nicht sofort gesperrt: wer am 2. des Monats kuendigt, hat den Monat
    // bezahlt. `plan_until` (0015) traegt das Ende des bezahlten Zeitraums.
    if (org.abo_status === "gekuendigt") return inZukunft(org.plan_until) ? "pro" : "free";
    return "pro";
  }
  return "free";                                   // 'free' und alles Unbekannte
}
