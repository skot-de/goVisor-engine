import "server-only";

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

/** Client-IP aus den üblichen Proxy-Headern (Vercel/Reverse-Proxy); Fallback "unknown". */
export function clientIp(req: Request): string {
  const xff = req.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0].trim();
  return req.headers.get("x-real-ip") || "unknown";
}
