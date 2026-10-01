import "server-only";
import { loadDataFile } from "@/lib/dataSource";

/**
 * Öffentliche Ausschreibungs-Seite (Ticket #17) — die Datenschicht.
 *
 * Übersetzt einen internen Lead in die öffentlich zeigbare Form einer One-Pager-Seite
 * (`/ausschreibung/<slug>`). Die Mechanik aus dem Ticket, auf unser aktuelles Setup gelegt:
 * gelesen wird aus den bestehenden `leads-<branche>.json` + `detail-<branche>.json`, nichts
 * Neues in der Pipeline.
 *
 * ⚠ ZWEI RIEGEL, BEIDE DEFAULT AUS — „Risiko vor Reichweite" aus dem Ticket:
 *   1. `OEFFENTLICHE_SEITEN` schaltet die Seiten überhaupt frei. Aus → es gibt sie nicht
 *      (die Route gibt 404). In Produktion liegt zusätzlich die Coming-Soon-Sperre davor;
 *      Deploy, Vorhang-Ausnahme und das Aufheben von `noindex` sind Svens Go-Live-Schritte,
 *      nicht Teil dieses Baus.
 *   2. `OEFFENTLICH_NAMEN` erlaubt erst, Namen DRITTER Firmen (Vorgänger, Top-Auftragnehmer)
 *      zu zeigen — und auch dann nur bei eindeutig juristischer Person (Rechtsform-Regel).
 *      Aus → nur Anzahlen und Statistik ohne Namen. Das ist zugleich der „globale
 *      Namens-Schalter" aus §12. Bis die Vorab-Gates G1 (Präzision) und G2 (Recht) bestanden
 *      sind, bleibt er aus. Der Name des AUFTRAGGEBERS (öffentliche Stelle) ist davon nicht
 *      betroffen — der ist ohnehin öffentlich.
 *
 * ⚠ Das einzige gesperrte Element (§6.2) ist die Wechsel-Wahrscheinlichkeit (`wechsel`). Ihr
 *   WERT verlässt diese Datei nie — nach außen geht allein `hatVerdraengung: boolean`, damit
 *   die Seite den gesperrten Block zeigen oder weglassen kann. Nie der Wert, auch nicht im
 *   Payload oder in strukturierten Daten.
 */

const BRANCHEN = ["it", "bau", "medizin", "beratung", "sicherheit", "energie", "ohne"] as const;

/** Schalter 1: Seiten überhaupt da? Default aus. */
export const OEFFENTLICHE_SEITEN_AN = process.env.OEFFENTLICHE_SEITEN === "1";
/** Schalter 2: Dürfen Namen Dritter gezeigt werden? Default aus (= globaler Namens-Schalter §12). */
export function namenErlaubt(): boolean {
  return process.env.OEFFENTLICH_NAMEN === "1";
}

/**
 * Rechtsform-Regel §6.2: der Name einer DRITTEN Firma darf nur stehen, wenn sie eindeutig
 * eine juristische Person ist (Kapital-/Genossenschaft, öffentliches Unternehmen). e.K., GbR,
 * Freiberufler, Namensbüros oder nicht erkennbare Rechtsform → Standard „ausblenden".
 * ⚠ Bewusst konservativ: im Zweifel NICHT zeigen. Lieber eine zeigbare Firma verschweigen als
 *   eine natürliche Person nennen.
 */
const JURISTISCH = /\b(?:g?GmbH|mbH|AG|SE|UG|KGaA|eG|e\.?\s?G\.?|Aktiengesellschaft|Genossenschaft|Anstalt des öffentlichen Rechts|AöR|Körperschaft|GmbH\s?&\s?Co)\b/i;
export function rechtsformErlaubt(name: string | null | undefined): boolean {
  if (!name) return false;
  const n = name.trim();
  if (n.length < 2) return false;
  // Ausschluss-Formen, die wie eine Firma aussehen, aber keine juristische Person sind.
  if (/\b(?:e\.?\s?K\.?|GbR|Einzelunternehmen|freiberuflich)\b/i.test(n)) return false;
  return JURISTISCH.test(n);
}

/** Herkunftsschicht (§13 `source_layer`): TED oberschwellig vs. national (unterschwellig). */
function quelleAus(lead: LeadRoh): "ted" | "national" {
  const id = String(lead.id ?? "");
  // DÖE/national: UUID oder reine Zahl ohne Jahres-Suffix. TED: <zahl>_<jahr>.
  if (/^\d+_\d{4}$/.test(id)) return "ted";
  return "national";
}

