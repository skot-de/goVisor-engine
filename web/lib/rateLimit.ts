import "server-only";
import { clientIp } from "./clientIp";
import { rateLimit } from "./rateLimitCore";

/**
 * Einfacher In-Memory-Fixed-Window-Rate-Limiter — Kosten-/Abuse-Bremse für teure Endpunkte
 * (LLM-Dokumentanalyse). Keine externe Abhängigkeit; pro Serverless-Instanz gültig (bewusst
 * einfach für die Pre-Launch-Phase — eine verteilte, exakte Quote gehört an den User/das Billing,
 * wenn PAYWALL_ENFORCED live geht, s. govisor/docsafety.py FREE_ANALYSES_PER_MONTH).
 */
/* ⚠ Der Zaehler liegt in `lib/rateLimitCore.js` — Plain JS, aus demselben Grund wie
 * `clientIp.js`: diese Datei traegt `server-only` und ist fuer `node` unladbar, ein Test
 * muesste die Zaehlregel abschreiben. `darfNoch` sieht nach OHNE zu verbrauchen; das
 * braucht `/api/lead-docs`, wo eine ungueltige Anfrage sonst die Quote fuer alle
 * verbraucht, ohne eine einzige Analyse auszuloesen. */
export { rateLimit, darfNoch } from "./rateLimitCore";

/* ⚠ Die Herkunft liegt in `lib/clientIp.js` — Plain JS, damit `node` sie laden und
 * `web/scripts/pruefe-herkunft.mjs` die ECHTE Fassung pruefen kann. Diese Datei traegt
 * `server-only` und waere fuer einen Test unerreichbar; er muesste die Regel abschreiben,
 * und ein Test gegen eine Abschrift geht gruen, waehrend die benutzte Fassung falsch ist.
 * Genau dieser Fehler stand hier: der linkeste `x-forwarded-for`-Wert ist frei waehlbar. */
export { clientIp };

/**
 * Fertige Bremse für einen Endpunkt: prüft und liefert im Zweifel gleich die 429-Antwort.
 * Spart die immer gleichen fünf Zeilen je Route — und sorgt dafür, dass niemand den
 * `retry-after`-Header vergisst, an dem sich anständige Clients orientieren.
 *
 * ⚠ WAS DIESE BREMSE NICHT IST. Der Zähler lebt im Arbeitsspeicher EINER Instanz. Auf
 * mehreren Serverless-Instanzen gilt das Limit entsprechend mehrfach, und ein Neustart
 * setzt ihn zurück. Das ist eine Schwelle gegen Schleifen, keine Mauer gegen einen
 * entschlossenen Abgriff. Wer die wirklich braucht, braucht einen geteilten Zähler.
 *
 * @returns die 429-Antwort, oder `null` wenn die Anfrage durchdarf.
 */
export function bremse(req: Request, name: string, limit: number, windowMs: number) {
  const rl = rateLimit(`${name}:${clientIp(req)}`, limit, windowMs);
  if (rl.ok) return null;
  return new Response(JSON.stringify({ error: "zu viele Anfragen" }), {
    status: 429,
    headers: { "content-type": "application/json", "retry-after": String(rl.retryAfter) },
  });
}
