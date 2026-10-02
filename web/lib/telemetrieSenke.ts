import "server-only";
import { createAdminClient } from "@/lib/supabase/admin";

/**
 * Telemetrie, Serverseite — die EINZIGE Stelle, die nach `gov_ereignisse` schreibt.
 *
 * Zwei Zugaenge, eine Senke:
 *   1. `/api/ereignis` nimmt die Ereignisse des Browsers an (Klicks, Verweildauer, Scrolltiefe).
 *   2. `erfasseSeitenaufruf()` wird von Server-Komponenten gerufen, fuer die oeffentlichen
 *      Landingpages. Die duerfen kein Javascript brauchen (Ticket 17 §6.2: Googlebot bekommt
 *      exakt dasselbe HTML), also gibt es dort keinen Browser, der etwas senden koennte.
 *
 * ⚠ WARUM DIE PRUEFUNG HIER UND NICHT IM CLIENT LIEGT. Der Client prueft ebenfalls, aber
 *   seine Pruefung ist eine Hoeflichkeit: wer die Route direkt aufruft, schickt was er will.
 *   Erst diese Datei entscheidet, was in der Tabelle landet. Deshalb hat `anon` kein
 *   Schreibrecht auf `gov_ereignisse` (s. 0035) — der Weg fuehrt zwingend hier durch.
 *
 * ⚠ DREI DINGE WERDEN VERARBEITET UND NICHT GESPEICHERT: IP-Adresse, User-Agent und der
 *   vollstaendige Referrer. Aus dem User-Agent bleibt ein `ist_bot`-Urteil, aus dem Referrer
 *   der Host. Die IP wird gar nicht angefasst — auch nicht gehasht. Ein gehashter
 *   Tageswert waere ein pseudonymes Wiedererkennungsmerkmal, und fuer die Fragen, die hier
 *   beantwortet werden sollen, braucht es keines: „wie viele Aufrufe" und „wie lange" gehen
 *   ohne. Der Preis ist bekannt und akzeptiert: ein Neuladen zaehlt doppelt.
 */

/** Erlaubte Ereignisnamen. Was hier nicht steht, wird verworfen.
 *
 * ⚠ EINE LISTE, KEIN FREITEXT. Sonst waechst die Tabelle mit Tippfehlern zu
 * (`lead_opend`, `Lead_Opened`), und jede Auswertung muesste raten, welche Schreibweise
 * gemeint war. Neue Ereignisse gehoeren hierher UND nach `EV` in `analytics.ts`. */
export const ERLAUBT = new Set([
  // Bestand aus Ticket #8 (EV in analytics.ts)
  "lead_opened", "lead_analysis_opened", "lead_marked_won",
  "onboarding_completed", "list_exported", "briefing_generated",
  "award_matched_to_user",
  "landing_viewed", "landing_signpost_clicked", "landing_second_half_seen",
  "landing_cta_clicked",
  // Neu mit 0035: die klassischen Kennzahlen
  "seite_gesehen",        // Seitenaufruf (Client ODER Server)
  "seite_verlassen",      // mit dauer_ms + tiefe_pct
  "klick",                // Klickkarte: Element + relative Position
  // Trichter
  "onboarding_begonnen", "onboarding_firma_erkannt", "konto_angelegt",
]);

/** Ereignis, wie es in die Tabelle geht. Alles optional ausser `art`. */
export type Ereignis = {
  art: string;
  sitzung?: string | null;
  pfad?: string | null;
  props?: Record<string, unknown>;
  dauer_ms?: number | null;
  tiefe_pct?: number | null;
  ziel?: string | null;
  ziel_x_pct?: number | null;
  ziel_y_pct?: number | null;
  viewport_w?: number | null;
  viewport_h?: number | null;
  herkunft?: string | null;
  ist_bot?: boolean;
  nutzer_id?: string | null;
  org_id?: string | null;
};

/* ─────────────────────────────────────────────────────────── Normalisierung */

/** Pfad ohne Query-String und ohne Fragment, auf 300 Zeichen beschnitten.
 *
 * ⚠ Der Query-String MUSS weg. Er kann personenbezogene Parameter tragen (Suchbegriffe,
 * Mailadressen aus Einladungslinks, `?token=` der Outreach-Landing). Dass der Client ihn
 * schon abschneidet, genuegt nicht — s. Kopfkommentar. */
