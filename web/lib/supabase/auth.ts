"use client";
import { mischeProfilBlob } from "./profilBlob";
import { createClient } from "./client";
import { buildProfile } from "@/lib/profileEngine";

export type Profile = ReturnType<typeof buildProfile> & {
  identityId?: string;
  /** Bestätigte Einheiten MIT Beleglage. Alte Profile tragen hier reine Namen (string) —
   *  beim Lesen beides zulassen, sonst verliert ein bestehendes Konto seine Identität. */
  confirmedEntities?: (string | { name: string; beleg: "kennung" | "selbstauskunft"; wins?: number })[];
  // ⚠ `branche` steht NICHT mehr hier. Es wird seit dem 2026-09-17 von `buildProfile`
  // selbst gefuehrt (`string | null`); eine zweite Deklaration hier (`string | undefined`)
  // liess den Schnitt zu `never` zusammenfallen und nahm damit die ganze Profile-Form mit.
  // Ein Feld, eine Quelle.
  /** Was der Nutzer im Eignungs-Check auf der Startseite angegeben hat. Drei der sechs
   *  Angaben haben schon ein Profilfeld (Grösse, PQ/ISO als `capabilities`); Haftpflicht-
   *  HÖHE, Referenzanzahl und Umsatz haben noch keins. Sie reisen trotzdem mit, damit
   *  niemand ein zweites Mal gefragt werden muss, sobald die Felder da sind. */
  checkAngaben?: import("@/lib/checkUebergabe").CheckAngaben;
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
/**
 * Das aktive Profil des angemeldeten Nutzers — oder `null`, solange es keins gibt.
 *
 * ⚠ TOLERANT gegen den Zustand VOR der Migration 0024. Fehlt die Spalte `active_profile_id`
 * noch, liefert PostgREST einen Fehler; wir geben dann `null` zurueck und alles verhaelt
 * sich wie frueher (gegen `user_profiles`). So darf dieser Code in `main` liegen, bevor die
 * Migration angewandt ist — der Aktiv-Zweig laeuft erst, wenn die Spalte da ist.
 */
export async function aktivesProfilId(
  supabase: ReturnType<typeof createClient>, userId: string,
): Promise<string | null> {
  const { data, error } = await supabase.from("user_profiles")
    .select("active_profile_id").eq("id", userId).single();
  if (error || !data) return null;
  return (data as { active_profile_id?: string | null }).active_profile_id ?? null;
}

export async function saveProfile(profile: Profile): Promise<{ ok: boolean; reason?: string }> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false, reason: "no-session" };
  /* Der profile-Blob traegt auch die #27-Eignungsangaben (stammdaten, references,
   * certificates, attributes, exclusions, zielrichtung, branchen, role, history). Ein
   * Onboarding-Save darf sie nicht wegschreiben.
   *
   * ⚠ HIER STAND EIN LESE-AENDERE-SCHREIBE-ZYKLUS: den bisherigen Blob laden, leere
   * #27-Felder aus ihm zurueckholen, alles zusammen zurueckschreiben. Zwischen Lesen und
   * Schreiben lag ein Fenster, in dem `patchProfil` (unternehmen.ts) denselben Blob
   * schrieb — dessen Aenderung war dann weg.
   *
   * Der Merge passiert jetzt in der Datenbank (`merge_profile`, s. profilBlob.ts). Damit
   * ist das Lesen ueberfluessig UND die Erhaltungsschleife: was der Patch nicht nennt,
   * bleibt ohnehin stehen. Leere Felder werden deshalb WEGGELASSEN statt nachgefuellt —
   * dieselbe Wirkung, eine Runde weniger und kein Fenster. */
  const blob: Record<string, unknown> = { ...(profile as unknown as Record<string, unknown>) };
  const K27 = ["stammdaten", "references", "certificates", "attributes", "exclusions", "zielrichtung", "branchen", "role", "history"];
  for (const k of K27) {
    const inc = blob[k];
    const leer = inc == null || inc === "ausgewogen"
      || (Array.isArray(inc) && inc.length === 0)
      || (typeof inc === "object" && !Array.isArray(inc) && Object.keys(inc as object).length === 0);
    if (leer) delete blob[k];
  }
  const misch = await mischeProfilBlob(blob);
  if (!misch.ok) return { ok: false, reason: misch.error };
  /* Die Spalten daneben sind einwertig und werden nur von hier geschrieben — „der letzte
   * gewinnt" ist richtig, ein eigenes Fenster entsteht nicht.
   *
   * ⚠ SUCH-/IDENTITAETS-SPALTEN gehoeren zum PROFIL, Konto-Spalten zum Nutzer. Gibt es ein
   * aktives Profil (Migration 0024/0025), gehen die Such-Spalten in `profiles` des aktiven
   * Profils — sonst wuerden alle Profile einer Org dieselben Werte teilen. `company_name`,
   * `entity_confidence` und `known_from_ted` bleiben am Konto (`user_profiles`). Ohne
   * aktives Profil (vor der Migration) schreibt alles wie frueher in `user_profiles`. */
  const suchSpalten = {
    identity_id: profile.identityId ?? null,
    // ⚠ `confirmed_entities` ist ein `text[]` (0001/0024). Die Beleglage (Objekt je Einheit)
    // reist im `profile`-jsonb mit (Blob oben); die Spalte bleibt die reine Namensliste.
    confirmed_entities: (profile.confirmedEntities ?? [])
      .map((e) => (typeof e === "string" ? e : e.name)),
    cpv_fields: profile.cpvFields ?? [],
    cpv_labels: profile.cpvLabels ?? [],
    regions: profile.regions ?? [],
    region_labels: profile.regionLabels ?? [],
    vol_min: profile.volMin ?? null,
    vol_max: profile.volMax ?? null,
    branche: profile.branche ?? null,
  };
  const kontoSpalten = {
    company_name: profile.firma ?? null,
    entity_confidence: confidenceSpalte(profile.entityConfidence),
    known_from_ted: profile.entityConfidence === "confirmed",
  };
  const aktiv = await aktivesProfilId(supabase, user.id);
  let error;
  if (aktiv) {
    ({ error } = await supabase.from("profiles").update(suchSpalten).eq("id", aktiv));
    if (!error) ({ error } = await supabase.from("user_profiles").update(kontoSpalten).eq("id", user.id));
  } else {
    ({ error } = await supabase.from("user_profiles")
      .update({ ...suchSpalten, ...kontoSpalten }).eq("id", user.id));
  }
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
  // ⚠ AKTIVES PROFIL GEWINNT, sobald es existiert (Migration 0024/0025) — die Engine sieht
  // damit das umgeschaltete Profil. Ohne aktives Profil (vor der Migration) wie frueher aus
  // `user_profiles`. Der Blob ist die Quelle fuer die Engine; die Spalten sind nur Anzeige.
  const aktiv = await aktivesProfilId(supabase, user.id);
  let blob: unknown = null;
  if (aktiv) {
    const { data } = await supabase.from("profiles").select("profile").eq("id", aktiv).single();
    blob = data?.profile ?? null;
  } else {
    const { data } = await supabase.from("user_profiles").select("profile").eq("id", user.id).single();
    blob = data?.profile ?? null;
  }
  if (!blob) return null;
  // ⚠ DER CAST WAR EINE BEHAUPTUNG, KEINE PRUEFUNG.
  //
  // Hier stand `data?.profile as Profile`. `Profile` ist `ReturnType<typeof buildProfile>`,
  // also ein Typ mit rund zwanzig Pflichtfeldern — zur Laufzeit kam aber schlicht das
  // jsonb aus der Datenbank zurueck, mit genau den Feldern, die jemand hineingeschrieben
  // hat. Der Cast hat die Luecke nicht geschlossen, sondern unsichtbar gemacht.
  //
  // Was daraus folgte, gemessen am 2026-09-11: fehlt im Blob `nachbarFields`, stirbt
  // `matchLead` an `p.nachbarFields.includes(...)` — und zwar beim ERSTEN Rendern der
  // Lead-Liste. Der Nutzer sieht „Application error: a client-side exception has occurred",
  // sonst nichts. Kein Hinweis, keine halbe Seite, kein Weg zurueck.
  //
  // `buildProfile` fuellt genau dafuer jedes Feld mit einem Vorgabewert (`input.x || []`).
  // Es hier anzuwenden kostet nichts und macht die Oberflaeche unempfindlich gegen jedes
  // Profil, das aelter, schmaler oder von Hand gesetzt ist.
  return buildProfile(blob) as Profile;
}
