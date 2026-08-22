"use client";
import { createClient } from "./client";

/* Account-/Settings-Operationen (Ticket #10). Alles RLS-gebunden über die Session. */

export type AccountRow = {
  id: string; email: string; company_name: string | null;
  identity_id: string | null; entity_confidence: string;
  confirmed_entities: string[]; cpv_fields: string[]; cpv_labels: string[];
  regions: string[]; region_labels: string[]; vol_min: number | null; vol_max: number | null;
  branche: string | null; plan: string;
};
export type AlertSettings = {
  deadline_warning_enabled: boolean; expiry_warning_enabled: boolean;
  award_notify_enabled: boolean; new_leads_digest_enabled: boolean;
  frequency: "instant" | "daily" | "weekly"; timezone: string;
};

export async function loadAccount(): Promise<AccountRow | null> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return null;
  const { data } = await sb.from("user_profiles").select("*").eq("id", user.id).single();
  return (data as AccountRow) ?? null;
}

export async function saveProfileFields(fields: Partial<{
  company_name: string | null; regions: string[]; region_labels: string[];
  vol_min: number | null; vol_max: number | null; branche: string | null;
}>): Promise<{ ok: boolean; error?: string }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false, error: "no-session" };
  const { error } = await sb.from("user_profiles").update(fields).eq("id", user.id);
  return { ok: !error, error: error?.message };
}

const DEFAULT_ALERTS: AlertSettings = {
  deadline_warning_enabled: true, expiry_warning_enabled: false,
  award_notify_enabled: true, new_leads_digest_enabled: false,
  frequency: "daily", timezone: "Europe/Berlin",
};

export async function loadAlertSettings(): Promise<AlertSettings> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return DEFAULT_ALERTS;
  const { data } = await sb.from("user_alert_settings").select("*").eq("user_id", user.id).single();
  return (data as AlertSettings) ?? DEFAULT_ALERTS;
}

export async function saveAlertSettings(s: AlertSettings): Promise<{ ok: boolean }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false };
  const { error } = await sb.from("user_alert_settings").upsert({ user_id: user.id, ...s });
  return { ok: !error };
}


export async function changePassword(pw: string) {
  return createClient().auth.updateUser({ password: pw });
}
export async function changeEmail(email: string) {
  return createClient().auth.updateUser({ email });   // löst Re-Verifikation aus
}

/* GDPR-Export (Art. 20) — clientseitig aus den eigenen (RLS-gelesenen) Daten gebündelt. */
export async function gdprExport(): Promise<Record<string, unknown> | null> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return null;
  const [profile, watchlist, interactions] = await Promise.all([
    sb.from("user_profiles").select("*").eq("id", user.id).single(),
    sb.from("user_watchlist").select("*").eq("user_id", user.id),
    sb.from("user_lead_interactions").select("*").eq("user_id", user.id),
    // Hier stand bis zum 2026-08-22 eine vierte Abfrage auf `success_fee_charges`. Sie
    // BLIEB bewusst stehen, nachdem die Erfolgsprämie gestrichen war: eine Auskunft, die
    // eine Datenkategorie stillschweigend weglässt, ist falsch, solange die Kategorie noch
    // existiert. Mit 0012 ist die Tabelle weg (sie war leer, 0 Zeilen, nachgezählt) — es
    // gibt nichts mehr auszukünften, und die Abfrage würde nur noch einen Fehler liefern.
  ]);
  // Anforderung protokollieren (Ticket #10 §5)
  await sb.from("user_data_export").insert({ user_id: user.id, status: "ready" });
  return {
    exportiert_am: new Date().toISOString(),
    profil: profile.data, merkliste: watchlist.data,
    interaktionen: interactions.data,
  };
}
