/* Success-Fee-Logik (Ticket #6) — reine Funktionen, ohne Provider testbar.
 * Bänder + Flat-Fees aus govisor/pricing.py (7 Stufen). Abgerechnet wird NUR auf echtem Wert;
 * sonst Kunden-Bestätigung mit Anker-Wächter (value_anchor): weicht die Angabe ≥2 Bänder vom
 * Anker ab, geht sie in HITL-Prüfung mit Beleg-Pflicht. Auf einer Schätzung wird nie abgerechnet. */

export const BANDS = ["<100k", "100-250k", "250-500k", "500k-1,3M", "1,3-5M", "5-25M", ">25M"] as const;
export type Band = (typeof BANDS)[number];

const FEE: Record<Band, number> = {
  "<100k": 600, "100-250k": 1200, "250-500k": 2400, "500k-1,3M": 4800,
  "1,3-5M": 9600, "5-25M": 15000, ">25M": 25000,
};
const BOUNDS: [number, Band][] = [
  [100_000, "<100k"], [250_000, "100-250k"], [500_000, "250-500k"], [1_300_000, "500k-1,3M"],
  [5_000_000, "1,3-5M"], [25_000_000, "5-25M"], [Infinity, ">25M"],
];

export function bandForValue(v: number): Band {
  for (const [max, b] of BOUNDS) if (v < max) return b;
  return ">25M";
}
export function bandIndex(b: Band): number { return BANDS.indexOf(b); }

/* Gebühr für ein Band. `source`: echt=voll, imputiert/default=×0.8 (unsichere Wertbasis). */
export function feeForBand(band: Band, source: "echt" | "kunde_bestaetigt" | "geschaetzt"): number {
  const base = FEE[band] ?? 0;
  return source === "echt" ? base : Math.round(base * 0.8);
}

/* Anker-Wächter: weicht die Kundenangabe ≥2 Bänder UNTER den Anker ab → Flag (Beleg-Pflicht). */
export function anchorFlag(claimed: Band, anchor: Band | null): boolean {
  if (!anchor) return false;
  return bandIndex(anchor) - bandIndex(claimed) >= 2;
}

/* Attributions-Gate (Ticket #6 §Success-Fee-Bedingungen). Alles muss erfüllt sein. */
export function feeApplies(opts: {
  plan: string; graceUntil: string | null; entityConfidence: string;
  clickedAt: string | null; awardDate: string;
}): { ok: boolean; grund?: string } {
  if (opts.entityConfidence !== "confirmed") return { ok: false, grund: "Identität nicht bestätigt" };
  if (opts.plan !== "paid") return { ok: false, grund: "kein Pro-Zugang" };
  if (opts.graceUntil && new Date(opts.awardDate) < new Date(opts.graceUntil)) return { ok: false, grund: "Schonfrist" };
  if (!opts.clickedAt) return { ok: false, grund: "Ausschreibung nicht vorab angesehen" };
  const clicked = new Date(opts.clickedAt).getTime();
  const award = new Date(opts.awardDate).getTime();
  if (award < clicked) return { ok: false, grund: "Zuschlag vor Klick" };
  if (award - clicked > 365 * 86400000) return { ok: false, grund: "über 12-Monats-Fenster" };
  return { ok: true };
}