/** Zustand der Seite (§9 Lebenszyklus), so weit die Daten es heute hergeben. */
function zustandAus(lead: LeadRoh): "offen" | "wertung" | "zuschlag" | "unbekannt" {
  if (Array.isArray(lead.zuschlag) && lead.zuschlag.length > 0) return "zuschlag";
  const d = lead.frist?.date;
  if (d && lead.frist?.src === "echt") {
    // date liegt als "TT.MM.JJJJ" vor.
    const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(d);
    if (m) {
      const frist = new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
      const heute = new Date();
      heute.setHours(0, 0, 0, 0);
      return frist < heute ? "wertung" : "offen";
    }
  }
  return "unbekannt";
}

/**
 * Exklusivschicht (§11): der GRUND, warum die Seite indexierbar sein darf — und zwar
 * seitenspezifisch. Nur eines davon muss gelten:
 *   - verifizierter Vorgängervertrag (`ersetzt`),
 *   - Auftraggeber-Historie mit n ≥ 6 in der CPV-Gruppe (`buyerProfile`),
 *   - Zyklushistorie (`kette`, Vorgänger/Nachfolger verknüpft).
 * Segment- und Anbieterzahlen zählen NICHT (die stehen auf vielen Seiten gleich).
 */
function exklusivSchicht(
  lead: LeadRoh,
  detail: DetailRoh | null,
): "predecessor" | "buyer_history" | "cycle" | null {
  if (Array.isArray(lead.ersetzt) && lead.ersetzt.length > 0) return "predecessor";
  if (Array.isArray(lead.kette) ? lead.kette.length > 0 : !!lead.kette) return "cycle";
  // §11 nennt als dritte Exklusivschicht „Auftraggeber-Historie mit n>=6 in der CPV-GRUPPE
  // dieser Ausschreibung". Dieses Tor zaehlt hier NICHT zur Indexierbarkeit — aus einem Grund,
  // der auch dann gilt, wenn man die Zahl sauber berechnet:
  // Gemessen am 2026-10-01 (Peer, docs/weiterentwicklung/sichtbarkeit-in-ki-antworten.md §8)
  // laesst das Tor 71.053 von 90.979 Leads durch = 78,1 %. Eine Bedingung, die vier von fuenf
  // Seiten erfuellen, gatet nicht, sie oeffnet — und „diese Vergabestelle hat in der Division
  // schon >=6 mal vergeben" ist genau die Art Segmentzahl, die §11 selbst ausschliesst, keine
  // seitenspezifische Erkenntnis.
  // ⚠ NICHT der Grund (eine fruehere Fassung behauptete das): „die Daten tragen die Zahl
  // nicht". `buyerProfile` im web/data-JSON hat zwar nur `total`, aber die CPV-gruppen-genaue
  // Zahl ist aus party_entity (role=buyer) × notices.cpv_main herleitbar (20.850 Paare mit
  // n>=6). Wer das merkt, baut das Tor sonst wieder ein — es bleibt draussen wegen der 78 %,
  // nicht wegen fehlender Daten.
  // Die Indexierbarkeit ruht auf den zwei starken, belegten Toren (Vorgaenger ~4.275, Zyklus
  // ~47) und haengt dadurch auch nicht mehr am Detail-Laden. Die Auftraggeber-Statistik wird
  // weiter gezeigt (auftraggeberStatistik), sie indexiert nur nicht.
  return null;
}

/** Leistungszusammenfassung §6.5 — EXTRAKTIV: nur vorhandener Bekanntmachungstext, gekürzt.
 *  Kein neuer LLM-Lauf, also keine Halluzination. Bei Zweifel (zu kurz) lieber weglassen. */
function leistungAus(lead: LeadRoh): string | null {
  const roh = (lead.beschreibung ?? "").replace(/\s+/g, " ").trim();
  if (roh.length < 40) return null;
  if (roh.length <= 600) return roh;
  // An einer Satzgrenze kürzen, nicht mitten im Wort.
  const kurz = roh.slice(0, 600);
  const grenze = Math.max(kurz.lastIndexOf(". "), kurz.lastIndexOf("! "), kurz.lastIndexOf("? "));
  return (grenze > 200 ? kurz.slice(0, grenze + 1) : kurz) + " …";
}

/* ------------------------------------------------------------------ Typen */

