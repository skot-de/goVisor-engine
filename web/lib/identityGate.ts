import "server-only";
import { createAdminClient } from "@/lib/supabase/admin";

/* Sperre für alles, was an der beanspruchten Firmen-Identität hängt.
 *
 * Der Anspruch „wir sind diese Firma" wird beim Onboarding erhoben und nur dann automatisch
 * belegt, wenn die Registrierungs-Adresse zu den Vergabedaten passt (Adresse selbst oder
 * Firmen-Domain, s. /api/entity-verify). Solange das nicht der Fall ist, steht das Profil auf
 * `probable` — und alles, was nach außen wirkt oder Geld bewegt, muss darauf hören.
 *
 * Fail-closed: kann der Status nicht gelesen werden, gilt „nicht bestätigt". Ein Fehler darf
 * keine Rechnung auslösen.
 */

export type IdentitaetsStatus = { bestaetigt: boolean; wert: string };

export async function identitaetBestaetigt(userId: string): Promise<IdentitaetsStatus> {
  try {
    const { data, error } = await createAdminClient()
      .from("user_profiles").select("entity_confidence").eq("id", userId).single();
    if (error || !data) return { bestaetigt: false, wert: "unbekannt" };
    const wert = String(data.entity_confidence ?? "none");
    return { bestaetigt: wert === "confirmed", wert };
  } catch {
    return { bestaetigt: false, wert: "unlesbar" };
  }
}

/** Standard-Antwort für gesperrte Endpunkte — überall derselbe Wortlaut. */
export const GESPERRT = {
  ok: false,
  error: "identity-unconfirmed",
  hinweis: "Diese Funktion ist gesperrt, bis eure Zugehörigkeit zur Firma bestätigt ist.",
} as const;
