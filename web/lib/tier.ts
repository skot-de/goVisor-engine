import "server-only";
import { createClient } from "@/lib/supabase/server";
import { stufeZuTier } from "@/lib/stufeZuTier";

export type Tier = "free" | "analyse" | "strategie";

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
 * ── DIE BEIDEN BEZAHLTEN STUFEN SIND GETRENNT (2026-10-01) ──────────────────────────────
 *
 * ⚠ HIER STAND `Tier = "free" | "pro"`, UND DAS KOSTETE GELD. Eine einzige Schwelle fuer zwei
 * bezahlte Stufen: `redact.ts` prueffte durchgehend `if (tier === "pro") return map`. Wer
 * Analyse fuer 99 € kaufte, bekam damit Strategie fuer 349 € mit, obwohl §3.6 den ganzen
 * Strategie-Bereich auf `++` legt („Keine Ausnahme, kein Free-Kontingent"). 250 € Unterschied
 * je Kunde und Monat — unsichtbar, weil kein Test die Stufen unterscheiden KONNTE.
 *
 * `Tier` traegt jetzt die echte Stufe. Wer sie auswertet, fragt NICHT auf Gleichheit ab,
 * sondern nimmt `darfAnalyse()` / `darfStrategie()` aus `lib/stufeZuTier.js` — sonst steht die
 * Schwelle wieder an N Stellen und die naechste Stufe wird an N−1 davon vergessen.
 *
 * ⚠ `trial` wird zu `strategie`, nicht zu `analyse`: §3a gibt vier Wochen „alle Funktionen
 * BEIDER Stufen".
 */
export async function getTier(): Promise<Tier> {
  // ⚠ Gate aus → VOLLE Stufe, nicht die mittlere. Hier stand `return "pro"`; mit zwei
  // getrennten Stufen muss es die obere sein, sonst wuerde das AUSSCHALTEN der Paywall
  // ploetzlich den Strategie-Bereich sperren. Verhalten bleibt damit exakt wie bisher.
  if (process.env.PAYWALL_ENFORCED !== "true") return "strategie";
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
    // nachgezogen (die Migration bricht ab, wenn ein Nutzer ohne Org bleibt), und 0025 hat
    // `handle_new_user` so erweitert, dass jede Selbstregistrierung Org, erstes Profil und
    // `role='owner'` anlegt. Gemessen am 2026-10-01: 0 von 13 Nutzern ohne Organisation.
    //
    // ⚠ Hier stand, `handle_new_user` sei noch nicht erweitert — das war falsch, 0024 hatte
    // es nur als Phase 2 ANGEKÜNDIGT und 0025 hat es ausgeführt. Der Riegel bleibt trotzdem:
    // ein eingeladener Nutzer übergeht laut 0025 bewusst den Org-Zweig, und bei einem
    // halben Invite-Pfad entsteht genau dieser Zustand. Fail-closed mit lauter Meldung.
    if (!data?.org_id) {
      console.error(`[tier] Nutzer ${user.id} hat keine Organisation (org_id null) — liefere free. ` +
                    "Ursache pruefen: handle_new_user (0025) sollte sie anlegen.");
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
