"use client";
import { createClient } from "./client";

/* Lead-Status ↔ user_lead_status (0023). Der dritte Knopf derselben Zeile, neben Stern
 * (`watchlist.ts`) und Ausblenden (`ausgeblendet.ts`), und bis zum 2026-09-19 der einzige
 * ohne Gedaechtnis: `setWf` setzte `l.userStatus` am Objekt, mehr nicht. Wer eine Sitzung
 * lang dreissig Vorgaenge einsortiert hatte, fand nach dem Neuladen dreissig leere Zellen.
 *
 * ⚠ KEIN `ignoreDuplicates` — HIER NICHT. Merkliste und Ausblenden koennen es fahren, weil
 * dort die blosse EXISTENZ der Zeile die Aussage ist. Hier ist es der WERT. Mit
 * `ignoreDuplicates: true` wuerde das erste Setzen ankommen und jede Aenderung danach
 * lautlos verpuffen — ein Fehler, der beim ersten Ausprobieren funktioniert.
 *
 * ⚠ TITEL UND KAEUFER GEHEN MIT, gleiche Begruendung wie in `watchlist.ts`: faellt der
 * Vorgang nach der Frist aus dem Frontend-Export, waere die Zeile sonst nicht mehr deutbar.
 *
 * Ohne Anmeldung ein No-op: der Status bleibt dann UI-Zustand und ist beim naechsten Laden
 * weg. Das ist dieselbe Regel wie bei den beiden Nachbarn. */
export const WF_STATUS = ["interessant", "pruefung", "fragen", "verworfen"] as const;
export type WfStatus = (typeof WF_STATUS)[number];

export async function syncLeadStatus(
  leadId: string, status: string | null,
  ctx?: { titel?: string | null; buyer?: string | null },
) {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return;
    if (status) {
      /* ⚠ Der Check-Constraint in 0023 laesst nur die vier bekannten Werte zu. Ein
         unbekannter Wert wuerde die Zeile ablehnen — hier abfangen, sonst verliert der
         Nutzer die Aenderung, ohne dass ihm jemand etwas sagt. */
      if (!(WF_STATUS as readonly string[]).includes(status)) return;
      await sb.from("user_lead_status").upsert(
        { user_id: user.id, lead_id: leadId, status,
          titel: ctx?.titel ?? null, buyer_name: ctx?.buyer ?? null,
          updated_at: new Date().toISOString() },
        { onConflict: "user_id,lead_id" });
    } else {
      await sb.from("user_lead_status").delete().eq("user_id", user.id).eq("lead_id", leadId);
    }
  } catch { /* no-op: ein Statusklick darf nie eine Fehlermeldung erzeugen */ }
}

/** Die eigenen Einordnungen als lead_id → status. */
export async function loadLeadStatus(): Promise<Map<string, string>> {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return new Map();
    const { data } = await sb.from("user_lead_status")
      .select("lead_id,status").eq("user_id", user.id);
    return new Map(((data as { lead_id: string; status: string }[]) || [])
      .map((z) => [z.lead_id, z.status]));
  } catch { return new Map(); }
}
