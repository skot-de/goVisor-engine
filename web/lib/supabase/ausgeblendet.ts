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
    if (aus && ctx?.grund) {
      /* ⛔ DER GRUND BRAUCHT EIN UPDATE, KEIN UPSERT — und daran ist er bis zum
         2026-09-20 IMMER gescheitert. Der Ablauf ist zweistufig: der Klick auf das Kreuz
         legt die Zeile OHNE Grund an, die Antwort in der Rueckfrage reicht ihn nach. Mit
         `ignoreDuplicates: true` wird die zweite Schreibung zu `ON CONFLICT DO NOTHING`
         und verpufft — die ganze Rueckfrage war wirkungslos, und niemand haette es
         gemerkt, weil der Klick sich richtig anfuehlt und kein Fehler entsteht.

         ⚠ Ich hatte genau diese Falle in `leadStatus.ts` beschrieben („ein Fehler, der
         beim Ausprobieren funktioniert") und hier nicht gesehen, obwohl ich den
         Nachreichweg selbst gebaut habe. Aufgefallen ist sie erst, als Sven fragte, ob
         wir sagen koennen, wer welchen Lead mit welchem Grund weggeklickt hat. */
      await sb.from("user_lead_hidden")
        .update({ grund: ctx.grund,
                  titel: ctx?.titel ?? null, buyer_name: ctx?.buyer ?? null })
        .eq("user_id", user.id).eq("lead_id", leadId);
    } else if (aus) {
      /* ⚠ HIER IST `ignoreDuplicates` RICHTIG. Wer einen Vorgang erneut ausblendet (etwa
         nach „Doch behalten"), darf einen bereits gegebenen Grund nicht mit `null`
         ueberschreiben. Die Existenz der Zeile ist hier die Aussage, nicht ihr Inhalt. */
      await sb.from("user_lead_hidden").upsert(
        { user_id: user.id, lead_id: leadId,
          titel: ctx?.titel ?? null, buyer_name: ctx?.buyer ?? null, grund: null },
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


/** Die EIGENEN Ausblendungen zu einer Menge von Bekanntmachungen: Kennung → Grund (oder "").
 *
 * ⚠ DAS IST DIE ANDERE HAELFTE DER AKTE. Die nutzeruebergreifende Zahl kommt anonym und
 * erst ab einer Schwelle aus einer statischen Datei; die eigene Sicht darf vollstaendig
 * sein, weil es die eigenen Daten sind — RLS liefert ohnehin nur die eigenen Zeilen.
 * Ohne Anmeldung kommt eine leere Karte, kein Fehler. */
export async function meineAusblendungen(leadIds: string[]): Promise<Map<string, string>> {
  if (!leadIds.length) return new Map();
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return new Map();
    const { data } = await sb.from("user_lead_hidden")
      .select("lead_id,grund,created_at").eq("user_id", user.id).in("lead_id", leadIds);
    return new Map(((data as { lead_id: string; grund: string | null; created_at: string }[]) || [])
      .map((z) => [z.lead_id, z.grund || ""]));
  } catch { return new Map(); }
}
