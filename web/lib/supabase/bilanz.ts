"use client";
import { loadOutcomes, type UserOutcome } from "./outcomes";
import { loadProfil } from "./unternehmen";

/* Feature #28 §2 — „Unsere Bilanz": verschneidet die öffentlichen (sichtbaren) Zuschläge mit den
 * eigenen Meldungen (user_outcomes, #11) zur ECHTEN Gewinnquote. Öffentlich sichtbar sind nur
 * Gewinne; die Teilnahmen kennt nur der Nutzer. Quote erst ab 10 Meldungen (AC3), Aufschlüsselung
 * ab Fallzahl 5 (AC5), immer mit Fallzahl. */

const MIN_QUOTE = 10;   // §2.1 echte Quote erst ab 10 gemeldeten Teilnahmen
const MIN_CELL = 5;     // §2.2 Aufschlüsselung ab Fallzahl 5

export type PublicBilanz = {
  wins_total: number;
  wins_by_year: { jahr: number; wins: number; volumen: number | null; vol_belegt: number }[];
  buyers_worked: string[];
  error?: string;
};

export type Breakdown = { label: string; n: number; won: number; quote: number };

export type BilanzData = {
  sichtbare_gewinne: number;              // öffentliche Zuschläge
  beworben: number;                       // gemeldete Teilnahmen (applied)
  gewonnen: number; verloren: number;
  echte_quote: number | null;             // gewonnen / beworben, nur ab MIN_QUOTE
  fehlend_bis_quote: number;              // wie viele Meldungen bis MIN_QUOTE
  nach_stelle: Breakdown[];
  nach_groesse: Breakdown[];
  bekannt_vs_neu: { bekannt: Breakdown | null; neu: Breakdown | null };
  verlustgruende: { grund: string; n: number }[];
  volumen_jahre: { jahr: number; wins: number; volumen: number | null }[];
  outcomes_total: number;
};

function bandOf(v?: number | null): string {
  if (v == null) return "ohne Wert";
  if (v < 100_000) return "< 100k €";
  if (v < 250_000) return "100–250k €";
  if (v < 500_000) return "250–500k €";
  if (v < 1_300_000) return "500k–1,3M €";
  if (v < 5_000_000) return "1,3–5M €";
  return "> 5M €";
}
const LOSS_LABEL: Record<string, string> = { price: "Preis", quality: "Qualität", formal: "Formal", reference: "Referenzen", unknown: "unbekannt" };

// Quote je Kategorie: gewonnen / (beworbene Teilnahmen in der Kategorie).
function breakdown(rows: UserOutcome[], keyOf: (o: UserOutcome) => string): Breakdown[] {
  const m = new Map<string, { n: number; won: number }>();
  for (const o of rows) {
    if (!o.applied) continue;
    const k = keyOf(o);
    const e = m.get(k) || { n: 0, won: 0 };
    e.n++; if (o.result === "won") e.won++;
    m.set(k, e);
  }
  return [...m.entries()]
    .filter(([, e]) => e.n >= MIN_CELL)
    .map(([label, e]) => ({ label, n: e.n, won: e.won, quote: Math.round((100 * e.won) / e.n) }))
    .sort((a, b) => b.quote - a.quote);
}

export async function loadBilanz(): Promise<{ data: BilanzData; identityId: string | null } | null> {
  const prof = await loadProfil();
  if (!prof) return null;
  const identityId = prof.ctx.identityId;
  const outcomes = await loadOutcomes();

  let pub: PublicBilanz = { wins_total: 0, wins_by_year: [], buyers_worked: [] };
  if (identityId) {
    try { const r = await fetch(`/api/unternehmen/bilanz?id=${encodeURIComponent(identityId)}`); const d = await r.json(); if (!d.error) pub = d as PublicBilanz; }
    catch { /* öffentliche Bilanz optional (lokal/Serverless) */ }
  }

  const applied = outcomes.filter((o) => o.applied);
  const gewonnen = applied.filter((o) => o.result === "won").length;
  const verloren = applied.filter((o) => o.result === "lost").length;
  const beworben = applied.length;

  // bekannte (schon dort gewonnen) vs. neue Stellen — Namensabgleich gegen buyers_worked.
  const worked = pub.buyers_worked.map((b) => b.toLowerCase());
  const isKnown = (o: UserOutcome) => { const b = (o.buyer_name || "").toLowerCase(); return !!b && worked.some((w) => w.includes(b) || b.includes(w)); };
  const bkRows = applied.filter(isKnown), neuRows = applied.filter((o) => !isKnown(o));
  const bd = (rows: UserOutcome[], label: string): Breakdown | null => {
    if (rows.length < MIN_CELL) return null;
    const won = rows.filter((o) => o.result === "won").length;
    return { label, n: rows.length, won, quote: Math.round((100 * won) / rows.length) };
  };

  const verlustgruende = Object.entries(computeLoss(applied)).map(([grund, n]) => ({ grund: LOSS_LABEL[grund] || grund, n })).sort((a, b) => b.n - a.n);

  return {
    identityId,
    data: {
      sichtbare_gewinne: pub.wins_total,
      beworben, gewonnen, verloren,
      echte_quote: beworben >= MIN_QUOTE ? Math.round((100 * gewonnen) / beworben) : null,
      fehlend_bis_quote: Math.max(0, MIN_QUOTE - beworben),
      nach_stelle: breakdown(applied, (o) => o.buyer_name || "ohne Stelle"),
      nach_groesse: breakdown(applied, (o) => bandOf(o.value_euro)),
      bekannt_vs_neu: { bekannt: bd(bkRows, "bekannte Stellen"), neu: bd(neuRows, "neue Stellen") },
      verlustgruende,
      volumen_jahre: pub.wins_by_year.map((y) => ({ jahr: y.jahr, wins: y.wins, volumen: y.volumen })),
      outcomes_total: outcomes.length,
    },
  };
}

function computeLoss(applied: UserOutcome[]): Record<string, number> {
  const m: Record<string, number> = {};
  for (const o of applied) if (o.result === "lost") { const k = o.loss_reason || "unknown"; m[k] = (m[k] || 0) + 1; }
  return m;
}
