import { createClient } from "./client";

/* Identitäts-Anspruch: „wir sind diese Firma".
 *
 * Der maschinelle Abgleich (/api/entity-verify) klärt gut die Hälfte der Fälle über die
 * Firmen-Domain. Für den Rest — gemessen 5,8 % unserer Zielgruppe, davon die Hälfte
 * t-online-Adressen — gibt es den Prüfantrag: der Nutzer schreibt dazu, wer er ist, und
 * jemand sieht sich das an. Der Status wird bewusst NICHT vom Client gesetzt (RLS erlaubt
 * nur insert/select) — sonst könnte man sich selbst freischalten.
 */

export type ClaimStatus = "belegt" | "unbestaetigt" | "geprueft" | "abgelehnt";

export type Claim = {
  id: string;
  identity_id: string;
  company_name: string;
  status: ClaimStatus;
  grund: string | null;
  nachricht: string | null;
  created_at: string;
};

export async function saveClaim(input: {
  identityId: string; companyName: string; emailDomain: string | null;
  status: Extract<ClaimStatus, "belegt" | "unbestaetigt">; grund: string; nachricht?: string;
}): Promise<{ error: string | null }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { error: "nicht angemeldet" };
  const { error } = await sb.from("identity_claims").insert({
    user_id: user.id,
    identity_id: input.identityId,
    company_name: input.companyName,
    email_domain: input.emailDomain,
    status: input.status,
    grund: input.grund,
    nachricht: input.nachricht ?? null,
  });
  return { error: error?.message ?? null };
}

export async function loadClaim(): Promise<Claim | null> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return null;
  const { data } = await sb.from("identity_claims")
    .select("id, identity_id, company_name, status, grund, nachricht, created_at")
    .eq("user_id", user.id).order("created_at", { ascending: false }).limit(1).maybeSingle();
  return (data as Claim) ?? null;
}