type LeadRoh = {
  id?: string;
  titel?: string;
  buyer?: string;
  buyerShort?: string;
  beschreibung?: string;
  verfahren?: string;
  contractKind?: string;
  cpv?: string;
  cpvLabel?: string;
  nuts?: string;
  region?: string;
  land?: string;
  frist?: { date?: string; src?: string; uhrzeit?: string; tage?: number };
  volumen?: { src?: string; wert?: string };
  lose?: Array<{ nr?: number; titel?: string; cpv?: string; region?: string; wert?: string }>;
  unterlagen?: { url?: string; access?: string; source?: string };
  wechsel?: string | null;
  ersetzt?: string[] | null;
  kette?: unknown;
  zuschlag?: unknown[];
  zuschlagNamen?: string[] | null;
  is_nationwide?: boolean;
  pub?: string | null;
};

type DetailRoh = {
  buyerProfile?: {
    name?: string;
    total?: number;
    zeitraum?: string;
    top3?: unknown;
    topWinners?: Array<{ name?: string; wins?: number }>;
  };
  marktSegment?: { label?: string; nAwards?: number; top3?: unknown };
};

export type OeffentlicheSeite = {
  noticeId: string;
  slug: string;
  branche: string;
  titel: string;
  buyer: string; // öffentlicher Auftraggeber — immer sichtbar
  kennungen: { ted: string | null; platform: string | null };
  verfahren: string | null;
  cpv: string | null;
  cpvLabel: string | null;
  nuts: string | null;
  region: string | null;
  land: string | null;
  bundesweit: boolean;
  frist: { date: string; uhrzeit: string | null } | null; // nur bei echt
  volumen: string | null; // nur bei echtem Wert
  lose: Array<{ nr: number | null; titel: string; cpv: string | null }>;
  leistung: string | null;
  unterlagenUrl: string | null;
  auftraggeberStatistik: { vergabenGesamt: number | null; zeitraum: string | null };
  auftraggeberAggregat: { name: string; wins: number | null; n: number } | null; // nur mit Namens-Riegel
  vorgaengerName: string | null; // nur mit Namens-Riegel + Rechtsform
  aktiveAnbieter: number | null;
  hatVerdraengung: boolean; // steuert den EINEN gesperrten Block — nie der Wert
  zustand: "offen" | "wertung" | "zuschlag" | "unbekannt";
  gewinner: string[] | null; // Zuschlagsphase, Namen nur mit Riegel + Rechtsform
  exklusivSchicht: "predecessor" | "buyer_history" | "cycle" | null;
  indexierbar: boolean;
  quelle: "ted" | "national";
};

/* ------------------------------------------------------------------ Slug */

/** Stabiler Teil des Slugs: die normalisierte notice_id (Unterstrich → Bindestrich). */
export function idSlug(id: string): string {
  return String(id).replace(/_/g, "-").toLowerCase();
}

/** Titel-Teil des Slugs: klein, nur [a-z0-9-], deutsche Umlaute aufgelöst, gekürzt. */
export function titelSlug(titel: string | undefined): string {
  return (titel ?? "")
    .toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80)
    .replace(/-+$/g, "");
}

/** Voller, kanonischer Slug: `<idSlug>-<titelSlug>`. 301-stabil über die id. */
export function vollSlug(lead: LeadRoh): string {
  const t = titelSlug(lead.titel);
  const i = idSlug(String(lead.id ?? ""));
  return t ? `${i}-${t}` : i;
}

/** Aus einem angefragten Slug die id herauslösen (führender id-Teil). */
export function idAusSlug(slug: string): string | null {
  const s = slug.toLowerCase();
  // TED: <zahl>-<jahr>.  National: reine Zahl oder UUID.
  const m = /^(\d+-\d{4}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\d+)/.exec(s);
  return m ? m[1] : null;
}

/* ------------------------------------------------------------------ Transform */