export function normalisierePfad(roh: unknown): string | null {
  if (typeof roh !== "string" || !roh) return null;
  const ohne = roh.split("?")[0].split("#")[0].trim();
  if (!ohne.startsWith("/")) return null;
  return ohne.slice(0, 300);
}

/** Aus einem Referrer nur den Host. Leer, wenn es die eigene Seite ist oder nichts da war.
 *
 * ⚠ NIE die vollstaendige Adresse: ein Referrer von einer Suchmaschine traegt den
 * Suchbegriff, und der gehoert einer fremden Person. */
export function herkunftHost(referer: unknown, eigenerHost?: string | null): string | null {
  if (typeof referer !== "string" || !referer) return null;
  try {
    const h = new URL(referer).hostname.toLowerCase();
    if (!h || (eigenerHost && h === eigenerHost.toLowerCase())) return null;
    return h.slice(0, 120);
  } catch {
    return null;
  }
}

/** Ist der Aufrufer ein Crawler?
 *
 * ⚠ DIESE FRAGE ENTSCHEIDET, OB DIE ZAHLEN ETWAS WERT SIND. Die oeffentlichen Landingpages
 * SIND ein SEO-Kanal; dort sind Suchmaschinen der erwartete Hauptverkehr. Wer sie mitzaehlt,
 * bekommt eine Trichterzahl, die nach OBEN verzerrt ist — sie sieht nach Erfolg aus, wo
 * keiner ist. Deshalb faellt das Urteil bei der Erfassung und nicht erst beim Auswerten.
 *
 * ⚠ Die Liste ist bewusst grob und faengt eher zu viel als zu wenig: ein als Bot verworfener
 * Mensch kostet eine Zeile, ein als Mensch gezaehlter Bot verdirbt eine Kennzahl. Wer die
 * Richtung umdreht, sollte das begruenden. Die Modell-Abrufer (GPTBot, ClaudeBot, …) stehen
 * mit drin: fuer die Grounding Page sind sie das ZIEL, aber eben keine Interessenten. */
const BOT_MUSTER = [
  "bot", "crawler", "spider", "crawl", "slurp", "search",
  "facebookexternalhit", "ia_archiver", "wget", "curl", "python-requests",
  "headlesschrome", "phantomjs", "lighthouse", "pagespeed", "preview",
  "monitor", "uptime", "pingdom", "semrush", "ahrefs", "mj12", "dotbot",
  "gptbot", "claudebot", "ccbot", "perplexity", "anthropic", "oai-searchbot",
];
export function istBot(userAgent: unknown): boolean {
  if (typeof userAgent !== "string" || !userAgent.trim()) return true; // kein UA = kein Browser
  const u = userAgent.toLowerCase();
  return BOT_MUSTER.some((m) => u.includes(m));
}

const ganzzahl = (v: unknown, min: number, max: number): number | null => {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return null;
  return Math.min(max, Math.max(min, Math.round(n)));
};

/** Ein eingehendes Ereignis auf das reduzieren, was gespeichert werden darf.
 *  `null` heisst: verwerfen. */
export function pruefe(roh: unknown, zusatz: Partial<Ereignis> = {}): Ereignis | null {
  if (!roh || typeof roh !== "object") return null;
  const e = roh as Record<string, unknown>;
  const art = typeof e.art === "string" ? e.art : "";
  if (!ERLAUBT.has(art)) return null;

  // ⚠ `props` wird auf 2 KB begrenzt, damit die Tabelle nicht zum Ablageort wird. Wer mehr
  //   braucht, braucht eine eigene Spalte — dann ist auch jemandem aufgefallen, WAS da liegt.
  let props: Record<string, unknown> = {};
  if (e.props && typeof e.props === "object" && !Array.isArray(e.props)) {
    const s = JSON.stringify(e.props);
    props = s.length <= 2048 ? (e.props as Record<string, unknown>) : { gekuerzt: true };
  }

  return {
    art,
    sitzung: typeof e.sitzung === "string" ? e.sitzung.slice(0, 64) : null,
    pfad: normalisierePfad(e.pfad),
    props,
    dauer_ms: ganzzahl(e.dauer_ms, 0, 86_400_000),
    tiefe_pct: ganzzahl(e.tiefe_pct, 0, 100),
    ziel: typeof e.ziel === "string" ? e.ziel.slice(0, 200) : null,
    ziel_x_pct: ganzzahl(e.ziel_x_pct, 0, 100),
    ziel_y_pct: ganzzahl(e.ziel_y_pct, 0, 100),
    viewport_w: ganzzahl(e.viewport_w, 0, 20_000),
    viewport_h: ganzzahl(e.viewport_h, 0, 20_000),
    ...zusatz,
  };
}

