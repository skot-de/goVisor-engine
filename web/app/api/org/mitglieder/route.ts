import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";

/**
 * Team einer Organisation: Mitglieder + offene Einladungen (Mehrfachprofile/Seats, Phase 2b).
 * DB: supabase/0026_pending_invites.sql. Umschalten/Profile: /api/profil.
 *
 * GET    Mitglieder + offene Einladungen der eigenen Org (+ eigene Rolle, fuer die UI).
 * POST   einladen {email, role?} — nur owner/admin; die Seat-Grenze setzt der Trigger aus
 *        0026 durch (belegt = Mitglieder + offene Einladungen), hier zu freundlicher 409.
 *        Danach verschickt Supabase die Einladungs-Mail (Auth-Admin).
 * DELETE zuruecknehmen {id} — nur owner/admin.
 *
 * ⚠ Die Mitgliederliste braucht den Admin-Client: die user_profiles-RLS (0001) laesst jeden
 * nur SEINE Zeile sehen. Wir loesen die Org des Aufrufers ueber seine eigene Zeile auf und
 * scopen dann alle Admin-Abfragen hart auf diese org_id — kein Blick in fremde Orgs.
 * ⚠ TOLERANT: fehlen die Spalten/Tabellen (vor 0024/0026), meldet GET „kein Team".
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function ich() {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { user: null as null, org: null as string | null, role: null as string | null };
  const { data, error } = await sb.from("user_profiles").select("org_id, role").eq("id", user.id).single();
  if (error || !data) return { user, org: null, role: null };
  const d = data as { org_id?: string | null; role?: string | null };
  return { user, org: d.org_id ?? null, role: d.role ?? null };
}

export async function GET() {
  const { user, org, role } = await ich();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  if (!org) return NextResponse.json({ team: false, role: null, mitglieder: [], einladungen: [] });
  const admin = createAdminClient();
  const { data: mit } = await admin.from("user_profiles").select("email, role").eq("org_id", org);
  const { data: inv } = await admin.from("pending_invites")
    .select("id, email, role, created_at").eq("org_id", org).eq("status", "offen").order("created_at");
  return NextResponse.json({
    team: true, role,
    mitglieder: (mit ?? []).map((m) => ({ email: m.email, role: m.role })),
    einladungen: (inv ?? []).map((i) => ({ id: i.id, email: i.email, role: i.role })),
  }, { headers: { "cache-control": "no-store" } });
}

export async function POST(req: Request) {
  const { user, org, role } = await ich();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  if (!org || !(role === "owner" || role === "admin")) {
    return NextResponse.json({ error: "Nur Inhaber/Admins können einladen." }, { status: 403 });
  }
  let body: { email?: string; role?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }
  const email = String(body.email ?? "").trim().toLowerCase();
  const rolle = body.role === "admin" ? "admin" : "member";
  if (!EMAIL.test(email)) return NextResponse.json({ error: "E-Mail ungültig" }, { status: 400 });

  const admin = createAdminClient();
  // Einladung anlegen — der Seat-Trigger (0026) entscheidet ueber die Kapazitaet.
  const { error } = await admin.from("pending_invites")
    .insert({ org_id: org, email, role: rolle, invited_by: user.id });
  if (error) {
    const voll = error.code === "23514" || /Kontingent|Seat/i.test(error.message);
    const doppelt = error.code === "23505";
    return NextResponse.json(
      { error: voll ? "Seat-Kontingent erreicht — weitere Sitze sind kostenpflichtig."
                    : doppelt ? "Für diese Adresse ist bereits eine Einladung offen." : error.message },
      { status: voll ? 409 : doppelt ? 409 : 400 });
  }
  // Einladungs-Mail; scheitert sie, bleibt die Einladung offen und kann erneut verschickt werden.
  const { error: mail } = await admin.auth.admin.inviteUserByEmail(email);
  if (mail) return NextResponse.json({ ok: true, warnung: "Einladung angelegt, Mailversand fehlgeschlagen: " + mail.message });
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: Request) {
  const { user, org, role } = await ich();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  if (!org || !(role === "owner" || role === "admin")) {
    return NextResponse.json({ error: "Nur Inhaber/Admins können Einladungen zurücknehmen." }, { status: 403 });
  }
  const id = new URL(req.url).searchParams.get("id") || "";
  if (!UUID.test(id)) return NextResponse.json({ error: "id ungültig" }, { status: 400 });
  const admin = createAdminClient();
  const { error } = await admin.from("pending_invites")
    .update({ status: "zurueckgezogen" }).eq("id", id).eq("org_id", org).eq("status", "offen");
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ ok: true });
}
