import "server-only";
import { createClient } from "@/lib/supabase/server";

export type Tier = "free" | "pro";

/**
 * Server-seitiger Zugangs-Tier des aktuellen Nutzers — steuert die Premium-Redaktion in den
 * Daten-Routes (lib/redact.ts). Die Paywall ist NUR sicher, wenn die echten Premium-Werte den
 * Server gar nicht erst verlassen (CSS-Blur allein ist per DevTools lesbar, s. docs/security-review.md).
 *
 * **Env-Gate `PAYWALL_ENFORCED`:**
 * - nicht gesetzt/"false" (heute, Billing = Stub) → **jeder ist `pro`** → keine Redaktion, das
 *   aktuelle „Pro-für-alle"-Demo-Verhalten (`accountLimit = false` im Client) bleibt exakt gleich.
 * - "true" (wenn Billing live geht) → Tier kommt aus der Supabase-Session: eingeloggt **und**
 *   Pro-Abo → `pro`, sonst `free`. Dann MUSS der Client-`accountLimit` aus derselben Quelle kommen.
 *
 * So ist die Enforcement heute wirkungslos (nichts ändert sich), aber vollständig vorverdrahtet:
 * ein Env-Flag + das echte Abo-Feld schalten sie scharf.
 */
export async function getTier(): Promise<Tier> {
  if (process.env.PAYWALL_ENFORCED !== "true") return "pro"; // Gate aus → wie heute (alle Pro)
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return "free";
    // Echtes Abo lesen, sobald Billing eine Spalte/Tabelle dafür hat (z. B. user_profiles.tier
    // oder subscriptions). Bis dahin: eingeloggt ≠ zahlend → free.
    const { data } = await supabase
      .from("user_profiles").select("tier").eq("id", user.id).maybeSingle();
    return data?.tier === "pro" ? "pro" : "free";
  } catch {
    return "free"; // im Zweifel restriktiv (keine Premium-Daten ausliefern)
  }
}
