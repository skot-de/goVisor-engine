"use client";
import { loadProfile, saveProfile } from "@/lib/supabase/auth";
import { buildProfile } from "@/lib/profileEngine";
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
  if (!data) return null;
  // ⚠ Gibt es ein aktives Profil (Migration 0024/0025), ueberlagern dessen Such-/Identitaets-
  // spalten die vom Konto — sonst zeigte /settings die Werte des ersten Profils statt des
  // umgeschalteten. Tolerant: fehlt die Spalte (vor der Migration), bleibt es beim Konto.
  const aktiv = (data as { active_profile_id?: string | null }).active_profile_id ?? null;
  if (aktiv) {
    const { data: p } = await sb.from("profiles")
      .select("identity_id,confirmed_entities,cpv_fields,cpv_labels,regions,region_labels,vol_min,vol_max,branche")
      .eq("id", aktiv).single();
    if (p) Object.assign(data, p);
  }
  return data as AccountRow;
}

/**
 * Profilfelder aus `/settings` speichern.
 *
 * ⚠ HIER STAND EIN REINES SPALTEN-UPDATE, UND DAS WAR EIN STILLER DATENVERLUST.
 *
 * `user_profiles` haelt dieselben Angaben zweimal: als Spalten (`vol_min`, `regions`, …)
 * und im `profile`-jsonb (`volMin`, `regions`, …). Die Spalten liest NUR `/settings`
 * selbst, um sein eigenes Formular zu fuellen. Die Passung liest `loadProfile()`, und das
 * liest ausschliesslich den Blob.
 *
 * Wer also in `/settings` seine Wertspanne oder seine Regionen aenderte, schrieb in
 * Felder, die kein Treffer je ansieht. Die Seite meldete dazu „Profil gespeichert, wirkt
 * beim naechsten Laden auf die Relevanz." — ein Versprechen, das der Code nicht hielt.
 *
 * Nachgewiesen am 2026-09-17 an der Datenbank: ein Profil trug `vol_min` 2.000.000 und
 * `vol_max` 10.000.000 in den Spalten und `null`/`null` im Blob. Fuer die Passung hatte
 * dieser Nutzer keine Wertgrenze.
 *
 * ⚠ DIE LOESUNG IST NICHT, BEIDES ZU SCHREIBEN, sondern EINEN Schreibweg zu haben.
 * Zwei Schreiber auf dieselbe Angabe laufen auseinander — das ist keine Prognose, es ist
 * hier bereits gemessen worden. `saveProfile` schreibt Blob UND Spalten in einem Zug und
 * bewahrt dabei die #27-Eignungsangaben; diese Funktion reicht nur noch dorthin durch.
 */
export async function saveProfileFields(fields: Partial<{
  company_name: string | null; regions: string[]; region_labels: string[];
  vol_min: number | null; vol_max: number | null; branche: string | null;
}>): Promise<{ ok: boolean; error?: string }> {
  // Der Blob ist die Wahrheit (s. `loadProfile`). Fehlt er — Konto ohne Onboarding —, ist
  // ein leeres Grundprofil der richtige Anfang; `buildProfile` fuellt jedes Feld mit einem
  // Vorgabewert, sonst stirbt `matchLead` spaeter an einem fehlenden Array.
  const vorher = (await loadProfile()) ?? buildProfile({});
  const patch: Record<string, unknown> = { ...vorher };
  if ("company_name" in fields) patch.firma = fields.company_name ?? null;
  if ("branche" in fields) patch.branche = fields.branche ?? null;
  if ("regions" in fields) patch.regions = fields.regions ?? [];
  if ("region_labels" in fields) patch.regionLabels = fields.region_labels ?? [];
  if ("vol_min" in fields) patch.volMin = fields.vol_min ?? null;
  if ("vol_max" in fields) patch.volMax = fields.vol_max ?? null;
  const { ok, reason } = await saveProfile(patch as Parameters<typeof saveProfile>[0]);
  return { ok, error: reason };
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
