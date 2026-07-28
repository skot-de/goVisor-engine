"use client";
import { createClient } from "./client";
import { parseWert } from "@/lib/explorerCore";

/* Eigener Vertragsbestand (Ticket #11 §8.2) → speist Strategie/Bindung. RLS-gebunden. */

export type UserContract = {
  id: string; lead_id: string | null; buyer_name: string | null; titel: string | null;
  cpv_bundle: string | null; nuts_code: string | null; value_euro: number | null;
  is_framework: boolean; start_date: string | null; end_date: string | null; source: string;
};

export async function loadContracts(): Promise<UserContract[]> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return [];
  const { data } = await sb.from("user_contracts").select("*").eq("user_id", user.id).order("end_date", { ascending: true });
  return (data as UserContract[]) || [];
}

export async function addContract(c: Partial<UserContract>): Promise<{ ok: boolean; error?: string }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false, error: "no-session" };
  const { error } = await sb.from("user_contracts").insert({ user_id: user.id, ...c });
  return { ok: !error, error: error?.message };
}

export async function updateContract(id: string, fields: Partial<UserContract>): Promise<{ ok: boolean }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false };
  const { error } = await sb.from("user_contracts").update(fields).eq("id", id).eq("user_id", user.id);
  return { ok: !error };
}

export async function removeContract(id: string) {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return;
  await sb.from("user_contracts").delete().eq("id", id).eq("user_id", user.id);
}

/* Datum in n Tagen (für end_date aus endTage). */
function inTagen(tage: number | null | undefined): string | null {
  if (tage == null) return null;
  const d = new Date(); d.setDate(d.getDate() + tage);
  return d.toISOString().slice(0, 10);
}

/* „Als gewonnen markieren" — Vertrag aus dem Lead vorbefüllen. Rahmenvertrag wird erkannt
 * (bindet beim Auslaufen wieder Kapazität → Verteidigungssignal in der Strategie). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function markWonFromLead(lead: any): Promise<{ ok: boolean; error?: string }> {
  const framework = /rahmen/i.test(String(lead.art || "")) || !!lead.rahmenvertrag;
  return addContract({
    lead_id: lead.id,
    buyer_name: lead.buyer || null,
    titel: lead.titel || null,
    cpv_bundle: String(lead.cpv || "").slice(0, 4) || null,
    nuts_code: lead.nuts || null,
    value_euro: parseWert(lead.volumen?.wert) ?? null,
    is_framework: framework,
    end_date: inTagen(lead.endTage),
    source: "won_in_app",
  });
}
