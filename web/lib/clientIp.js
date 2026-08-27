/* Wer fragt gerade an? — die Herkunft, auf die jede Ratenbremse ihren Zähler stellt.
 *
 * WARUM EINE EIGENE DATEI, UND WARUM PLAIN JS. `rateLimit.ts` trägt `server-only` und ist
 * für `node` damit unladbar. Ein Test müsste die Funktion abschreiben — und ein Test gegen
 * eine Abschrift geht grün, während die benutzte Fassung falsch ist. Genau das ist hier
 * passiert (s. u.), deshalb liegt die Regel wie `s3sign.js` daneben in Plain JS.
 */

/**
 * Client-IP aus den Proxy-Headern. Fallback `"unknown"`.
 *
 * ⚠ **DER LINKESTE WERT IN `x-forwarded-for` GEHÖRT DEM CLIENT, NICHT UNS.** Genau den las
 * die vorige Fassung. `x-forwarded-for` ist eine Liste, an die jeder Proxy hinten anhängt —
 * schickt der Aufrufer den Header selbst mit, steht SEIN Wert vorne und unsere echte
 * Gegenstelle dahinter:
 *
 *     Client sendet:  x-forwarded-for: 10.0.0.1
 *     bei uns an:     x-forwarded-for: 10.0.0.1, 203.0.113.77
 *     gelesen wurde:  10.0.0.1        ← frei wählbar, bei jeder Anfrage neu
 *
 * Ein neuer Wert je Anfrage ist ein neuer Zähler: damit war jede Bremse im Haus mit einer
 * Kopfzeile abschaltbar. Am 2026-08-27 gegen den laufenden Server gemessen, 40 Anfragen bei
 * einem Limit von 30: **alte Fassung 0 abgewiesen, neue Fassung 10**.
 *
 * Das trifft nicht nur die Enumerations-Sperre vor `/api/entity-search` und das Token-Raten
 * vor dem iCal-Feed, sondern auch `/api/lead-docs` — und der Endpunkt gibt Geld aus.
 *
 * Die Reihenfolge ist deshalb: erst Kopfzeilen, die NUR die Plattform setzt und eingehend
 * überschreibt, dann als letzter Ausweg `x-forwarded-for` von RECHTS. Rechts steht, was der
 * nächste Proxy gesehen hat — der Teil, den der Aufrufer nicht bestimmt. Bei genau einem
 * vorgelagerten Proxy ist das die echte Gegenstelle.
 *
 * ⚠ Was das NICHT heilt: der Zähler lebt weiter im Speicher EINER Instanz, und wer über
 * viele IPs verfügt, umgeht jede IP-Bremse ohnehin. Für die teuren Endpunkte gehört die
 * Quote an den angemeldeten Nutzer, nicht an die Herkunft. Das bleibt offen.
 *
 * @param {{ headers: { get(name: string): string | null } }} req
 * @returns {string}
 */
export function clientIp(req) {
  for (const name of ["x-vercel-forwarded-for", "cf-connecting-ip", "x-real-ip"]) {
    const wert = req.headers.get(name)?.trim();
    if (wert) return wert;
  }
  const xff = req.headers.get("x-forwarded-for");
  if (xff) {
    const teile = xff.split(",").map((s) => s.trim()).filter(Boolean);
    if (teile.length) return teile[teile.length - 1];
  }
  return "unknown";
}
