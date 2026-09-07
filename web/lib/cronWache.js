/* Wer darf einen Endpunkt auslösen, den sonst nur der Scheduler ruft.
 *
 * WARUM EINE EIGENE DATEI, UND WARUM PLAIN JS. `cronAuth.ts` trägt `server-only` und baut
 * eine `NextResponse` — für `node` unladbar. Wie bei `ladegrund.js` und `rateLimitCore.js`
 * daneben liegt die ENTSCHEIDUNG deshalb hier und die Verpackung in HTTP dort. Geprüft wird
 * damit die echte Regel, nicht eine Abschrift: `web/scripts/pruefe-cronwache.mjs`.
 *
 * ⚠ WARUM DAS ÜBERHAUPT UNTER TEST GEHÖRT. Diese Regel hatte schon einmal genau den Fehler,
 * gegen den sie heute geschrieben ist: fehlte `CRON_SECRET`, wurde die Prüfung ÜBERSPRUNGEN
 * (`if (secret) {…}`) — der Endpunkt verschickt E-Mails, und eine nicht gesetzte
 * Umgebungsvariable machte ihn für jeden zur Schaltfläche. Eine Sicherheitsregel, die bei
 * fehlender Konfiguration aufmacht statt zuzumachen, sieht im Betrieb aus wie eine, die
 * funktioniert — bis zu dem Tag, an dem die Variable fehlt.
 */

export const DURCH = "durch";
/** Kein Geheimnis gesetzt: der Endpunkt ist ABGESCHALTET, nicht offen. → HTTP 503 */
export const UNKONFIGURIERT = "unkonfiguriert";
/** Geheimnis gesetzt, Aufrufer weist sich nicht aus. → HTTP 403 */
export const ABGELEHNT = "abgelehnt";

/**
 * @param {string|undefined|null} secret  Wert von `CRON_SECRET`
 * @param {(name: string) => string|null} kopf  Zugriff auf einen Anfrage-Kopf
 * @returns {"durch"|"unkonfiguriert"|"abgelehnt"}
 */
export function cronUrteil(secret, kopf) {
  // ⚠ Fail-closed. Der leere String zählt hier als „nicht gesetzt": eine Variable, die im
  // Deployment versehentlich leer bleibt, ist kein Geheimnis, und `"" === ""` liesse sonst
  // jeden Aufrufer ohne Kopfzeile durch.
  if (!secret) return UNKONFIGURIERT;
  const lesen = (n) => (kopf ? kopf(n) : null);
  const ok = lesen("x-cron-secret") === secret ||
             lesen("authorization") === `Bearer ${secret}`;
  return ok ? DURCH : ABGELEHNT;
}
