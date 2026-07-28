"use client";
import { createClient } from "./client";
import type { buildProfile } from "@/lib/profileEngine";

type Profile = ReturnType<typeof buildProfile> & {
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
  const { error } = await supabase.from("user_profiles").update({
    company_name: profile.firma ?? null,
    identity_id: profile.identityId ?? null,
    entity_confidence: profile.entityConfidence ?? "none",
    confirmed_entities: profile.confirmedEntities ?? [],
    cpv_fields: profile.cpvFields ?? [],
    cpv_labels: profile.cpvLabels ?? [],
    regions: profile.regions ?? [],
    region_labels: profile.regionLabels ?? [],
    vol_min: profile.volMin ?? null,
    vol_max: profile.volMax ?? null,
    branche: profile.branche ?? null,
    known_from_ted: profile.entityConfidence === "confirmed",
    profile,
  }).eq("id", user.id);
  return { ok: !error, reason: error?.message };
}

/* user_profiles.profile-Blob → Engine-Profil (oder null, wenn nicht eingeloggt / leer). */
export async function loadProfile(): Promise<Profile | null> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;
  const { data } = await supabase.from("user_profiles").select("profile").eq("id", user.id).single();
  return (data?.profile as Profile) ?? null;
}
