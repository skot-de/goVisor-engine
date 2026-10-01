import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";

/**
 * Nutzer × Profil-Zuordnung verwalten (Preismodell v1.9 §7.1). DB:
 * supabase/0033_user_profile_assignments.sql. Der Nutzer-Umschalter/-Liste liest die eigene
 * Zuordnung ueber /api/profil; HIER weist owner/admin anderen Mitgliedern Profile zu.
 *
 * GET    Mitglieder der Org + je Mitglied die zugeordneten profile_id, dazu die Org-Profile.
 * POST   {user_id, profile_id} zuordnen — owner/admin, beide in DERSELBEN Org.
 * DELETE {user_id, profile_id} entfernen — nie das AKTIVE und nie die LETZTE Zuordnung.
 *
 * ⚠ Admin-Client, hart auf die Org des Aufrufers gescopet (die user_profiles-RLS zeigt nur die
 * eigene Zeile, und die Zuordnung hat bewusst keine Client-Schreib-Policy). Gleiche Linie wie
 * /api/org/mitglieder. Tolerant: fehlt die Tabelle (vor 0033), meldet GET „kein Team".
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function ich() {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { user: null as null, org: null as string | null, role: null as string | null };
  const { data } = await sb.from("user_profiles").select("org_id, role").eq("id", user.id).single();
  const d = (data ?? {}) as { org_id?: string | null; role?: string | null };
  return { user, org: d.org_id ?? null, role: d.role ?? null };
}
const adminNur = (role: string | null) => role === "owner" || role === "admin";

export async function GET() {
  const { user, org, role } = await ich();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  if (!org || !adminNur(role)) return NextResponse.json({ error: "Nur Inhaber/Admins." }, { status: 403 });
  const admin = createAdminClient();
  const { data: mit } = await admin.from("user_profiles")
    .select("id, email, role, active_profile_id").eq("org_id", org);
  const { data: profs } = await admin.from("profiles").select("id, name").eq("org_id", org).order("created_at");
  const ids = (mit ?? []).map((m) => m.id);
  const { data: zu, error } = ids.length
    ? await admin.from("user_profile_assignments").select("user_id, profile_id").in("user_id", ids)
    : { data: [], error: null };
  if (error) return NextResponse.json({ team: false, grund: "Zuordnung (0033) nicht vorhanden" });
  const proNutzer = new Map<string, string[]>();
  for (const z of zu ?? []) {
    const a = proNutzer.get(z.user_id) ?? []; a.push(z.profile_id); proNutzer.set(z.user_id, a);
  }
  return NextResponse.json({
    team: true, role,
    profile: (profs ?? []).map((p) => ({ id: p.id, name: p.name })),
    mitglieder: (mit ?? []).map((m) => ({
      id: m.id, email: m.email, role: m.role, active_profile_id: m.active_profile_id,
      profile_ids: proNutzer.get(m.id) ?? [],
    })),
  }, { headers: { "cache-control": "no-store" } });
}

/** Pruefen, dass Ziel-Nutzer UND Profil zur Org des Aufrufers gehoeren. */
async function selbeOrg(admin: ReturnType<typeof createAdminClient>, org: string, userId: string, profileId: string) {
  const { data: u } = await admin.from("user_profiles").select("org_id, active_profile_id").eq("id", userId).single();
  const { data: p } = await admin.from("profiles").select("org_id").eq("id", profileId).single();
  const uu = u as { org_id?: string; active_profile_id?: string | null } | null;
  const pp = p as { org_id?: string } | null;
  return { ok: !!uu && !!pp && uu.org_id === org && pp.org_id === org, aktiv: uu?.active_profile_id ?? null };
}

export async function POST(req: Request) {
  const { user, org, role } = await ich();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  if (!org || !adminNur(role)) return NextResponse.json({ error: "Nur Inhaber/Admins." }, { status: 403 });
  let body: { user_id?: string; profile_id?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }
  if (!UUID.test(String(body.user_id ?? "")) || !UUID.test(String(body.profile_id ?? "")))
    return NextResponse.json({ error: "user_id/profile_id ungültig" }, { status: 400 });
  const admin = createAdminClient();
  const { ok } = await selbeOrg(admin, org, body.user_id!, body.profile_id!);
  if (!ok) return NextResponse.json({ error: "Nutzer und Profil müssen zur selben Organisation gehören." }, { status: 400 });
  const { error } = await admin.from("user_profile_assignments")
    .upsert({ user_id: body.user_id, profile_id: body.profile_id }, { onConflict: "user_id,profile_id" });
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  // Ein aktives Profil muss immer zugeordnet sein. Faellt das aktive des Nutzers durch die
  // (nun eingeschraenkte) Zuordnung heraus, auf das gerade zugeordnete umstellen.
  const { data: usr } = await admin.from("user_profiles").select("active_profile_id").eq("id", body.user_id).single();
  const { data: zu } = await admin.from("user_profile_assignments").select("profile_id").eq("user_id", body.user_id);
  const set = new Set((zu ?? []).map((r) => (r as { profile_id: string }).profile_id));
  const aktiv = (usr as { active_profile_id?: string | null } | null)?.active_profile_id ?? null;
  if (!aktiv || !set.has(aktiv)) {
    await admin.from("user_profiles").update({ active_profile_id: body.profile_id }).eq("id", body.user_id);
  }
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: Request) {
  const { user, org, role } = await ich();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  if (!org || !adminNur(role)) return NextResponse.json({ error: "Nur Inhaber/Admins." }, { status: 403 });
  const u = new URL(req.url).searchParams;
  const userId = u.get("user_id") || "", profileId = u.get("profile_id") || "";
  if (!UUID.test(userId) || !UUID.test(profileId))
    return NextResponse.json({ error: "user_id/profile_id ungültig" }, { status: 400 });
  const admin = createAdminClient();
  const { ok, aktiv } = await selbeOrg(admin, org, userId, profileId);
  if (!ok) return NextResponse.json({ error: "fremde Organisation" }, { status: 400 });
  // Nie das aktive Profil entziehen — sonst haette der Nutzer ein aktives Profil, das er nicht
  // mehr nutzen darf.
  if (aktiv === profileId)
    return NextResponse.json({ error: "Das aktive Profil des Nutzers lässt sich nicht entziehen, erst umschalten." }, { status: 409 });
  // Nie die letzte Zuordnung entziehen — jeder Nutzer behält mindestens ein Profil.
  const { count } = await admin.from("user_profile_assignments")
    .select("profile_id", { count: "exact", head: true }).eq("user_id", userId);
  if ((count ?? 0) <= 1)
    return NextResponse.json({ error: "Die letzte Zuordnung lässt sich nicht entziehen." }, { status: 409 });
  const { error } = await admin.from("user_profile_assignments")
    .delete().eq("user_id", userId).eq("profile_id", profileId);
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ ok: true });
}
