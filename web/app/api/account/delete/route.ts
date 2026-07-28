import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";

/* Account-Löschung (Ticket #10 §5, Art. 17). Der eingeloggte Nutzer löscht sich selbst:
 * Session verifizieren → Admin-Client löscht auth.users → Kaskade räumt user_profiles &
 * alle abhängigen Tabellen (on delete cascade). Bezahlte Rechnungen später pseudonymisieren
 * (offen bis Billing produktiv). */
export async function POST() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ ok: false, error: "not-authenticated" }, { status: 401 });

  const admin = createAdminClient();
  const { error } = await admin.auth.admin.deleteUser(user.id);
  if (error) return NextResponse.json({ ok: false, error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
