"use client";
import { createClient } from "./client";

/* Feature #11 §8.1 — erklärte Angaben, einheitlich (`user_declarations`).
 * Der eine Ort für „was ihr könnt / nachweisen könnt", quer über Erhebungsorte (Onboarding,
 * Anforderungs-Check, Treffergüte). Alterung + „Stimmt so"-Sammelbestätigung (§4.2). */

export type DeclKind =
  | "capability" | "certificate" | "guarantee" | "volume_limit" | "region"
  | "exclusion" | "regulatory" | "partnership" | "prequalification" | "reference" | "capacity";
export type DeclSource = "onboarding" | "requirement_check" | "trefferguete" | "dismiss_reason";

export type Declaration = {
  id?: string;
  kind: DeclKind;
  key: string;
  value: unknown;              // jsonb: Band, Betrag, Datum, Boolean …
  source: DeclSource;
  declared_at?: string;
  confirmed_at?: string | null;
  valid_until?: string | null;
};

export async function loadDeclarations(): Promise<Declaration[]> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return [];
  const { data } = await sb.from("user_declarations").select("*").eq("user_id", user.id);
  return (data as Declaration[]) || [];
}

// Angabe setzen (upsert über user_id,kind,key) — declared_at/confirmed_at auf jetzt.
export async function declare(d: Declaration): Promise<{ ok: boolean; error?: string }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false, error: "no-session" };
  const now = new Date().toISOString();
  const row = {
    user_id: user.id, kind: d.kind, key: d.key, value: d.value, source: d.source,
    declared_at: now, confirmed_at: now, valid_until: d.valid_until ?? null,
  };
  const { error } = await sb.from("user_declarations").upsert(row, { onConflict: "user_id,kind,key" });
  return { ok: !error, error: error?.message };
}

export async function removeDeclaration(kind: DeclKind, key: string) {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return;
  await sb.from("user_declarations").delete().eq("user_id", user.id).eq("kind", kind).eq("key", key);
}

/* „Stimmt so" — Sammelbestätigung (§4.2 / #27 §9.1). Setzt confirmed_at auf jetzt, ohne
 * Neueingabe. Optional nur für bestimmte ids. Gibt die Zahl der bestätigten Angaben zurück. */
export async function confirmDeclarations(ids?: string[]): Promise<{ ok: boolean; count: number }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false, count: 0 };
  let q = sb.from("user_declarations").update({ confirmed_at: new Date().toISOString() }).eq("user_id", user.id);
  if (ids && ids.length) q = q.in("id", ids);
  const { data, error } = await q.select("id");
  return { ok: !error, count: data ? data.length : 0 };
}

// Monate seit letzter Bestätigung (für den 6-Monats-Trigger, §4.2 / #16 OF6: 12 M bei Zertifikaten).
export function ageMonths(d: Declaration): number | null {
  const ref = d.confirmed_at || d.declared_at;
  if (!ref) return null;
  const then = new Date(ref).getTime();
  if (Number.isNaN(then)) return null;
  return Math.floor((Date.now() - then) / (1000 * 60 * 60 * 24 * 30.44));
}

// Angaben, die eine Bestätigung brauchen (Fähigkeiten >6 M, Zertifikate >12 M).
export function needsConfirmation(decls: Declaration[]): Declaration[] {
  return decls.filter((d) => {
    const m = ageMonths(d);
    if (m == null) return false;
    return d.kind === "certificate" ? m >= 12 : m >= 6;
  });
}
