import "server-only";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { getTier } from "@/lib/tier";

/**
 * Vorgangs-Kontingent (Preismodell v1.9 §4.3). DB: supabase/0029_vorgang_credits.sql.
 *
 * ⚠ NAMENSHINWEIS: „Vorgang" meint hier die ABRECHNUNGSEINHEIT (§4.3), NICHT die Vorgangsakte
 * (lib/vorgangsakte.ts, /api/vorgang). Diese Datei und /api/kontingent heissen deshalb bewusst
 * „kontingent", damit beides nicht verwechselt wird. Die DB-Objekte (vorgang_freigaben,
 * vorgang_freischalten) tragen den v1.9-Begriff und liegen im eigenen Namensraum.
 *
 * Ein Vorgang ist ein aufgeschlossener Lead (erstes Oeffnen Unterlagen ODER Bewertung) ODER
 * ein einzeln aufgerufenes Firmenprofil. Free: 3/Monat; aufgeschlossene Vorgaenge bleiben
 * dauerhaft offen. Bezahlte Stufen (und solange die Paywall aus ist): unbegrenzt.
 *
 * ⚠ Das Limit ist SERVER-AUTORITATIV: es wird hier aus der Stufe berechnet und der
 * `security definer`-RPC uebergeben (die kein Client direkt aufrufen kann, s. 0030). Ein
 * client-seitig uebergebenes Limit gaebe es nie — sonst koennte ein Free-Nutzer umgehen.
 */

const FREE_LIMIT = Number(process.env.FREE_VORGAENGE ?? 3);   // §4.3; §10 #5 = justierbar

/** Monatslimit der aktuellen Stufe: FREE_LIMIT fuer 'free', null (= unbegrenzt) fuer 'pro'.
 *  `getTier()` liefert 'pro', solange PAYWALL_ENFORCED aus ist → heutiges Verhalten (alle Pro). */
export async function vorgangLimit(): Promise<number | null> {
  return (await getTier()) === "free" ? FREE_LIMIT : null;
}

async function kontext() {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { user: null as null, org: null as string | null };
  const { data } = await sb.from("user_profiles").select("org_id").eq("id", user.id).single();
  return { user, org: (data as { org_id?: string | null } | null)?.org_id ?? null };
}

export type FreigabeStatus = "freigeschaltet" | "schon_frei" | "limit_erreicht";

/** Schaltet einen Vorgang frei (oder meldet, dass er schon offen / das Limit voll ist). */
export async function freischalten(art: "lead" | "firma", ref: string):
  Promise<{ ok: boolean; status?: FreigabeStatus; error?: string }> {
  const { user, org } = await kontext();
  if (!user) return { ok: false, error: "Anmeldung erforderlich" };
  if (!org) return { ok: false, error: "keine Organisation" };
  const limit = await vorgangLimit();
  const admin = createAdminClient();
  const { data, error } = await admin.rpc("vorgang_freischalten", {
    p_org: org, p_art: art, p_ref: ref, p_limit: limit, p_durch: user.id,
  });
  if (error) return { ok: false, error: error.message };
  return { ok: true, status: data as FreigabeStatus };
}

/** Zaehlerstand fuer die Oberflaeche (§4.2 „2 von 3 Vorgaengen"). offen/limit = null → unbegrenzt. */
export async function vorgangStand():
  Promise<{ verbraucht: number; limit: number | null; offen: number | null }> {
  const limit = await vorgangLimit();
  const { org } = await kontext();
  if (!org) return { verbraucht: 0, limit, offen: limit };
  const sb = await createClient();
  const start = new Date(); start.setUTCDate(1); start.setUTCHours(0, 0, 0, 0);
  // RLS scopt den Zaehler automatisch auf die Org des Nutzers.
  const { count } = await sb.from("vorgang_freigaben")
    .select("id", { count: "exact", head: true })
    .gte("freigeschaltet_am", start.toISOString());
  const verbraucht = count ?? 0;
  return { verbraucht, limit, offen: limit == null ? null : Math.max(0, limit - verbraucht) };
}
