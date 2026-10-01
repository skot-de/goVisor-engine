import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { nutzbareProfilIds, darfProfil } from "@/lib/supabase/zuordnung";

/**
 * Profil-Verwaltung einer Organisation (Mehrfachprofile, Phase 2b).
 * Konzept: docs/mehrfachprofile-konzept.md. Umschalten: /api/profil/wechseln.
 *
 * GET    Liste der Profile der eigenen Org + aktives + Kontingent.
 * POST   neues Profil {name}. Das DB-Limit (organizations.profiles_paid) setzt der Trigger
 *        aus 0025 durch; hier wird sein Fehler in eine freundliche 409 uebersetzt.
 * PATCH  umbenennen {id, name}.
 * DELETE loeschen {id} — nie das aktive und nie das letzte Profil.
 *
 * ⚠ TOLERANT gegen den Zustand VOR 0024: fehlen die Spalten/Tabellen, meldet GET schlicht
 * „kein Mehrfachprofil" und die Schreibwege 409/400 — nichts bricht.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const nameOk = (s: unknown): s is string => typeof s === "string" && s.trim().length >= 1 && s.length <= 80;

async function sitzung() {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  return { sb, user };
}

/** org_id + active_profile_id des Nutzers, tolerant (null, wenn Spalte fehlt / keine Org). */
async function kontext(sb: Awaited<ReturnType<typeof createClient>>, userId: string) {
  const { data, error } = await sb.from("user_profiles")
    .select("org_id, active_profile_id").eq("id", userId).single();
  if (error || !data) return { org: null as string | null, aktiv: null as string | null };
  const d = data as { org_id?: string | null; active_profile_id?: string | null };
  return { org: d.org_id ?? null, aktiv: d.active_profile_id ?? null };
}

export async function GET() {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  const { org, aktiv } = await kontext(sb, user.id);
  if (!org) return NextResponse.json({ mehrfach: false, profiles: [], aktiv: null, limit: 1 });
  const { data: profs } = await sb.from("profiles")
    .select("id,name,created_at").eq("org_id", org).order("created_at", { ascending: true });
  const { data: o } = await sb.from("organizations").select("profiles_paid").eq("id", org).single();
  // §7.1: welche Profile DARF dieser Nutzer waehlen (Zuordnung)? null = keine Einschraenkung.
  // Die Liste zeigt weiter ALLE Org-Profile (fuer die Verwaltung), markiert aber `nutzbar`.
  const nutzbar = await nutzbareProfilIds(sb, user.id);
  return NextResponse.json({
    mehrfach: true,
    aktiv,
    limit: (o as { profiles_paid?: number } | null)?.profiles_paid ?? 1,
    profiles: (profs ?? []).map((p) => ({
      id: p.id, name: p.name, active: p.id === aktiv, nutzbar: darfProfil(nutzbar, p.id),
    })),
  }, { headers: { "cache-control": "no-store" } });
}

export async function POST(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  let body: { name?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }
  if (!nameOk(body.name)) return NextResponse.json({ error: "Name fehlt (1 bis 80 Zeichen)" }, { status: 400 });
  const { org } = await kontext(sb, user.id);
  if (!org) return NextResponse.json({ error: "keine Organisation" }, { status: 400 });
  const { data, error } = await sb.from("profiles")
    .insert({ org_id: org, name: body.name.trim(), created_by: user.id }).select("id,name").single();
  if (error) {
    const kontingent = error.code === "23514" || /Kontingent/i.test(error.message);
    return NextResponse.json(
      { error: kontingent ? "Profil-Kontingent erreicht, weitere Profile sind kostenpflichtig." : error.message },
      { status: kontingent ? 409 : 403 });
  }
  // §7.1: den Ersteller dem neuen Profil zuordnen (Admin-Client; keine Client-Schreib-Policy).
  // ⚠ Hat er noch GAR KEINE Zuordnung (Fallback „alle Org-Profile"), zuerst seinen heutigen
  // Zugang festschreiben — sonst verloere er mit der ERSTEN Zuordnung den Zugriff auf die
  // uebrigen Profile. Tolerant: fehlt die Tabelle (vor 0033), bleibt es beim Fallback.
  if (data?.id) {
    try {
      const admin = createAdminClient();
      const { count } = await admin.from("user_profile_assignments")
        .select("profile_id", { count: "exact", head: true }).eq("user_id", user.id);
      if ((count ?? 0) === 0) {
        const { data: alle } = await admin.from("profiles").select("id").eq("org_id", org);
        const rows = (alle ?? []).map((p) => ({ user_id: user.id, profile_id: p.id })); // inkl. dem neuen
        if (rows.length) await admin.from("user_profile_assignments").upsert(rows, { onConflict: "user_id,profile_id" });
      } else {
        await admin.from("user_profile_assignments")
          .upsert({ user_id: user.id, profile_id: data.id }, { onConflict: "user_id,profile_id" });
      }
    } catch { /* vor 0033 */ }
  }
  return NextResponse.json({ ok: true, profile: data });
}

export async function PATCH(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  let body: { id?: string; name?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }
  if (!UUID.test(String(body.id ?? "")) || !nameOk(body.name)) {
    return NextResponse.json({ error: "id/Name ungültig" }, { status: 400 });
  }
  const { error } = await sb.from("profiles").update({ name: body.name!.trim() }).eq("id", body.id!);
  if (error) return NextResponse.json({ error: error.message }, { status: 403 });
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  const id = new URL(req.url).searchParams.get("id") || "";
  if (!UUID.test(id)) return NextResponse.json({ error: "id ungültig" }, { status: 400 });
  const { org, aktiv } = await kontext(sb, user.id);
  if (!org) return NextResponse.json({ error: "keine Organisation" }, { status: 400 });
  if (id === aktiv) return NextResponse.json({ error: "Das aktive Profil lässt sich nicht löschen, erst umschalten." }, { status: 409 });
  const { count } = await sb.from("profiles").select("id", { count: "exact", head: true }).eq("org_id", org);
  if ((count ?? 0) <= 1) return NextResponse.json({ error: "Das letzte Profil lässt sich nicht löschen." }, { status: 409 });
  const { error } = await sb.from("profiles").delete().eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 403 });
  return NextResponse.json({ ok: true });
}
