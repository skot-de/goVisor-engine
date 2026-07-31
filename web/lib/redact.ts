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

/**
 * Strategie/Wettbewerb (#Härtung 4) — abgestufte Teaser-Paywall (Sven-Regeln, provider-Kontext).
 * Für Free verlassen die Pro-Zahlen den Server NICHT (CSS-Blur wäre DevTools-lesbar). Die UI zeigt
 * anhand `_pro:false` die Teaser-Chrome (Locks, „N weitere · Pro", Pro-Gate).
 *  - Felder: Metrik-Zahlen verdeckt (Feld-Identität + 36M-Größe bleiben).
 *  - Wettbewerb: nur erste 3 Anbieter (Gesamtzahl gemerkt), Matrix Pro, Anbieterprofil 3 Zeilen ohne Zahlen.
 *  - Fähigkeiten (Anforderungen) + Bindung (gesperrtes Volumen): komplett Pro.
 *  - Profil/Pipeline/Stellen/Nachbarn/Einstieg: unverändert frei.
 */
export function redactStrategie(map: Any, tier: Tier): Any {
  if (tier === "pro" || !map) return map;
  const out = structuredClone(map);
  for (const br of Object.keys(out)) {
    const s = out[br];
    if (!s || typeof s !== "object") continue;
    s._pro = false;
    for (const f of (s.felder || [])) {          // Zahlen verdecken, Identität/Größe bleiben
      f.vergabenJahr = null; f.trend = null; f.bieterMedian = null; f.kleinstesLos = null; f.buergschaft = null;
    }
    if (s.wettbewerb) {
      const all = s.wettbewerb.anbieter || [];
      s.wettbewerb._anbieterTotal = all.length;
      s.wettbewerb.anbieter = all.slice(0, 3);   // erste 3 Zeilen
      s.wettbewerb.matrix = null;                // Wer-holt-wo-Matrix ist Pro
      const prof = s.wettbewerb.profile || {};   // Anbieterprofil: 3 Zeilen ohne Zahlen
      for (const k of Object.keys(prof))
        prof[k] = (prof[k] || []).slice(0, 3).map((z: Any) => ({ buyer: z.buyer, wins: null, anteil: null, markt: null, ueber: null }));
    }
    s.faehigkeiten = { gated: true };            // Anforderungen: komplett Pro
    s.bindung = { gated: true };                 // gesperrtes Volumen: komplett Pro
  }
  return out;
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
