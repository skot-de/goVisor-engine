"use client";
import { createClient } from "./client";

/* Ausgeblendete Vorgaenge ↔ user_lead_hidden (0021). Gegenstueck zur Merkliste.
 *
 * ⚠ WARUM DAS MEHR IST ALS EIN AUSBLENDEN. Jede Ablehnung ist ein negatives Beispiel fuer
 * die Passung — und sie kostet einen Klick statt eines Formulars. Deshalb wandern Titel und
 * Kaeufer mit (dieselbe Begruendung wie in `watchlist.ts`): faellt der Vorgang aus dem
 * Frontend-Export, waere die Zeile sonst nicht mehr deutbar.
 *
 * Nur bei aktiver Sitzung; ohne Anmeldung bleibt das Ausblenden reiner UI-Zustand und ist
 * beim naechsten Laden wieder weg. Das ist gewollt: ohne Konto gibt es nichts zu lernen. */
export async function syncAusgeblendet(
  leadId: string, aus: boolean,
  ctx?: { titel?: string | null; buyer?: string | null; grund?: string | null },
) {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return;
    if (aus) {
      await sb.from("user_lead_hidden").upsert(
        { user_id: user.id, lead_id: leadId,
          titel: ctx?.titel ?? null, buyer_name: ctx?.buyer ?? null, grund: ctx?.grund ?? null },
        { onConflict: "user_id,lead_id", ignoreDuplicates: true });
    } else {
      await sb.from("user_lead_hidden").delete().eq("user_id", user.id).eq("lead_id", leadId);
    }
  } catch { /* no-op: Ausblenden darf nie eine Fehlermeldung erzeugen */ }
}

/** Die eigenen Ausblendungen, als Menge von lead_id. */
export async function loadAusgeblendet(): Promise<Set<string>> {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return new Set();
    const { data } = await sb.from("user_lead_hidden").select("lead_id").eq("user_id", user.id);
    return new Set(((data as { lead_id: string }[]) || []).map((z) => z.lead_id));
  } catch { return new Set(); }
}
