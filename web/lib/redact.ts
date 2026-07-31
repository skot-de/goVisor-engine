import "server-only";
import type { Tier } from "@/lib/tier";

/* Premium-Redaktion: für Free-Nutzer werden die echten Analytik-Werte server-seitig durch
 * Platzhalter ersetzt, BEVOR sie den Server verlassen. Der Client blurrt weiterhin (Tease-Optik
 * bleibt), aber per DevTools ist nur der Platzhalter lesbar — kein echter Pro-Wert mehr im DOM.
 * Gibt jeweils eine redigierte KOPIE zurück (mutiert den Route-Cache nicht). Pro → unverändert. */

const RED = 0; // Zahl-Platzhalter (wird beim Free-Blur ohnehin verwischt)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;

/** Premium-Analytik eines einzelnen Lead-Details (marktSegment, buyerProfile-Mix) redigieren. */
export function redactDetail(one: Any, tier: Tier): Any {
  if (tier === "pro" || !one) return one;
  const d = structuredClone(one);
  const ms = d.marktSegment;
  if (ms) {
    for (const k of ["nAwards", "erfolglos", "singleBidder", "top3", "score"]) if (k in ms) ms[k] = RED;
    if (Array.isArray(ms.dominatoren)) ms.dominatoren = [];   // Konkurrenten-Namen sind Pro
    if ("chronic" in ms) ms.chronic = null;
  }
  const bp = d.buyerProfile;
  if (bp && Array.isArray(bp.mix)) bp.mix = bp.mix.map((x: Any) => ({ ...x, pct: RED, n: RED }));
  return d;
}

/** Firmenprofil (#25) redigieren: die Pro-Sektion „Was ausläuft" (expiring) verlässt den Server
 * für Free-Nutzer nicht — sie ist in der UI Pro-badge-gated, und CSS-Blur allein ist DevTools-lesbar.
 * „Kopf an Kopf" ist ohne eigenes Profil ohnehin leer, KPIs/Wo-festsitzt bleiben frei. */
export function redactFirma(p: Any, tier: Tier): Any {
  if (tier === "pro" || !p || p.error) return p;
  const d = structuredClone(p);
  d.expiring = [];              // Pro: auslaufende Verträge der Firma
  return d;
}

/** Marktblöcke (Chancen-Tab) redigieren — Bieterzahlen + Vergabestellen-Aufschlüsselungen raus. */
export function redactMarkt(m: Any, tier: Tier): Any {
  if (tier === "pro" || !m) return m;
  const out = structuredClone(m);
  for (const b of Object.keys(out)) {
    const seg = out[b];
    if (!seg || typeof seg !== "object") continue;
    for (const s of (seg.topStellen || [])) { s.vergaben = RED; s.offen = RED; }
    for (const e of (seg.einstieg || [])) { e.bieter = RED; e.wert = null; }
  }
  return out;
}
