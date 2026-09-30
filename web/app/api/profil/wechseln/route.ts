import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * Aktives Profil wechseln (Mehrfachprofile, s. docs/mehrfachprofile-konzept.md).
 *
 * Ein Nutzer nutzt genau EIN Profil aktiv; dieser Endpunkt setzt `active_profile_id`. Die
 * Berechtigung liegt in der RLS aus 0024: `profiles_select_member` laesst den Nutzer nur die
 * Profile SEINER Org sehen — ein fremdes Profil kommt beim SELECT gar nicht zurueck, und das
 * UPDATE trifft ohnehin nur die eigene `user_profiles`-Zeile (`profiles_update_own`, 0001).
 * Zusaetzlich pruefen wir hier explizit, dass das Profil sichtbar (= in der eigenen Org) ist.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(req: Request) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });

  let body: { profile_id?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }
  const id = String(body.profile_id ?? "");
  if (!UUID.test(id)) return NextResponse.json({ error: "profile_id fehlt/ungültig" }, { status: 400 });

  // Gehoert das Profil zu einer Org, die der Nutzer sehen darf? (RLS filtert auf die eigene Org.)
  const { data: p } = await supabase.from("profiles").select("id").eq("id", id).single();
  if (!p) return NextResponse.json({ error: "Profil nicht gefunden" }, { status: 404 });

  const { error } = await supabase.from("user_profiles")
    .update({ active_profile_id: id }).eq("id", user.id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, active_profile_id: id });
}
