"use client";
import { createClient } from "./client";

/* Merkliste ↔ user_watchlist (Ticket #9). Nur bei aktiver Session; RLS-gebunden. No-op anonym
 * (dann bleibt die Merkliste lokaler UI-Zustand). Die Watchlist ist die Basis der Alerts. */
/* ⚠ WARUM HIER TITEL UND KÄUFER MITGEHEN. Die Merkliste speicherte bis zum 2026-09-01 nur
 * die Kennung. Abgelaufene Vorgänge fliegen aber aus dem Frontend-Export
 * (`export_web_leads.py`: „nicht mehr biet-bar → raus aus der Akquise-Liste"), und damit
 * verschwand ein gemerkter Vorgang am Tag nach der Frist SPURLOS: die Zeile blieb, der
 * Inhalt war weg, und niemand konnte mehr sagen, worum es ging.
 *
 * Genau dieser Moment ist die wertvollste Frage, die wir stellen können („habt ihr
 * mitgeboten?" — die Bieterzahl steht in keiner Bekanntmachung). Ohne Titel und Käufer
 * lässt sie sich nicht stellen.
 *
 * `user_outcomes` macht es seit Ticket #11 genauso und begründet es dort: denormalisierter
 * Kontext, kein Join nötig. Dieselbe Entscheidung, derselbe Grund. */
export async function syncWatchlist(
  leadId: string, add: boolean, ctx?: { titel?: string | null; buyer?: string | null },
) {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return;
    if (add) {
      await sb.from("user_watchlist").upsert(
        { user_id: user.id, lead_id: leadId, auto: false,
          titel: ctx?.titel ?? null, buyer_name: ctx?.buyer ?? null },
        { onConflict: "user_id,lead_id", ignoreDuplicates: true });
    } else {
      await sb.from("user_watchlist").delete().eq("user_id", user.id).eq("lead_id", leadId);
    }
  } catch { /* no-op */ }
}


export type MerkZeile = { lead_id: string; titel: string | null; buyer_name: string | null };

/** Die eigene Merkliste, roh. Fuer die Vorgaenge, die aus dem Export gefallen sind. */
export async function loadWatchlist(): Promise<MerkZeile[]> {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return [];
    const { data } = await sb.from("user_watchlist")
      .select("lead_id, titel, buyer_name").eq("user_id", user.id);
    return (data as MerkZeile[]) || [];
  } catch { return []; }
}
