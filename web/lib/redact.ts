import "server-only";
import type { Tier } from "@/lib/tier";
import { darfAnalyse, darfStrategie } from "@/lib/stufeZuTier";

/* Premium-Redaktion: für Free-Nutzer werden die echten Analytik-Werte server-seitig durch
 * Platzhalter ersetzt, BEVOR sie den Server verlassen. Der Client blurrt weiterhin (Tease-Optik
 * bleibt), aber per DevTools ist nur der Platzhalter lesbar — kein echter Pro-Wert mehr im DOM.
 * Gibt jeweils eine redigierte KOPIE zurück (mutiert den Route-Cache nicht).
 *
 * ── ZWEI SCHWELLEN, NICHT EINE (2026-10-01, Preismodell v1.9 §3) ───────────────────────────
 *
 * ⚠ HIER STAND VIERMAL `if (tier === "pro") return …`. Eine Schwelle fuer zwei bezahlte
 * Stufen heisst: wer Analyse fuer 99 € kauft, bekommt Strategie fuer 349 € mit. Welche
 * Funktion auf welcher Stufe liegt, steht in §3 und NICHT in diesem Kopf — nachgelesen, nicht
 * geraten:
 *
 *   redactDetail   §3.2  Lead-Detail „Markt"/„Vergabestelle"      → +   `darfAnalyse`
 *   redactMarkt    §3.2  Lead-Detail „Markt"                       → +   `darfAnalyse`
 *   redactFirma    §3.5  Firmenprofil-Tab „Angriffspunkte"         → ++  `darfStrategie`
 *   redactStrategie §3.6 ganzer Strategie-Bereich, „keine Ausnahme" → ++  `darfStrategie`
 *
 * ⚠ Gefragt wird ueber `darfAnalyse()`/`darfStrategie()`, nicht per Gleichheitsvergleich.
 * Sonst steht die Schwelle wieder an vier Stellen und die naechste Stufe wird an drei davon
 * vergessen — genau so ist dieser Befund entstanden. */

const RED = 0; // Zahl-Platzhalter (wird beim Free-Blur ohnehin verwischt)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;

/** Premium-Analytik eines einzelnen Lead-Details (marktSegment, buyerProfile-Mix) redigieren. */
export function redactDetail(one: Any, tier: Tier): Any {
  if (darfAnalyse(tier) || !one) return one;
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

/** Firmenprofil (#25) redigieren — der Tab „Angriffspunkte" ist Strategie (§3.5).
 *
 * ⚠ HIER STAND NUR `expiring = []`, UND DER KOMMENTAR NANNTE DAS ABSICHTLICH SO
 * („KPIs/Wo-festsitzt bleiben frei"). §3.5 von v1.9 ordnet aber FUENF Dinge dem Tab
 * „Angriffspunkte" zu, und der traegt `++`: Wo festsitzt · Was auslaeuft · Kopf an Kopf ·
 * weitere Signale · Beobachten. Drei davon tragen Daten, und zwei verliessen den Server
 * trotzdem. Sven am 2026-10-01 auf Vorlage des Befundes: „ja, zieh sits nach."
 *
 * Was jetzt redigiert wird, je Abschnitt der Oberflaeche nachgesehen und nicht geraten:
 *   `sits` + `n_vergabestellen`   Abschnitt „Wo {firma} festsitzt" (der Zaehler steht in
 *                                 dessen Ueberschrift, er gehoert zum selben Abschnitt)
 *   `expiring`                    Abschnitt „Was bei {firma} auslaeuft"
 *   `signale`                     Abschnitt „Weitere Signale"
 *
 * Was BEWUSST frei bleibt, weil §3.5 es der „Uebersicht" (`+`) zuordnet: Identitaet,
 * Zuordnungsguete, `kpi` (Kennzahlen), `felder` (Leistungsfelder), `regionen`.
 *
 * ⚠ UND `kpi.aus18_n` BLEIBT AUSDRUECKLICH DRIN, obwohl es „Laeuft aus ≤ 18 Monate" zaehlt
 * und damit dieselbe Sache wie `expiring` betrifft. Das ist kein Leck, sondern der entworfene
 * Anreiz: §3.5 legt die ZAHL in die Uebersicht und die LISTE (Namen, Fristen) in die
 * Angriffspunkte. Wer die Zahl mitredigiert, nimmt dem Teaser seinen Zweck.
 *
 * ⚠ DIE FORM BLEIBT ERHALTEN, die Werte werden geleert. `signale = { gated: true }` waere
 * kuerzer, aber die Oberflaeche liest `data.signale.bietergemeinschaften` und
 * `t(data.signale.netzwerk)` direkt — ein fehlendes Feld waere dort kein Teaser, sondern ein
 * Absturz. „Kopf an Kopf" braucht nichts: der Abschnitt rendert einen festen Leerzustand. */
export function redactFirma(p: Any, tier: Tier): Any {
  if (darfStrategie(tier) || !p || p.error) return p;
  const d = structuredClone(p);
  d.sits = [];                       // ++ „Wo festsitzt"
  d.n_vergabestellen = RED;          //    dessen Zaehler in der Ueberschrift
  d.expiring = [];                   // ++ „Was auslaeuft" (Namen und Fristen)
  if (d.signale && typeof d.signale === "object") {
    d.signale = { ...d.signale, subcontracting: RED, subcontracting_total: RED,
                  bietergemeinschaften: RED, netzwerk: "" };   // ++ „Weitere Signale"
  }
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
  if (darfStrategie(tier) || !map) return map;
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
  if (darfAnalyse(tier) || !m) return m;
  const out = structuredClone(m);
  for (const b of Object.keys(out)) {
    const seg = out[b];
    if (!seg || typeof seg !== "object") continue;
    for (const s of (seg.topStellen || [])) { s.vergaben = RED; s.offen = RED; }
    for (const e of (seg.einstieg || [])) { e.bieter = RED; e.wert = null; }
  }
  return out;
}
