import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";

/**
 * Konten & Profile (Admin-Portal, Bereich 3). Orgs mit Mitgliedern/Profilen/Seats/Plan +
 * Aktionen: Seats/Profile/Plan setzen (der manuelle Hebel, solange der Kauf-Flow nicht
 * scharf ist) und Passwort-Reset-Mail. Identitaets-Ansprueche laufen ueber /api/intern/claims.
 *
 * ⚠ Liest quer ueber alle Nutzer → Admin-Client (die user_profiles-RLS zeigt nur die eigene
 * Zeile). Gleiche Sperre wie die uebrigen /api/intern-Routen (Middleware: istAdmin; hier
 * zusaetzlich der Prod-Riegel).
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function gesperrt() {
  return process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1";
}
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET() {
  if (gesperrt()) return NextResponse.json({ error: "not found" }, { status: 404 });
  const admin = createAdminClient();
  const [orgsR, upsR, profsR] = await Promise.all([
    admin.from("organizations").select("id,name,plan,plan_until,seats_paid,profiles_paid").order("created_at"),
    admin.from("user_profiles").select("email,role,org_id,active_profile_id"),
    admin.from("profiles").select("id,org_id"),
  ]);
  if (orgsR.error) return NextResponse.json({ error: orgsR.error.message }, { status: 500 });
  const ups = upsR.data ?? []; const profs = profsR.data ?? [];
  const mitglieder = new Map<string, { email: string; role: string }[]>();
  for (const u of ups) {
    if (!u.org_id) continue;
    (mitglieder.get(u.org_id) ?? mitglieder.set(u.org_id, []).get(u.org_id)!)
      .push({ email: u.email, role: u.role });
  }
  const profZahl = new Map<string, number>();
  for (const p of profs) profZahl.set(p.org_id, (profZahl.get(p.org_id) ?? 0) + 1);
  const orgs = (orgsR.data ?? []).map((o) => ({
    id: o.id, name: o.name, plan: o.plan, plan_until: o.plan_until,
    seats_paid: o.seats_paid, profiles_paid: o.profiles_paid,
    mitglieder: mitglieder.get(o.id) ?? [],
    profile: profZahl.get(o.id) ?? 0,
  }));
  return NextResponse.json({ orgs }, { headers: { "cache-control": "no-store" } });
}

export async function PATCH(req: Request) {
  if (gesperrt()) return NextResponse.json({ error: "not found" }, { status: 404 });
  let body: { org_id?: string; seats_paid?: number; profiles_paid?: number; plan?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }
  if (!UUID.test(String(body.org_id ?? ""))) return NextResponse.json({ error: "org_id ungültig" }, { status: 400 });
  const patch: Record<string, unknown> = {};
  if (body.seats_paid != null) {
    const n = Math.floor(Number(body.seats_paid));
    if (!(n >= 1 && n <= 1000)) return NextResponse.json({ error: "seats_paid 1..1000" }, { status: 400 });
    patch.seats_paid = n;
  }
  if (body.profiles_paid != null) {
    const n = Math.floor(Number(body.profiles_paid));
    if (!(n >= 1 && n <= 1000)) return NextResponse.json({ error: "profiles_paid 1..1000" }, { status: 400 });
    patch.profiles_paid = n;
  }
  if (body.plan != null) {
    if (!["free", "paid", "cancelled"].includes(body.plan)) return NextResponse.json({ error: "plan ungültig" }, { status: 400 });
    patch.plan = body.plan;
  }
  if (!Object.keys(patch).length) return NextResponse.json({ error: "nichts zu ändern" }, { status: 400 });
  const admin = createAdminClient();
  const { error } = await admin.from("organizations").update(patch).eq("id", body.org_id!);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}

export async function POST(req: Request) {
  if (gesperrt()) return NextResponse.json({ error: "not found" }, { status: 400 });
  let body: { action?: string; email?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }
  if (body.action !== "passwort-reset") return NextResponse.json({ error: "unbekannte Aktion" }, { status: 400 });
  const email = String(body.email ?? "").trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return NextResponse.json({ error: "E-Mail ungültig" }, { status: 400 });
  // Loest die Reset-Mail aus — setzt NIE selbst ein Passwort (Konzept-Leitplanke).
  const sb = await createClient();
  const { error } = await sb.auth.resetPasswordForEmail(email);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
