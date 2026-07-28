/* Alert-Logik (Ticket #9) — reine Funktion, damit sie ohne Cron/Provider testbar ist.
 * Primär: „Angebotsfrist naht" (14/3 Tage vor Frist, nur offene Leads). Sekundär: „Vertrag
 * läuft aus" (90/30 Tage, nur wo Ende ECHT ist — §9: kein Countdown auf geschätztem Ende). */

export type AlertType = "deadline_14d" | "deadline_3d" | "expiry_90d" | "expiry_30d";
export type LeadTiming = {
  id: string; titel?: string; src?: string;      // 'f02'=offen, 'auslauf'=Vertragsende
  tage?: number | null;                            // Tage bis Angebotsfrist
  endTage?: number | null;                         // Tage bis Vertragsende
  endeEcht?: boolean;                              // Vertragsende belegt (nicht geschätzt)
};
export type WatchState = { deadline_14d_sent: boolean; deadline_3d_sent: boolean; expiry_warn_sent: boolean };
export type AlertPrefs = { deadline_warning_enabled: boolean; expiry_warning_enabled: boolean };
export type DueAlert = { type: AlertType; leadId: string; titel: string; days: number };

export function dueAlerts(lead: LeadTiming, w: WatchState, prefs: AlertPrefs): DueAlert[] {
  const out: DueAlert[] = [];
  const titel = lead.titel || lead.id;

  // Primär: Angebotsfrist (nur offene Ausschreibungen mit Frist in der Zukunft)
  if (prefs.deadline_warning_enabled && lead.src === "f02" && lead.tage != null && lead.tage >= 0) {
    // Fenster diskret: ≤3 Tage = 3-Tage-Alert; 4–14 Tage = 14-Tage-Alert. Ein Lead 1 Tag vor
    // Frist darf keinen „14 Tage"-Alert nachziehen — deshalb explizite Untergrenze im 14er-Zweig.
    if (lead.tage <= 3 && !w.deadline_3d_sent) out.push({ type: "deadline_3d", leadId: lead.id, titel, days: lead.tage });
    else if (lead.tage > 3 && lead.tage <= 14 && !w.deadline_14d_sent) out.push({ type: "deadline_14d", leadId: lead.id, titel, days: lead.tage });
  }

  // Sekundär: Vertragsende — NUR wo das Ende belegt ist (kein Alarm auf Schätzung)
  if (prefs.expiry_warning_enabled && lead.endeEcht && lead.endTage != null && lead.endTage >= 0 && !w.expiry_warn_sent) {
    if (lead.endTage <= 30) out.push({ type: "expiry_30d", leadId: lead.id, titel, days: lead.endTage });
    else if (lead.endTage <= 90) out.push({ type: "expiry_90d", leadId: lead.id, titel, days: lead.endTage });
  }
  return out;
}

// Welche „*_sent"-Flags nach dem Senden gesetzt werden (dedupliziert weitere Sends).
export function sentFlagFor(t: AlertType): keyof WatchState {
  if (t === "deadline_3d") return "deadline_3d_sent";
  if (t === "deadline_14d") return "deadline_14d_sent";
  return "expiry_warn_sent";
}

export function alertText(a: DueAlert): { betreff: string; zeile: string } {
  const m: Record<AlertType, string> = {
    deadline_3d: `Angebotsfrist in ${a.days} Tag(en)`,
    deadline_14d: `Angebotsfrist in ${a.days} Tagen`,
    expiry_30d: `Vertrag läuft in ${a.days} Tagen aus`,
    expiry_90d: `Vertrag läuft in ${a.days} Tagen aus`,
  };
  return { betreff: `goVisor: ${m[a.type]} — ${a.titel.slice(0, 60)}`, zeile: `${m[a.type]}: ${a.titel}` };
}
