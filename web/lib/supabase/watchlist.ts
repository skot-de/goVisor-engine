"use client";
import { createClient } from "./client";

/* Merkliste ↔ user_watchlist (Ticket #9). Nur bei aktiver Session; RLS-gebunden. No-op anonym
 * (dann bleibt die Merkliste lokaler UI-Zustand). Die Watchlist ist die Basis der Alerts. */
export async function syncWatchlist(leadId: string, add: boolean) {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return;
    if (add) {
      await sb.from("user_watchlist").upsert(
        { user_id: user.id, lead_id: leadId, auto: false },
        { onConflict: "user_id,lead_id", ignoreDuplicates: true });
    } else {
      await sb.from("user_watchlist").delete().eq("user_id", user.id).eq("lead_id", leadId);
    }
  } catch { /* no-op */ }
}
