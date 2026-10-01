import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";

/**
 * Nutzer × Profil-Zuordnung (Preismodell v1.9 §7.1, DB: supabase/0033_user_profile_assignments.sql).
 *
 * Welche Profile ein Nutzer sehen/waehlen darf. TOLERANT, genau wie 0024-0027:
 *   - fehlt die Tabelle (vor 0033)  → null  = keine Einschraenkung (heutiger Zustand)
 *   - hat der Nutzer KEINE Zuordnung → null  = alle Profile der Org (wie bisher)
 *   - sonst → die Liste der zugeordneten profile_id
 *
 * Gelesen unter der Nutzer-Session (RLS: upa_select_own → nur eigene Zuordnungen).
 */
export async function nutzbareProfilIds(
  sb: SupabaseClient, userId: string,
): Promise<string[] | null> {
  const { data, error } = await sb
    .from("user_profile_assignments").select("profile_id").eq("user_id", userId);
  if (error) return null;                       // Tabelle fehlt o. Ae. → tolerant
  if (!data || data.length === 0) return null;  // keine Zuordnung → wie heute (alle Org-Profile)
  return data.map((r) => (r as { profile_id: string }).profile_id);
}

/** Darf der Nutzer dieses Profil nutzen? `null` aus nutzbareProfilIds = ja (keine Einschraenkung). */
export function darfProfil(nutzbar: string[] | null, profileId: string): boolean {
  return nutzbar === null || nutzbar.includes(profileId);
}
