import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * Testphasen-Stand (Preismodell v1.9 §3a / §4.2). Liefert, ob die Org gerade in der Testphase
 * ist, wie lange noch, und wie viele Vorgaenge bereits aufgeschlossen wurden — fuer den Hinweis
 * im Kopf („Testphase endet in N Tagen; X Vorgaenge aufgeschlossen, danach 3 im Monat").
 *
 * Auswertung der Stufe liegt in lib/stufeZuTier.js (trial + Datum → pro, sonst free); HIER nur
 * die Rohwerte fuer die Anzeige. Ruhig, wenn keine Testphase laeuft (trial:false, kein Hinweis).
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const FREE = Number(process.env.FREE_VORGAENGE ?? 3);

export async function GET() {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ trial: false });
  const { data: up } = await sb.from("user_profiles").select("org_id").eq("id", user.id).single();
  const org = (up as { org_id?: string | null } | null)?.org_id;
  if (!org) return NextResponse.json({ trial: false });
  const { data: o } = await sb.from("organizations").select("tier, trial_ends_at").eq("id", org).single();
  const oo = o as { tier?: string; trial_ends_at?: string | null } | null;
  if (!oo || oo.tier !== "trial") return NextResponse.json({ trial: false });
  const endet = oo.trial_ends_at ? Date.parse(oo.trial_ends_at) : NaN;
  const tageRest = Number.isFinite(endet) ? Math.max(0, Math.ceil((endet - Date.now()) / 86_400_000)) : 0;
  // Vorgaenge der Org (RLS: vorgang_select_member scopt auf die eigene Org).
  const { count } = await sb.from("vorgang_freigaben").select("id", { count: "exact", head: true });
  return NextResponse.json(
    { trial: true, endet_am: oo.trial_ends_at ?? null, tage_rest: tageRest, genutzt: count ?? 0, limit_free: FREE },
    { headers: { "cache-control": "no-store" } },
  );
}