/** Interner Lead (+ optionales Detail) → öffentlich zeigbare Form. Rein, keine Seiteneffekte. */
export function zuOeffentlich(lead: LeadRoh, detail: DetailRoh | null, branche: string): OeffentlicheSeite {
  const namen = namenErlaubt();
  const bp = detail?.buyerProfile;

  // Vorgängername nur bei Riegel UND Rechtsform. `ersetzt` trägt notice_ids, keine Namen —
  // einen Namen kennen wir hier (ohne Zusatz-Lookup) nur über den Top-Auftragnehmer; den
  // zeigen wir als „Auftraggeber-Aggregat", nicht als Vorgänger. Vorgängername bleibt daher
  // vorerst null (korrekt: lieber keine Behauptung, s. §6.3 „Unsicher").
  const vorgaengerName: string | null = null;

  // Auftraggeber-Aggregat §6.3: EIGENER Abschnitt, Namen nur mit Riegel + Rechtsform, n ≥ 6.
  let auftraggeberAggregat: OeffentlicheSeite["auftraggeberAggregat"] = null;
  const topW = bp?.topWinners?.[0];
  if (namen && topW?.name && rechtsformErlaubt(topW.name) && typeof bp?.total === "number" && bp.total >= 6) {
    auftraggeberAggregat = { name: topW.name, wins: topW.wins ?? null, n: bp.total };
  }

  // Zuschlag: Gewinnernamen nur mit Riegel + je Name die Rechtsform-Regel.
  let gewinner: string[] | null = null;
  if (Array.isArray(lead.zuschlag) && lead.zuschlag.length > 0) {
    const namenRoh = (lead.zuschlagNamen ?? []).filter(Boolean) as string[];
    gewinner = namen ? namenRoh.filter((n) => rechtsformErlaubt(n)) : [];
  }

  const platform = plattformIdAus(lead.unterlagen?.url);

  return {
    noticeId: String(lead.id ?? ""),
    slug: vollSlug(lead),
    branche,
    titel: (lead.titel ?? "").trim(),
    buyer: (lead.buyer ?? lead.buyerShort ?? "").trim(),
    kennungen: { ted: quelleAus(lead) === "ted" ? idSlug(String(lead.id ?? "")) : null, platform },
    verfahren: lead.verfahren ?? null,
    cpv: lead.cpv ?? null,
    cpvLabel: lead.cpvLabel || null,
    nuts: lead.nuts || null,
    region: lead.region || null,
    land: lead.land || null,
    bundesweit: !!lead.is_nationwide,
    frist: lead.frist?.src === "echt" && lead.frist.date
      ? { date: lead.frist.date, uhrzeit: lead.frist.uhrzeit ?? null }
      : null,
    volumen: lead.volumen?.src === "echt" && lead.volumen.wert ? String(lead.volumen.wert) : null,
    lose: (lead.lose ?? []).map((l) => ({
      nr: l.nr ?? null,
      titel: (l.titel ?? "").trim(),
      cpv: l.cpv || null,
    })).filter((l) => l.titel),
    leistung: leistungAus(lead),
    unterlagenUrl: lead.unterlagen?.url || null,
    auftraggeberStatistik: { vergabenGesamt: bp?.total ?? null, zeitraum: bp?.zeitraum ?? null },
    auftraggeberAggregat,
    vorgaengerName,
    aktiveAnbieter: typeof detail?.marktSegment?.nAwards === "number" ? detail.marktSegment.nAwards : null,
    hatVerdraengung: lead.wechsel != null && lead.wechsel !== "na",
    zustand: zustandAus(lead),
    gewinner,
    exklusivSchicht: exklusivSchicht(lead, detail),
    indexierbar: false, // wird in ladeOeffentlich gesetzt (hängt an Schalter + Exklusivschicht)
    quelle: quelleAus(lead),
  };
}

