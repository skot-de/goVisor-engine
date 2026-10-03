"use client";
import { createClient } from "./supabase/client";
import { dichte, merkmale } from "./dichte";
import { sendeEreignis } from "./telemetrie";

/* Analytics (Ticket #8) — eine dünne, pluggbare Event-Schicht. Sink-Reihenfolge:
 *  1) EIGENE SENKE → `/api/ereignis` → `gov_ereignisse` (0035). Seit 2026-10-02 die
 *     tragende Senke: kein Drittanbieter, keine Cookies, Daten bleiben in unserer Instanz.
 *  2) PostHog, falls `window.posthog` initialisiert ist (Integrationspunkt — braucht Key/Init,
 *     bewusst kein harter Dependency: `posthog-js` + init in einem Provider ergänzen, dann fließt es).
 *  3) In-Memory-Ring (`window.__gvEvents`) + console.debug — zum Prüfen ohne Senke.
 * Die Success-Fee-/HITL-Events aus dem Ticket sind als Konstanten vorbereitet; Revenue-Events
 * feuert der Server-Billing-Pfad, nicht der Client.
 *
 * ⚠ BIS ZUM 2026-10-02 GAB ES KEINE SENKE. Senke 1 existierte nicht, der PostHog-Zweig war
 *   tot (keine Abhängigkeit, keine Initialisierung, `window.posthog` nie gesetzt), und der
 *   Ring-Puffer verschwand beim Schließen des Tabs. Alle neun Ereignisse feuerten also ins
 *   Leere — gebaut, nicht verdrahtet. Wer hier etwas umbaut: `tests/test_telemetrie.py`
 *   prüft, dass `track()` die Senke weiterhin ruft.
 *
 * ⚠ NEUE EREIGNISSE GEHÖREN AN ZWEI STELLEN eingetragen: nach `EV` hier UND in die Liste
 *   `ERLAUBT` in `lib/telemetrieSenke.ts`. Der Server verwirft, was er nicht kennt — sonst
 *   wächst die Tabelle mit Tippfehlern zu. Die Wache oben prüft auch das. */

type Props = Record<string, unknown>;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare global { interface Window { posthog?: any; __gvEvents?: { event: string; props: Props; t: number }[]; } }

export function track(event: string, props: Props = {}) {
  if (typeof window === "undefined") return;
  try { sendeEreignis(event, props); } catch { /* Senke darf nie die Oberfläche stören */ }
  try { window.posthog?.capture?.(event, props); } catch { /* Sink optional */ }
  (window.__gvEvents ||= []).push({ event, props, t: Date.now() });
  if (window.__gvEvents.length > 200) window.__gvEvents.shift();
  if (process.env.NODE_ENV === "development") console.debug("[analytics]", event, props);
}

/* Attribution (Grundlage für Success-Fee #6 + North-Star „Wins Detected"): erster Detail-Klick
 * und erster Bewertungs-Tab-Klick je Lead. Nur bei aktiver Session, RLS-gebunden. No-op sonst. */
export async function recordLeadClick(leadId: string, lead?: Parameters<typeof dichte>[0]) {
  // DICHTE MITSCHREIBEN. Ohne sie beantwortet die Tabelle nur „welcher Lead wurde
  // geoeffnet", nicht die Frage, um die es geht: werden duenne Leads ueberhaupt geklickt?
  // Gemessen 2026-08-16 sind 58 % der Leads duenn — ob das jemanden stoert, weiss niemand.
  //
  // Nachtraeglich ist das NICHT rekonstruierbar: die Dichte eines Leads aendert sich, sobald
  // seine Unterlagen ankommen. Wer sie erst beim Auswerten berechnet, misst den Stand von
  // heute gegen einen Klick von letzter Woche.
  const d = lead ? dichte(lead) : null;
  const m = lead ? merkmale(lead) : null;
  track("lead_opened", { lead_id: leadId, dichte: d, merkmale: m });
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return;
    await sb.from("user_lead_interactions").upsert(
      { user_id: user.id, lead_id: leadId, dichte: d, merkmale: m },
      { onConflict: "user_id,lead_id", ignoreDuplicates: true });
  } catch { /* still no-op */ }
}

export async function recordAnalysis(leadId: string) {
  track("lead_analysis_opened", { lead_id: leadId });
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return;
    // first_analysis_at nur setzen, wenn noch leer (erster Bewertungs-Klick zählt)
    await sb.from("user_lead_interactions").upsert(
      { user_id: user.id, lead_id: leadId, first_analysis_at: new Date().toISOString() },
      { onConflict: "user_id,lead_id" });
  } catch { /* no-op */ }
}

