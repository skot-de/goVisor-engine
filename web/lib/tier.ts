import "server-only";
import { createClient } from "@/lib/supabase/server";
import { stufeZuTier } from "@/lib/stufeZuTier";

export type Tier = "free" | "pro";

/**
 * Server-seitiger Zugangs-Tier des aktuellen Nutzers — steuert die Premium-Redaktion in den
 * Daten-Routes (lib/redact.ts). Die Paywall ist NUR sicher, wenn die echten Premium-Werte den
 * Server gar nicht erst verlassen (CSS-Blur allein ist per DevTools lesbar, s. docs/security-review.md).
 *
 * **Env-Gate `PAYWALL_ENFORCED`:**
 * - nicht gesetzt/"false" (heute, Billing = Stub) → **jeder ist `pro`** → keine Redaktion, das
 *   aktuelle „Pro-für-alle"-Demo-Verhalten (`accountLimit = false` im Client) bleibt exakt gleich.
 * - "true" (wenn Billing live geht) → Tier kommt aus der Supabase-Session. Dann MUSS der
 *   Client-`accountLimit` aus derselben Quelle kommen.
 *
 * ── DIE STUFE HÄNGT AN DER ORGANISATION, NICHT AM NUTZER (2026-10-01, Preismodell v1.9 §2) ──
 *
 * Hier stand `user_profiles.plan`. Abo, Seats und Unternehmensprofile hängen aber seit 0024 an
 * `organizations` — zwei Quellen für eine Aussage, und sie driften: wer im internen
 * Kontenwerkzeug `organizations.plan` setzt, ändert am Gating nichts, und ein Nutzer konnte
 * bezahlte Rechte tragen, die seine Organisation nicht hat. Sven: „tier gehört nur an die
 * organisation". Gelesen wird deshalb `organizations.tier` über `user_profiles.org_id`.
 *
 * ⚠ ERFORDERT MIGRATION 0028. Ohne sie kennt die Datenbank `tier`/`abo_status` nicht und die
 * Abfrage wirft. Das ist genau die Falle, die dieser Datei schon einmal gestellt wurde: bis
 * 2026-08-22 stand hier `select("tier")` auf eine Spalte, die es in keiner Migration gab.
 * Solange `PAYWALL_ENFORCED` aus war, fiel das niemandem auf; am Tag der Scharfschaltung hätte
 * der catch daraus lautlos „free" gemacht und JEDER Zahlende wäre auf den Free-Umfang gefallen.
 * Deshalb unten: fehlende Spalte wird als KONFIGURATIONSFEHLER erkannt und benannt, nicht als
 * „zahlt nicht" verbucht.
 *
 * ⚠ DIE VIER STUFEN WERDEN HIER AUF ZWEI ABGEBILDET. `Tier` kennt `free|pro`, weil die
 * Redaktion in `lib/redact.ts` nur diese zwei Ebenen unterscheidet. Das Gating „Strategie
 * schaltet den Bereich Strategie frei" (§3) braucht die rohe Stufe und ist NICHT gebaut; wer
 * das nachzieht, holt sie aus derselben Abfrage statt eine zweite aufzumachen.
 */
export async function getTier(): Promise<Tier> {
  if (process.env.PAYWALL_ENFORCED !== "true") return "pro"; // Gate aus → wie heute (alle Pro)
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return "free";

    // EIN Rundlauf über den Fremdschlüssel user_profiles.org_id → organizations.
    // Die RLS-Policy `org_select_member` (0024) gibt genau die eigene Organisation heraus.
    const { data, error } = await supabase
      .from("user_profiles")
      .select("org_id, organizations(tier, abo_status, plan_until, trial_ends_at)")
      .eq("id", user.id)
      .maybeSingle();

    // Ein FEHLER ist nicht dasselbe wie „zahlt nicht". Wer beides gleich behandelt, merkt
    // einen Schemafehler erst an den Beschwerden zahlender Kunden.
    if (error) {
      // 42703 = undefined_column. Heisst: 0028 ist nicht eingespielt. Eigene Meldung, weil
      // „Abo-Abfrage fehlgeschlagen" den Betreiber in die falsche Richtung schickt.
      if (error.code === "42703") {
        console.error(
          "[tier] FATAL: organizations.tier fehlt, Migration 0028 ist nicht eingespielt. " +
          "Bis dahin MUSS PAYWALL_ENFORCED aus bleiben, sonst fallen alle Zahlenden auf free.",
        );
      } else {
        console.error("[tier] Abo-Abfrage fehlgeschlagen, liefere free:", error.message);
      }
      return "free";
    }

    // Kein org_id ist ein DATENFEHLER, kein Free-Kunde. 0024 hat den Bestand vollständig
    // nachgezogen (die Migration bricht ab, wenn ein Nutzer ohne Org bleibt), aber
    // `handle_new_user` ist noch nicht erweitert (0024, Block „Phase 2") — eine
    // Selbstregistrierung kann also einen Nutzer ohne Organisation erzeugen. Gemessen am
    // 2026-10-01: 0 von 14. Fail-closed mit lauter Meldung, damit es auffällt, bevor es wehtut.
    if (!data?.org_id) {
      console.error(`[tier] Nutzer ${user.id} hat keine Organisation (org_id null) — liefere free. ` +
                    "Ursache pruefen: handle_new_user legt noch keine Org an (0024 Phase 2).");
      return "free";
    }
    // Supabase typisiert eine 1:1-Einbettung je nach Version als Objekt ODER Array.
    const org = (Array.isArray(data.organizations) ? data.organizations[0] : data.organizations) as
      { tier?: string; abo_status?: string; plan_until?: string; trial_ends_at?: string } | null;
    if (!org) {
      console.error(`[tier] org ${data.org_id} nicht lesbar (RLS?) — liefere free.`);
      return "free";
    }

    // Die Abbildung der vier Stufen auf free|pro steht in `stufeZuTier.js` — reines JS,
    // damit `web/scripts/pruefe-stufe.mjs` die echte Funktion aufrufen kann statt den
    // Quelltext abzutasten.
    return stufeZuTier(org)
  } catch (e) {
    console.error("[tier] unerwartet:", e instanceof Error ? e.message : e);
    return "free"; // im Zweifel restriktiv (keine Premium-Daten ausliefern)
  }
}
