"use client";
import { createClient } from "./client";
import type { buildProfile } from "@/lib/profileEngine";

export type Profile = ReturnType<typeof buildProfile> & {
  identityId?: string; confirmedEntities?: string[]; branche?: string;
};

export async function register(email: string, password: string) {
  return createClient().auth.signUp({ email, password });
}
export async function login(email: string, password: string) {
  return createClient().auth.signInWithPassword({ email, password });
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
    confirmed_entities: profile.confirmedEntities ?? [],
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
