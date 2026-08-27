import "server-only";
import { clientIp } from "./clientIp";

/**
 * Einfacher In-Memory-Fixed-Window-Rate-Limiter — Kosten-/Abuse-Bremse für teure Endpunkte
 * (LLM-Dokumentanalyse). Keine externe Abhängigkeit; pro Serverless-Instanz gültig (bewusst
 * einfach für die Pre-Launch-Phase — eine verteilte, exakte Quote gehört an den User/das Billing,
 * wenn PAYWALL_ENFORCED live geht, s. govisor/docsafety.py FREE_ANALYSES_PER_MONTH).
 */
type Bucket = { count: number; resetAt: number };
const store = new Map<string, Bucket>();

export function rateLimit(key: string, limit: number, windowMs: number): { ok: boolean; retryAfter: number } {
  const now = Date.now();
  const b = store.get(key);
  if (!b || now >= b.resetAt) {
    store.set(key, { count: 1, resetAt: now + windowMs });
    return { ok: true, retryAfter: 0 };
  }
  if (b.count >= limit) return { ok: false, retryAfter: Math.ceil((b.resetAt - now) / 1000) };
  b.count++;
  return { ok: true, retryAfter: 0 };
}

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