/** Plattform-ID §13: aus der Unterlagen-URL ableiten (keine eigene eForms-Angabe). */
function plattformIdAus(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

/* ------------------------------------------------------------------ Lookup */

/*
 * idSlug -> branche, der Schluessel zum richtigen `leads-<branche>.json`.
 *
 * ⚠ Quelle ist `leads-fristen.json` — die schlanke Datei, die der Export ohnehin schreibt
 *   (9,2 MB / 42.105 Eintraege, je Eintrag u.a. `id` und `branche`; dieselbe, die leadIndex.ts
 *   nutzt). Darum zieht ein Serverless-Kaltstart NICHT alle sieben `leads-<branche>.json`
 *   (~110 MB), nur um die Branche eines Vorgangs zu finden. Kein eigener Index-Erzeuger noetig.
 *
 * ⚠ TOLERANT: fehlt die Datei oder traegt sie keine `branche` (aeltere Demo), faellt der
 *   Lookup auf den Voll-Scan der Branchendateien zurueck — dann teuer, aber korrekt.
 */
let brancheCache: Map<string, string> | null = null; // idSlug -> branche

async function brancheFuer(id: string): Promise<string | null> {
  if (!brancheCache) {
    const karte = new Map<string, string>();
    const roh = await loadDataFile("leads-fristen.json");
    if (roh) {
      try {
        const arr = JSON.parse(roh) as Array<{ id?: string; branche?: string }>;
        if (Array.isArray(arr)) {
          for (const l of arr) if (l?.id && l.branche) karte.set(idSlug(String(l.id)), l.branche);
        }
      } catch {
        /* defekt -> faellt unten auf den Scan, wenn die Karte leer bleibt */
      }
    }
    if (karte.size === 0) {
      // Fallback: Voll-Scan der Branchendateien (nur ohne brauchbare leads-fristen.json).
      for (const b of BRANCHEN) {
        const r = await loadDataFile(`leads-${b}.json`);
        if (!r) continue;
        try {
          const o = JSON.parse(r) as unknown;
          const arr = Array.isArray(o) ? o : Object.values(o as Record<string, unknown>);
          for (const l of arr as LeadRoh[]) if (l?.id) karte.set(idSlug(String(l.id)), b);
        } catch {
          /* defekte Datei überspringen, nicht den ganzen Lookup umwerfen */
        }
      }
    }
    brancheCache = karte;
  }
  return brancheCache.get(idSlug(id)) ?? null;
}

/**
 * Eine öffentliche Seite laden — oder null, wenn die Ausschreibung nicht existiert oder die
 * Seiten gar nicht freigeschaltet sind (`OEFFENTLICHE_SEITEN` aus).
 *
 * `indexierbar` wird hier gesetzt: nur bei aktivem Schalter UND seitenspezifischer
 * Exklusivschicht UND vorhandenem Titel (§11 Qualitätsschwelle). Die Route hängt daran, ob
 * sie `noindex` setzt.
 */
export async function ladeOeffentlich(slug: string): Promise<OeffentlicheSeite | null> {
  if (!OEFFENTLICHE_SEITEN_AN) return null;
  const id = idAusSlug(slug);
  if (!id) return null;
  const branche = await brancheFuer(id);
  if (!branche) return null;

  const rohLeads = await loadDataFile(`leads-${branche}.json`);
  if (!rohLeads) return null;
  let lead: LeadRoh | null = null;
  try {
    const o = JSON.parse(rohLeads) as unknown;
    const arr = Array.isArray(o) ? o : Object.values(o as Record<string, unknown>);
    lead = (arr as LeadRoh[]).find((l) => idSlug(String(l?.id ?? "")) === idSlug(id)) ?? null;
  } catch {
    return null;
  }
  if (!lead) return null;

  // Detail (buyerProfile/marktSegment) ist optional — fehlt es, bleibt die Seite ärmer, aber gültig.
  let detail: DetailRoh | null = null;
  const rohDetail = await loadDataFile(`detail-${branche}.json`);
  if (rohDetail) {
    try {
      const d = JSON.parse(rohDetail) as Record<string, DetailRoh>;
      detail = d[String(lead.id)] ?? null;
    } catch {
      /* Detail ist Beiwerk — ein Parsefehler darf die Seite nicht kippen */
    }
  }

  const seite = zuOeffentlich(lead, detail, branche);
  seite.indexierbar = OEFFENTLICHE_SEITEN_AN && seite.exklusivSchicht != null && seite.titel.length > 0;
  return seite;
}

/**
 * Slugs aller indexierbaren Seiten (§11) für die Sitemap — billig aus `leads-fristen.json`,
 * ohne die Branchendateien zu laden. Enumeriert nur, was auch die Seite selbst auf `index`
 * setzt: seitenspezifische Exklusivschicht (Vorgänger/Zyklus).
 *
 * ⚠ Hängt am Export-Feld `exklusivSchicht` in leads-fristen.json (der Peer baut es). TOLERANT:
 *   solange das Feld fehlt ODER der Schalter aus ist, kommt eine leere Liste zurück — lieber
 *   leer als falsch (eine Sitemap, die auf noindex-Seiten zeigt, schadet der Domain).
 *
 * ⚠ Der Slug wird hier mit derselben `vollSlug()` gebaut wie in der Route — EINE Normalisierung,
 *   damit Sitemap-URL und Seiten-URL nie auseinanderlaufen (kein Python-Slug im Export).
 */
export async function indexierbareSlugs(): Promise<string[]> {
  if (!OEFFENTLICHE_SEITEN_AN) return [];
  const roh = await loadDataFile("leads-fristen.json");
  if (!roh) return [];
  try {
    const arr = JSON.parse(roh) as Array<{ id?: string; titel?: string; exklusivSchicht?: string | null; x?: string | null }>;
    if (!Array.isArray(arr)) return [];
    const out: string[] = [];
    for (const l of arr) {
      const x = l.exklusivSchicht ?? l.x ?? null; // Feldname noch offen, beide lesen
      if (!l.id || !l.titel || !x) continue;      // nur §11-indexierbare
      out.push(vollSlug({ id: l.id, titel: l.titel }));
    }
    return out;
  } catch {
    return [];
  }
}

/** Nur für Tests/Export: den Modul-Cache leeren. */
export function _resetIndexCache(): void {
  brancheCache = null;
}
