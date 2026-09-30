import "server-only";
import { createAdminClient } from "@/lib/supabase/admin";

/** Verbucht einen bezahlten Kauf idempotent (kauf_gutschreiben, 0027). Aufrufer: der
 *  Zahlungs-Webhook. `ref` ist die Zahlungs-Referenz (z.B. Stripe checkout.session.id) und
 *  traegt die Idempotenz: ein zweiter Aufruf mit derselben ref erhoeht nichts. */
export async function erfuelleKauf(
  org: string, art: "seat" | "profile", menge: number, ref: string, cents?: number,
): Promise<{ ok: boolean; status?: string; error?: string }> {
  const admin = createAdminClient();
  const { data, error } = await admin.rpc("kauf_gutschreiben", {
    p_org: org, p_art: art, p_menge: menge, p_provider: "stripe", p_ref: ref,
    p_cents: cents ?? null,
  });
  if (error) return { ok: false, error: error.message };
  return { ok: true, status: data as string };   // 'gutgeschrieben' | 'schon_verbucht'
}