/* ─────────────────────────────────────────────────────────────── Schreiben */

/**
 * Schreibt Ereignisse. Wirft NIE.
 *
 * ⚠ FAIL-OPEN IST HIER PFLICHT, NICHT BEQUEMLICHKEIT. Die Senke haengt an einer
 *   oeffentlichen Seite, die laut Ticket 17 §11 ein LCP unter 2,5 s halten muss und der
 *   SEO-Kanal des Produkts ist. Eine Messung, die bei einem Supabase-Ausfall die Seite
 *   mitnimmt, waere ein Eigentor: man verliert den Kanal, um die Statistik zu retten.
 *   Deshalb wird jeder Fehler nur protokolliert.
 */
export async function schreibe(ereignisse: Ereignis[]): Promise<number> {
  if (!ereignisse.length) return 0;
  try {
    const sb = createAdminClient();
    const { error } = await sb.from("gov_ereignisse").insert(ereignisse);
    if (error) {
      console.error("[telemetrie] Schreiben fehlgeschlagen:", error.message);
      return 0;
    }
    return ereignisse.length;
  } catch (e) {
    console.error("[telemetrie] Senke nicht erreichbar:", (e as Error)?.message);
    return 0;
  }
}

/**
 * Seitenaufruf einer SERVER-Komponente erfassen (oeffentliche Landingpages).
 *
 * ⚠ RUFT `after()` AUF, laeuft also NACH der Antwort. Ein synchroner Schreibvorgang je
 *   Seitenaufruf kostet Latenz an genau der Stelle, an der Ticket 17 keine hat: §11 verlangt
 *   LCP < 2,5 s, und die Seite existiert, um in Suchergebnissen zu bestehen.
 *
 * ⚠ ERZEUGT KEIN HTML. Kein Zaehlpixel, kein Script-Tag, nichts. §6.2 verlangt, dass
 *   Googlebot exakt dieselbe Seite bekommt wie ein Mensch; ein Zaehlpixel waere ein
 *   Unterschied im Markup und zugleich nutzlos, weil Crawler es nicht laden.
 *
 * Aufruf aus einer Server-Komponente oder Route:
 *     import { headers } from "next/headers";
 *     erfasseSeitenaufruf(await headers(), "/ausschreibung/" + slug, { exklusivSchicht: ex });
 */
export function erfasseSeitenaufruf(
  kopfzeilen: Headers,
  pfad: string,
  props: Record<string, unknown> = {},
): void {
  try {
    const ua = kopfzeilen.get("user-agent");
    const eigener = kopfzeilen.get("host");
    const ereignis: Ereignis = {
      art: "seite_gesehen",
      sitzung: null, // Server-Erfassung, kein sessionStorage — s. 0035
      pfad: normalisierePfad(pfad),
      props,
      herkunft: herkunftHost(kopfzeilen.get("referer"), eigener),
      ist_bot: istBot(ua),
    };
    // `after` ist in Next 15 stabil und genau fuer diesen Fall da: Arbeit nach der Antwort,
    // ohne die Antwort zu verzoegern und ohne dass die Laufzeit sie abschneidet (ein
    // freischwebendes Promise waere genau das Risiko).
    import("next/server")
      .then(({ after }) => after(() => schreibe([ereignis])))
      .catch(() => { /* fail-open, s. schreibe() */ });
  } catch {
    /* fail-open: eine Messung darf die Seite nie kippen */
  }
}
