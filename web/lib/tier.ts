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
 *   `user_profiles.plan = 'paid'` → `pro`, sonst `free`. Dann MUSS der Client-`accountLimit`
 *   aus derselben Quelle kommen.
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
    // ⚠ DIE SPALTE HEISST `plan`, NICHT `tier`. Bis zum 2026-08-22 stand hier
    // `select("tier")` — eine Spalte, die es in keiner Migration je gab. Solange
    // PAYWALL_ENFORCED aus war, fiel das niemandem auf; am Tag der Scharfschaltung hätte
    // die Abfrage geworfen, der catch hätte daraus lautlos „free" gemacht, und JEDER
    // Zahlende wäre auf den Free-Umfang gefallen. Der teuerste denkbare Zeitpunkt.
    // Werte laut 0001: 'free' | 'paid' | 'cancelled'.
    const { data, error } = await supabase
      .from("user_profiles").select("plan,plan_until").eq("id", user.id).maybeSingle();
    // Ein FEHLER ist nicht dasselbe wie „zahlt nicht". Wer beides gleich behandelt, merkt
    // einen Schemafehler erst an den Beschwerden zahlender Kunden.
    if (error) {
      console.error("[tier] Abo-Abfrage fehlgeschlagen, liefere free:", error.message);
      return "free";
    }
    if (data?.plan === "paid") return "pro";
    // Gekündigt heisst nicht sofort gesperrt: wer am 2. des Monats kündigt, hat den Monat
    // bezahlt. `plan_until` (0015) trägt das Ende des bezahlten Zeitraums; ohne Datum bleibt
    // es beim sofortigen Ende, weil wir dann nichts Besseres wissen.
    if (data?.plan === "cancelled" && data.plan_until) {
      const bis = Date.parse(data.plan_until as string);
      if (Number.isFinite(bis) && bis > Date.now()) return "pro";
    }
    return "free";
  } catch (e) {
    console.error("[tier] unerwartet:", e instanceof Error ? e.message : e);
    return "free"; // im Zweifel restriktiv (keine Premium-Daten ausliefern)
  }
}
