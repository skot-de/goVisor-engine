"use client";
import { createClient } from "./client";
import type { buildProfile } from "@/lib/profileEngine";

export type Profile = ReturnType<typeof buildProfile> & {
  identityId?: string;
  /** Bestätigte Einheiten MIT Beleglage. Alte Profile tragen hier reine Namen (string) —
   *  beim Lesen beides zulassen, sonst verliert ein bestehendes Konto seine Identität. */
  confirmedEntities?: (string | { name: string; beleg: "kennung" | "selbstauskunft"; wins?: number })[];
  branche?: string;
};

export async function register(email: string, password: string) {
  return createClient().auth.signUp({ email, password });
}
export async function login(email: string, password: string) {
  return createClient().auth.signInWithPassword({ email, password });
}
/* Anmelden ohne Passwort und Passwort zuruecksetzen — beides fuehrt ueber `/auth/callback`
 * zurueck, der den Einmal-Token einloest. Ohne diese Rueckkehr-Route landeten die Mails auf
 * einer Adresse, die nichts damit anfangen kann; genau das war bis 2026-08-18 der Zustand.
 *
 * `window.location.origin` statt einer festen Adresse: dieselbe Datei laeuft lokal, in der
 * Vorschau und live. Supabase muss die Ziele trotzdem in seiner Liste erlaubter
 * Weiterleitungen fuehren, sonst schickt es stumm an die Site-URL. */
export async function magicLink(email: string) {
  return createClient().auth.signInWithOtp({
    email,
    options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
  });
}
export async function passwortVergessen(email: string) {
  return createClient().auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/auth/callback?next=/auth/passwort`,
  });
}
export async function logout() {
  return createClient().auth.signOut();
}
export async function currentUser() {
  const { data } = await createClient().auth.getUser();
  return data.user;
}

/* Engine-Profil → user_profiles-Zeile. Speichert die Struktur-Spalten (für Queries/Billing)
 * UND das volle Profil als Blob (exakter Round-Trip für die Engine). RLS bindet auf auth.uid(). */
export async function saveProfile(profile: Profile): Promise<{ ok: boolean; reason?: string }> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false, reason: "no-session" };
  // Merge-sicher: der profile-Blob trägt auch die #27-Eignungsangaben (stammdaten, references,
  // certificates, attributes, exclusions, zielrichtung, branchen, role, history). Ein Onboarding-
  // Save würde sie sonst wegschreiben (kein Datenverlust). Leere/Default-Werte nicht drüberbügeln.
  const { data: existing } = await supabase.from("user_profiles").select("profile").eq("id", user.id).single();
  const prev = (existing?.profile as Record<string, unknown> | null) ?? {};
  const blob: Record<string, unknown> = { ...(profile as unknown as Record<string, unknown>) };
  const K27 = ["stammdaten", "references", "certificates", "attributes", "exclusions", "zielrichtung", "branchen", "role", "history"];
  for (const k of K27) {
    const inc = blob[k];
    const leer = inc == null || inc === "ausgewogen"
      || (Array.isArray(inc) && inc.length === 0)
      || (typeof inc === "object" && !Array.isArray(inc) && Object.keys(inc as object).length === 0);
    if (leer && prev[k] !== undefined) blob[k] = prev[k];
  }
  const { error } = await supabase.from("user_profiles").update({
    company_name: profile.firma ?? null,
    identity_id: profile.identityId ?? null,
    entity_confidence: confidenceSpalte(profile.entityConfidence),
    // ⚠ `confirmed_entities` ist in 0001_auth_profiles.sql ein `text[]`. Die Beleglage
    // (Objekt je Einheit) kann dort NICHT liegen, ohne dass das Update am Typ scheitert.
    // Sie reist deshalb im `profile`-jsonb mit (blob unten), die Spalte bleibt die reine
    // Namensliste — auch fuer /settings, das genau diese Spalte anzeigt.
    confirmed_entities: (profile.confirmedEntities ?? [])
      .map((e) => (typeof e === "string" ? e : e.name)),
    cpv_fields: profile.cpvFields ?? [],
    cpv_labels: profile.cpvLabels ?? [],
    regions: profile.regions ?? [],
    region_labels: profile.regionLabels ?? [],
    vol_min: profile.volMin ?? null,
    vol_max: profile.volMax ?? null,
    branche: profile.branche ?? null,
    known_from_ted: profile.entityConfidence === "confirmed",
    profile: blob,
  }).eq("id", user.id);
  return { ok: !error, reason: error?.message };
}

/* user_profiles.profile-Blob → Engine-Profil (oder null, wenn nicht eingeloggt / leer). */
/* Die Engine spricht „belegt/unsicher" (⚠-Guard), die Spalte kennt laut CHECK nur
 * `confirmed|probable|none` — der englische Wert-Vertrag aus CLAUDE.md. Ohne diese
 * Abbildung scheitert das Speichern am Constraint, und zwar lautlos.
 *   belegt   → confirmed  (Domain oder Adresse belegen die Zugehörigkeit)
 *   unsicher → probable   (Firma zugeordnet, aber nicht nachgewiesen)
 *   nichts   → none       (gar keine Identität) */
export function confidenceSpalte(v: unknown): "confirmed" | "probable" | "none" {
  if (v === "belegt" || v === "confirmed") return "confirmed";
  if (v === "unsicher" || v === "probable") return "probable";
  return "none";
}

export async function loadProfile(): Promise<Profile | null> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;
  const { data } = await supabase.from("user_profiles").select("profile").eq("id", user.id).single();
  return (data?.profile as Profile) ?? null;
}