// Event-Namen aus Ticket #8 (Revenue-Funnel) — Server-Billing referenziert dieselben Konstanten.
export const EV = {
  ONBOARDING_DONE: "onboarding_completed",
  EXPORT: "list_exported",
  BRIEFING: "briefing_generated",
  /* ⚠ `AWARD_MATCHED: "award_matched_to_user"` stand hier und wurde NIE gefeuert: die
   * Funktion, die einen Zuschlag einem Nutzer zuordnet, ist nicht gebaut. Ein Ereignis
   * fuer eine Funktion, die es nicht gibt, ist keine Vorbereitung, sondern eine leere
   * Zeile in jeder Auswertung. Es kommt zurueck, wenn die Zuordnung kommt — dann auch in
   * `ERLAUBT` in lib/telemetrieSenke.ts, sonst verwirft der Server es still. */
  /* Die vier FEE_*-Ereignisse sind am 2026-08-17 entfallen: die Erfolgsgebuehr
   * wurde als Modell verworfen. Wer sie sucht, findet sie in der Historie. */

  /* Outreach-Landing (`/t/<token>`).
   *
   * DREI Ereignisse, nicht eines. Die Frage ist „liest jemand die zweite Haelfte der
   * Seite", und der Klick auf den Wegweiser allein beantwortet sie NICHT: wenige Klicks
   * koennen heissen „niemand kommt dorthin" oder „alle scrollen ohnehin von selbst".
   * Das sind gegenteilige Befunde mit gegenteiligen Konsequenzen.
   *
   * Deshalb zusaetzlich `LANDING_FINDEN`, sobald der zweite Teil wirklich im Bild war.
   * Erst das Verhaeltnis traegt:
   *     FINDEN / GESEHEN                      kommt ueberhaupt jemand an?
   *     FINDEN mit viaWegweiser / FINDEN      hat der Wegweiser sie hingebracht?
   *
   * ⚠ KORREKTUR 2026-10-03: hier stand „WEGWEISER / FINDEN" mit einem eigenen Ereignis
   *   `LANDING_WEGWEISER: "landing_signpost_clicked"`. Das Ereignis wurde NIE gefeuert — die
   *   Wegweiser-Nutzung reist als Merkmal `viaWegweiser` an `LANDING_FINDEN` mit (bewusst so,
   *   s. LandingView.tsx Zeile 239). Die beschriebene Kennzahl war damit nicht berechenbar,
   *   und der Kommentar beschrieb einen aelteren Entwurf. Konstante entfernt, Verhaeltnis
   *   richtiggestellt. Gefunden von
   *   `tests/test_telemetrie.py::test_jedes_erlaubte_ereignis_hat_eine_aufrufstelle`.
   *
   * Mitgeschickt wird der TOKEN, nicht der Firmenname: der Token steht ohnehin in der
   * URL, der Name waere eine zusaetzliche Preisgabe an den Auswertungsdienst. */
  LANDING_GESEHEN: "landing_viewed",
  LANDING_FINDEN: "landing_second_half_seen",
  LANDING_CTA: "landing_cta_clicked",

  /* TRICHTER (0035/0036). Vier Stufen, und jede einzelne trennt zwei Abbruchgruenden
   * voneinander, die unterschiedliche Konsequenzen haben:
   *
   *     seite_gesehen           → Landingpage erreicht  (SEO wirkt)
   *     ONBOARDING_BEGONNEN     → Onboarding geoeffnet   (der Einstieg ueberzeugt)
   *     ONBOARDING_FIRMA_ERKANNT→ Firma gefunden         (Daten reichen aus)
   *     KONTO_ANGELEGT          → Konto entstanden       (Vertrauen genuegt)
   *     ONBOARDING_DONE         → Profil fertig          (der Weg ist gehbar)
   *
   * ⚠ DIESE DREI STANDEN AM 2026-10-02 IN DER ERLAUBNISLISTE DES SERVERS, ABER NIEMAND
   *   FEUERTE SIE. Deklariert und nicht verdrahtet, also derselbe Fehler, den diese Datei
   *   schon einmal hatte. `tests/test_telemetrie.py` prueft jetzt BEIDE Richtungen: jedes
   *   `EV`-Ereignis ist serverseitig erlaubt, UND jedes erlaubte Ereignis hat eine
   *   Aufrufstelle. */
  ONBOARDING_BEGONNEN: "onboarding_begonnen",
  ONBOARDING_FIRMA_ERKANNT: "onboarding_firma_erkannt",
  KONTO_ANGELEGT: "konto_angelegt",
} as const;
