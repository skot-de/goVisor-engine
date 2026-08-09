"use client";
import { createClient } from "./client";

/* Feature #11 §8.3 — Ergebnismeldungen („die Moat-Tabelle").
 * WICHTIG (§4.3.1 Regel 1 / AC11/AC12): Eine Meldung löst NIE eine Erfolgsprämie aus und hat
 * KEINE Verbindung zu success_fee_charges. Das private Tracking (§4.3.0) nützt ab dem ersten
 * Nutzer OHNE fremden Pool — es ist der Eigenwert, der den Kaltstart auflöst. */

export type OutcomeResult = "won" | "lost" | "cancelled" | "excluded";
export type LossReason = "price" | "quality" | "formal" | "reference" | "unknown";
export type DismissReason = "cpv_mismatch" | "region" | "too_small" | "too_big" | "no_capacity" | "other";

export type UserOutcome = {
  id?: string;
  lead_id: string;
  applied: boolean;
  dismiss_reason?: DismissReason | null;
  result?: OutcomeResult | null;
  rank?: number | null;
  loss_reason?: LossReason | null;
  reported_at?: string;
  usable_for_aggregate?: boolean;
  // Denormalisierter Kontext für die private Bilanz (kein Join nötig, kein Aggregat-Rückfluss):
  titel?: string | null;
  buyer_name?: string | null;
  value_euro?: number | null;
};

export async function loadOutcomes(): Promise<UserOutcome[]> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return [];
  const { data } = await sb.from("user_outcomes").select("*").eq("user_id", user.id).order("reported_at", { ascending: false });
  return (data as UserOutcome[]) || [];
}

// Meldung anlegen/aktualisieren (ein Ergebnis je Lead). Upsert über (user_id, lead_id).
export async function reportOutcome(o: UserOutcome): Promise<{ ok: boolean; error?: string }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false, error: "no-session" };
  // Plausibilität fürs spätere Aggregat (§8.3 usable_for_aggregate): nur entschiedene, beworbene Meldungen.
  const usable = o.applied === true && !!o.result && o.result !== "excluded";
  const row = {
    user_id: user.id, lead_id: o.lead_id, applied: o.applied,
    dismiss_reason: o.applied ? null : (o.dismiss_reason ?? null),
    result: o.applied ? (o.result ?? null) : null,
    rank: o.result === "lost" ? (o.rank ?? null) : null,
    loss_reason: o.result === "lost" ? (o.loss_reason ?? null) : null,
    usable_for_aggregate: usable,
    titel: o.titel ?? null, buyer_name: o.buyer_name ?? null, value_euro: o.value_euro ?? null,
    reported_at: new Date().toISOString(),
  };
  const { error } = await sb.from("user_outcomes").upsert(row, { onConflict: "user_id,lead_id" });
  return { ok: !error, error: error?.message };
}

export async function removeOutcome(leadId: string) {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return;
  await sb.from("user_outcomes").delete().eq("user_id", user.id).eq("lead_id", leadId);
}

/* Private Bilanz (§4.3.0 „Eure eigene Bilanz") — nur eigene Meldungen, kein Marktvergleich.
 * Genau das, was #28 als Grundlage braucht. */
export type Bilanz = {
  gemeldet: number; beworben: number; verworfen: number;
  gewonnen: number; verloren: number; aufgehoben: number;
  quote: number | null;              // gewonnen / (gewonnen+verloren)
  volumen_gewonnen: number;          // Summe value_euro der Gewinne (soweit bekannt)
  volumen_beworben: number;
  offene_meldungen: number;          // beworben + entschieden, aber ohne result
  loss_reasons: Record<string, number>;
};

export function computeBilanz(outcomes: UserOutcome[]): Bilanz {
  const beworbenRows = outcomes.filter((o) => o.applied);
  const gewonnen = beworbenRows.filter((o) => o.result === "won");
  const verloren = beworbenRows.filter((o) => o.result === "lost");
  const aufgehoben = beworbenRows.filter((o) => o.result === "cancelled");
  const entschieden = gewonnen.length + verloren.length;
  const loss_reasons: Record<string, number> = {};
  for (const o of verloren) { const k = o.loss_reason || "unknown"; loss_reasons[k] = (loss_reasons[k] || 0) + 1; }
  return {
    gemeldet: outcomes.length,
    beworben: beworbenRows.length,
    verworfen: outcomes.filter((o) => !o.applied).length,
    gewonnen: gewonnen.length, verloren: verloren.length, aufgehoben: aufgehoben.length,
    quote: entschieden > 0 ? Math.round((100 * gewonnen.length) / entschieden) : null,
    volumen_gewonnen: gewonnen.reduce((s, o) => s + (o.value_euro || 0), 0),
    volumen_beworben: beworbenRows.reduce((s, o) => s + (o.value_euro || 0), 0),
    offene_meldungen: beworbenRows.filter((o) => o.applied && !o.result).length,
    loss_reasons,
  };
}
