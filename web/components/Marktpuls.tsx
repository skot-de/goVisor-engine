"use client";

import { useEffect, useMemo, useState } from "react";
import { useSprache } from "@/lib/i18n";
import "./marktpuls.css";
import { LAND_IN } from "@/lib/staaten";

/**
 * Marktpuls — Saisonalität + aktuelle Marktlage.
 * Briefing: `INPUT/v1 Features/add/govisor-briefing-marktpuls.md`.
 *
 * **In sich geschlossen** (AC1): die Komponente macht keine Annahme über ihre Umgebung —
 * keine Seitenbreite, kein Auth-Kontext, kein Router, kein globaler Zustand. Sie bringt ihr
 * eigenes CSS mit (Namespace `mp-*`) und skaliert über `container-type` an der Einbaubreite,
 * nicht am Viewport. Damit ist sie auf Landingpage, Blog und Strategie-Bereich gleich
 * einsetzbar; der Einbauort ist bewusst noch offen.
 *
 * **Zwei Einbauformen:**
 *   `<Marktpuls daten={json} />`  — bevorzugt. Server-Komponente lädt `marktpuls.json` und
 *                                   reicht es durch; das Element rendert vollständig ohne
 *                                   JavaScript-Nachladen (Briefing §5), der Umschalter
 *                                   arbeitet danach auf dem bereits geladenen JSON.
 *   `<Marktpuls />`               — Notnagel für rein clientseitige Einbauorte: holt einmalig
 *                                   `/api/marktpuls`. Danach ebenfalls kein Nachladen.
 *
 * **Was hier NICHT passiert** (Briefing §6): keine Live-Kurve der letzten Wochen, keine
 * Prognose, keine Einzelverfahren. Der Begleittext wird aus den berechneten Werten erzeugt —
 * das Skript liefert nur einen Befund-CODE plus Zahlen, formuliert wird erst hier.
 */

/* ── Datenvertrag (Spiegel von scripts/build_marktpuls.py) ────────────────── */
export type MarktpulsMonat = {
  m: number; avg: number; pct: number;
  /** Prüffeld zum Saisonindex — nur am Gesamtwert mitgeführt (Grössenbudget). */
  pct_naiv?: number;
  /** Nur gesetzt, wenn wahr: dieser Monat wich über die ganze Achse verlässlich in
   *  dieselbe Richtung ab. Fehlt das Feld, wechselt der Monat jährlich die Richtung —
   *  sein Ausschlag im Fenster ist dann Rauschen, egal wie gross er aussieht. */
  stabil?: boolean;
};
export type MarktpulsBefund = {
  typ: "spitze" | "tief" | "flach" | "keine_daten";
  monat?: number; pct?: number; avg?: number; monat_tief?: number; pct_tief?: number;
  /** Beleg des benannten Monats: „in {jahre_gleich} von {jahre} Jahren". */
  jahre?: number; jahre_gleich?: number; mittel?: number; spanne?: [number, number];
};
export type MarktpulsSaison = {
  monate: MarktpulsMonat[]; jahresmittel: number; verfahren_gesamt: number;
  /** Das Fenster steht einmal unter `fenster` — es ist für alle Blöcke dasselbe. */
  befund: MarktpulsBefund; genug: boolean;
};
export type MarktpulsCoverage = {
  verfahren_gesamt: number; verfahren_im_fenster: number;
  quellen_zeitreihe: string[];
  quellen_ausgeschlossen: { quelle: string; verfahren: number; von: number; bis: number }[];
  letzte_veroeffentlichung: string | null; belastbar: boolean;
  /** ab wann dieses Land überhaupt im Bestand ist (schema 2). CH: 2016 — Bestandsbeginn,
   *  nicht Marktbeginn. */
  bestand_von?: number | null;
  /** Anteil der Verfahren, deren Zeitpunkt nur auf year/month steht statt auf einem echten
   *  `publication_date` (DE ~26 %, praktisch die ganze DÖE-Menge). Herkunfts-Kennzeichnung. */
  datum_nur_monat_pct?: number;
  /** nur am Aggregat: Länder, die mitgezählt, aber für eine eigene Kurve zu dünn sind. */
  nicht_belastbar?: string[];
};
/* ── Jahres-Layer (schema 2) ──────────────────────────────────────────────────
 * Eine Zeile je QUELLE, nicht je Linie: `serie` sagt, zu welcher Linie die Quelle gehört.
 * Zusammengeführte Quellen teilen sich eine `serie` und werden hier addiert — die
 * Zusammensetzung bleibt trotzdem in den Daten, statt in einer Summe zu verschwinden. */
export type MarktpulsJahresReihe = {
  quelle: string; serie: string; grund: "basis" | "durchgehend" | "beginnt_spaeter";
  von: number; werte: number[];
  /** Jahre mit weniger als 12 belegten Monaten — CH-TED 2016 hat fünf. Ein Teiljahr als
   *  Jahreswert gezeichnet liest sich als Einbruch bzw. als Wachstum im Folgejahr. */
  teiljahre?: { jahr: number; monate: number }[];
};
export type MarktpulsBruch = {
  jahr: number;
  /** `gemessen` = aus dem Bestand abgeleitet, `kuratiert` = äusseres Wissen mit `beleg`. */
  art: "gemessen" | "kuratiert";
  typ: "schema_wechsel" | "quelle_start" | "land_start" | "regel";
  von?: string; nach?: string; quelle?: string; land?: string; code?: string; beleg?: string;
};
/* ── Single-Bid (schema 3) ────────────────────────────────────────────────────
 * Anteil der Zuschläge mit genau einem Bieter. Drei Eigenschaften, die die Anzeige
 * mittragen MUSS, sonst wird die Zahl falsch gelesen:
 *   1. rückblickend — von den offenen Ausschreibungen trägt keine eine Bieterzahl,
 *   2. teilblind — DÖE meldet sie nie, der DE-Unterschwellenbereich fehlt komplett,
 *   3. quellenabhängig — eine Mischkurve springt beim Quellen-Onset (atverg 2019). */
export type MarktpulsBieterReihe = {
  quelle: string; von: number;
  /** Basis: Zuschläge mit Bieterzahl, ohne die Verfahrensarten, bei denen ein Bieter die
   *  Bauart ist (Direktvergabe u. a.). `sb` = davon mit genau einem Bieter.
   *  Gespeichert sind die ZÄHLER, nicht der Anteil — ein Prozentwert ohne seine Grundmenge
   *  ist nicht einzuordnen, und zwei getrennt gespeicherte Grössen laufen auseinander. */
  n: number[]; sb: number[];
  /** Nur auf Branchen-Gesamtebene: dieselben Zähler ohne den Verfahrensart-Filter. */
  n_alle?: number[]; sb_alle?: number[];
};
export type MarktpulsBieter = {
  achse: number[]; von: number; bis: number;
  reihen: Record<string, MarktpulsBieterReihe[]>;
  abdeckung: Record<string, { jahr: number; pct: number; cans: number }[]>;
  ohne_wettbewerb: string[];
  offene_mit_bieterzahl: number;
};
export type MarktpulsJahre = {
  achse: number[]; von: number; bis: number; laufendes_jahr: number;
  reihen: Record<string, MarktpulsJahresReihe[]>;
  brueche: Record<string, MarktpulsBruch[]>;
  vorlauf: Record<string, { quelle: string; verfahren: number }[]>;
};
export type MarktpulsLageLand = {
  laufend: number; ohne_frist: number; frist_basis: string; frist_abdeckung: number;
  zuschlag_30d: number; aufhebung_30d: number;
};
export type MarktpulsDaten = {
  schema: number; erzeugt: string; stand: string; laender: string[];
  gesamt_key: string; branchen: string[];
  fenster: { von: number; bis: number; jahre: number };
  min_faelle: number;
  coverage: Record<string, MarktpulsCoverage>;
  saison: Record<string, MarktpulsSaison>;
  /** optional: eine Datei nach Stand 1 führt den Jahres-Layer nicht. Die Anzeige blendet
   *  den Umschalter dann aus, statt am ersten Deploy zu brechen, bei dem Skript und
   *  Frontend nicht Schritt halten. */
  jahre?: MarktpulsJahre;
  /** optional wie `jahre` — eine Datei nach Stand 1/2 führt den Layer nicht. */
  bieter?: MarktpulsBieter;
  lage: {
    stand: string; fenster_tage: number;
    je_land: Record<string, MarktpulsLageLand>;
    je_branche: Record<string, { key: string; n: number }[]>;
  };
};

/* ── Anzeige-Vokabular ────────────────────────────────────────────────────────
 * Deutsche Sätze/Wörter als Übersetzungsschlüssel (Projekt-Konvention, s. lib/i18n).
 * Auf Modul-Ebene stehen nur die SCHLÜSSEL — durch `t()` gehen sie erst beim Rendern,
 * sonst friert die Sprache beim Import ein (der Fehler hat hier schon zugeschlagen). */
/* `EU` ist im Bestand kein Land, sondern der Sammel-Topf für alles ausserhalb der drei
 * geführten Länder — er heisst deshalb auch so, statt als „EU" ein Gebiet vorzutäuschen. */
const LAND_LABEL: Record<string, string> = {
  DE: "Deutschland", AT: "Österreich", CH: "Schweiz", LU: "Luxemburg", EU: "Übrige EU-Länder",
};
/* Eigene Form für „in …": „in der Schweiz", nicht „in Schweiz". Die Präposition steckt im
 * Satz, der Artikel am Land. Die Begründung ist geblieben, die Liste ist nach `lib/staaten`
 * gewandert — sie wurde von zwei Dateien gebraucht. */
// Sie steht bei den übrigen Importen oben.
const BRANCHE_LABEL: Record<string, string> = {
  bau: "Bau & Infrastruktur", it: "IT & Software", beratung: "Beratung & Dienstleistung",
  medizin: "Medizin & Gesundheit", sicherheit: "Sicherheit", energie: "Energie & Versorgung",
};
const QUELLE_LABEL: Record<string, string> = {
  ted: "TED (EU-weite Bekanntmachungen)", doe: "oeffentlichevergabe.de",
  simap: "simap.ch", atverg: "Ausschreibungen Österreich",
};
const MONAT_KURZ = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const MONAT_LANG = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
  "September", "Oktober", "November", "Dezember"];

/* Die Fliesstexte des Elements — ein Katalog wie in `lib/labels.js`, aus demselben Grund:
 * ein Satz gehört an EINE Stelle, sonst driften die zwei Fassungen desselben Satzes
 * auseinander (Zeitreihen-Hinweis und Basiszeile teilen sich Bausteine).
 *
 * ⚠ Diese Sätze sind zugleich die Übersetzungsschlüssel und stehen NOCH NICHT in
 * `lib/i18n/messages/flat.{en,fr}.json` — sie müssen dort ergänzt werden, sonst bleibt das
 * Element in EN/FR deutsch (der deutsche Fallback ist gewollt, aber er ist nicht fertig).
 * Bis dahin ist das der bewusste, benannte Rest, kein Versehen. */
const TXT = {
  titel: "Marktpuls",
  frage: "Wann wird ausgeschrieben, und was läuft gerade?",
  stand: "Stand: {datum}",
  ladefehler: "Marktpuls derzeit nicht verfügbar.",
  laedt: "Marktpuls wird geladen …",
  veraltet: "Der nächtliche Lauf ist seit {n} Tagen nicht durchgelaufen. Angezeigt wird der letzte erfolgreiche Stand vom {datum}, nicht der heutige.",
  land: "Land",
  branche: "Branche",
  alleLaender: "Alle Länder",
  alleBranchen: "Alle Branchen",
  landZuDuenn: "Zu wenige Verfahren im Fenster ({n}), für dieses Land gibt es noch keine belastbare Kurve.",
  brancheZuWenig: "Zu wenige Verfahren ({n}, Mindestzahl {min}).",
  kombiZuWenig: "Zu wenige Verfahren für diese Kombination, die Kurve wäre nicht belastbar (Mindestzahl {min}).",
  diagramm: "Ø Ausschreibungen je Kalendermonat, {von} bis {bis}",
  jahresmittelLinie: "Jahresmittel {n}",
  befundSpitze: "Der stärkste Monat ist {monat} mit Ø {n} Ausschreibungen, {pct} % über dem Jahresmittel.",
  befundTief: "Der schwächste Monat ist {monat} mit Ø {n} Ausschreibungen, {pct} % unter dem Jahresmittel.",
  /* Der Beleg, der den Satz erst belastbar macht — und zugleich das Kriterium, nach dem der
   * Monat überhaupt genannt werden durfte. Ohne ihn stünde da eine Fensterzahl, die an einer
   * Nachkommastelle kippen kann; mit ihm eine Aussage über zwei Jahrzehnte. */
  befundBeleg: "Und das nicht nur zufällig in diesem Zeitraum: in {gleich} von {jahre} Jahren lag der {monat} auf derselben Seite des Jahresmittels ({von} bis {bis} %).",
  befundFlach: "Die Ausschreibungen verteilen sich über das Jahr gleichmäßiger als oft angenommen: kein Monat weicht verlässlich vom Jahresmittel ab. Der stärkste Ausschlag im gezeigten Zeitraum ist {hoch} ({pctHoch} %), er wiederholt sich über die Jahre aber nicht.",
  monatUnsicher: "wechselt jährlich die Richtung. Im Zeitraum auffällig, über die Jahre nicht belastbar",
  befundLeer: "Für diese Auswahl liegen keine Werte vor.",
  basis: "Grundlage: {n} Verfahren aus {jahre} vollen Jahren ({von} bis {bis}). Gezählt wird das Verfahren, nicht die Bekanntmachung. Korrektur- und Folgebekanntmachungen desselben Verfahrens zählen einmal.",
  tabelle: "Werte als Tabelle",
  spalteMonat: "Monat",
  spalteAvg: "Ø Ausschreibungen",
  spalteAbw: "Abweichung vom Jahresmittel",
  jahresmittel: "Jahresmittel",
  lage: "Aktuelle Lage",
  lageGesamt: "Aktuell laufen {n} Ausschreibungen, auf die geboten werden kann, über alle erfassten Länder.",
  lageLand: "Aktuell laufen in {raum} {n} Ausschreibungen, auf die geboten werden kann.",
  kpiLaufend: "laufende Ausschreibungen",
  kpiZuschlag: "Zuschläge (letzte {n} Tage)",
  kpiAufhebung: "Aufhebungen (letzte {n} Tage)",
  kpiOhneFrist: "frisch, aber ohne veröffentlichte Frist",
  fristBasis: "„Laufend“ steht auf der Angebotsfrist aus der Bekanntmachung ({pct} % der frisch veröffentlichten Verfahren tragen eine). Verfahren ohne veröffentlichte Frist sind nicht mitgezählt. Die Zahl ist eine Untergrenze, keine Vollzählung.",
  quellen: "Zeitreihe aus: {quellen}.",
  quelleRaus: "{quelle} ist erst ab {jahr} im Bestand und bleibt aus der Zeitreihe heraus. Ein Quellen-Start ist ein Ingest-Sprung, kein Marktsignal.",
  duenneLaender: "Mitgezählt, aber für eine eigene Kurve zu dünn: {laender}.",
  landNichtBelastbar: "Für dieses Land reicht die Datenlage im Fenster nicht für eine belastbare Kurve.",

  /* ── Jahres-Layer ── */
  zeitraum: "Ansicht",
  ansichtSaison: "Monate im Jahr",
  ansichtJahre: "Jahre",
  jahreDiagramm: "Ausschreibungen je Jahr, {von} bis {bis}, eine Linie je Quelle",
  jahreLeer: "Für diese Auswahl liegen keine Jahreswerte vor.",
  jahreBasis: "Grundlage: {n} Verfahren über {jahre} Jahre ({von} bis {bis}). Das laufende Jahr {laufend} fehlt, es ist noch kein volles Jahr und läse sich als Einbruch.",
  serieAb: "ab {jahr}",
  serieZusammengefuehrt: "{quellen}. Zusammengeführt, weil beide über die ganze Achse durchgehend liefern.",
  serieEigen: "{quelle} liefert erst ab {jahr} und bekommt deshalb eine eigene Linie. Nicht addiert: ein Quellen-Start wäre in einer Summe von echtem Wachstum nicht zu unterscheiden.",
  serieBestandSpaeter: "Vor {jahr} liegt für diese Auswahl nichts vor. Das ist der Beginn unserer Erfassung, nicht der des Marktes. Die Achse bleibt trotzdem stehen, damit die Lücke sichtbar ist statt weggeschnitten.",
  teiljahrHinweis: "{jahr} ist bei {quelle} nur mit {n} von 12 Monaten belegt, der Punkt ist deshalb offen gezeichnet und trägt keinen Jahresvergleich.",
  vorlaufHinweis: "{quelle} liegt vor {jahr} mit {n} Verfahren im Bestand. Zu wenige für einen Betrieb, deshalb ohne Linie ausgewiesen statt weggelassen.",
  brueche: "Markierte Bruchstellen",
  bruecheHinweis: "Ein Knick über viele Jahre ist häufiger eine Regel- oder Formatänderung als ein Marktereignis. Markiert ist beides. Was aus unseren Daten abgeleitet ist und was äußeres Wissen ist, steht dabei.",
  bruchGemessen: "gemessen",
  bruchKuratiert: "belegt",
  bruchSchema: "Das Meldeformat wechselt von {von} auf {nach}. Was und wie gemeldet wird, ändert sich damit, ein Sprung an dieser Stelle ist zuerst ein Formatwechsel.",
  bruchQuelle: "{quelle} kommt neu in den Bestand. Die Linie beginnt hier, der Markt nicht.",
  bruchLand: "{land} kommt neu in den Bestand. In der Gesamtlinie sähe das ohne Marke wie Wachstum aus.",
  bruchRegel: "Regeländerung: {beleg}",
  spalteJahr: "Jahr",
  spalteSumme: "Zusammen",

  /* ── Single-Bid ── */
  ansichtBieter: "Wettbewerb",
  bieterTitel: "Zuschläge mit nur einem Bieter",
  bieterZahl: "Zuletzt ({jahr}) hatten {sb} von {n} ausgewerteten Zuschlägen nur ein einziges Angebot, {pct} %. Über den ganzen gezeigten Zeitraum sind es {sbGes} von {nGes}.",
  bieterDiagramm: "Anteil der Zuschläge mit genau einem Bieter, {von} bis {bis}, eine Linie je Quelle",
  bieterLeer: "Für diese Auswahl liegen keine Bieterzahlen vor.",
  bieterBasis: "Gezählt werden Zuschläge, bei denen die Zahl der eingegangenen Angebote veröffentlicht wurde. Verfahren, die per Bauart nur einen Bieter haben, sind ausgenommen. Direktvergaben und Verhandlungsverfahren ohne vorherigen Aufruf.",
  bieterRueckblick: "Diese Zahl entsteht erst mit dem Zuschlag: von den aktuell offenen Ausschreibungen tragen nur {n} eine Bieterzahl. Sie beschreibt also, wo der Wettbewerb dünn war. Nicht, wo er es gerade ist.",
  /* Null ist kein Sonderfall der Zahl, sondern ein anderer Satz: „trägt 0 eine
   * Bieterzahl“ ist in keiner Sprache richtig, und in EN/FR bräche die Pluralform.
   * (Das Schlusszeichen muss typografisch sein — ein gerades Anführungszeichen im
   *  Kommentar bringt den Katalog-Guard aus dem Tritt, er parst Strings mit.) */
  bieterRueckblickNull: "Diese Zahl entsteht erst mit dem Zuschlag: keine einzige der aktuell offenen Ausschreibungen trägt eine Bieterzahl. Sie beschreibt also, wo der Wettbewerb dünn war. Nicht, wo er es gerade ist.",
  bieterAbdeckung: "Im Jahr {jahr} trugen {pct} % der {cans} Zuschläge überhaupt eine Bieterzahl. Der Rest ist für diese Kennzahl unsichtbar, {quelle} veröffentlicht sie nicht.",
  bieterAbdeckungTitel: "Wie viel des Marktes diese Kennzahl sieht",
  spalteQuote: "ein Bieter",
  spalteFaelle: "Zuschläge mit Bieterzahl",
  quellenJahre: "Jahresansicht: {quellen}. Je Quelle eine eigene Reihe, hier fällt keine heraus. Ausgeschlossen wird nur in der Monatsansicht, wo ein späterer Quellen-Start den Durchschnitt verschöbe.",
  achseNurFenster: "Die Jahresachse deckt dasselbe Fenster ab wie die Saison ({von} bis {bis}). Die Historie bis {frueh} wird gesondert erzeugt (Schalter --ab-jahr), weil sie im täglichen Lauf zu lange braucht.",
} as const;

const ALLE = "alle";
/* Ab dieser Abweichung ist ein Monat hervorgehoben bzw. gedämpft — dieselbe Schwelle, die
 * `build_marktpuls.befund()` für den Ein-Satz-Befund benutzt (Briefing §7). */
const AUSREISSER = 25;
/* Ab so vielen Tagen ohne neuen Lauf gilt der Stand als veraltet und wird als solcher
 * gekennzeichnet (Briefing §4.3/AC8) — Aktualisierung ist täglich, zwei Tage Luft. */
const VERALTET_TAGE = 2;

const zahl = (n: number, nk = 0) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: nk, maximumFractionDigits: nk });
/** Vorzeichen gehört an den WERT, nicht in den Satz — sonst müsste jede Übersetzung das
 *  „+" mitschleppen und ein negativer Wert stünde als „+-3 %" da. */
const mitVorzeichen = (n: number, nk = 0) => (n > 0 ? "+" : "") + zahl(n, nk);
const datum = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("de-DE");
};
const tageSeit = (iso: string) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 0;
  return Math.floor((Date.now() - d.getTime()) / 86_400_000);
};

/* ── Jahres-Layer ─────────────────────────────────────────────────────────────
 * Bewusst handgezeichnetes SVG statt einer Diagramm-Bibliothek: das Element soll in sich
 * geschlossen bleiben (AC1) und ohne Nachladen rendern (Briefing §5) — eine Chart-Library
 * wäre ein Vielfaches seiner eigenen Grösse.
 *
 * Die Linien folgen der Regel aus dem Skript: `serie` ist die Linie, `quelle` die Herkunft.
 * Quellen, die sich eine Serie teilen, werden hier addiert — die einzelnen Quellen bleiben
 * in der Tabelle darunter sichtbar. Was NICHT passiert: Serien addieren. Eine Summe aus
 * TED und DÖE wäre nicht von echtem Wachstum zu unterscheiden. */
const SERIE_FARBE = ["var(--mp-s1)", "var(--mp-s2)", "var(--mp-s3)", "var(--mp-s4)"];
const VB_W = 720, VB_H = 232, PAD_L = 52, PAD_R = 12, PAD_T = 16, PAD_B = 32;

type Linie = {
  serie: string;
  quellen: MarktpulsJahresReihe[];
  /** auf die Achse ausgerichtet; `null` = Serie existiert in diesem Jahr noch nicht. */
  werte: (number | null)[];
  von: number;
  farbe: string;
};

function linienBauen(reihen: MarktpulsJahresReihe[], achse: number[]): Linie[] {
  const nach = new Map<string, MarktpulsJahresReihe[]>();
  for (const r of reihen) nach.set(r.serie, [...(nach.get(r.serie) ?? []), r]);
  /* Reihenfolge: die Serie mit dem frühesten Beginn zuerst — so bekommt die tragende
   * Quelle (TED) stabil dieselbe Farbe, egal welche nationale Quelle dazukommt. */
  const serien = [...nach.entries()].sort(
    (a, b) => Math.min(...a[1].map((r) => r.von)) - Math.min(...b[1].map((r) => r.von)));
  return serien.map(([serie, quellen], i) => {
    const werte = achse.map((jahr) => {
      let summe: number | null = null;
      for (const q of quellen) {
        const idx = jahr - q.von;
        if (idx >= 0 && idx < q.werte.length) summe = (summe ?? 0) + q.werte[idx];
      }
      return summe;
    });
    return { serie, quellen, werte, von: Math.min(...quellen.map((r) => r.von)),
             farbe: SERIE_FARBE[i % SERIE_FARBE.length] };
  });
}

/** Teiljahre je Serie×Jahr — die Punkte, die offen gezeichnet werden. */
function teiljahrKarte(linien: Linie[]): Map<string, { quelle: string; monate: number }[]> {
  const m = new Map<string, { quelle: string; monate: number }[]>();
  for (const l of linien) {
    for (const q of l.quellen) {
      for (const t of q.teiljahre ?? []) {
        const k = `${l.serie}|${t.jahr}`;
        m.set(k, [...(m.get(k) ?? []), { quelle: q.quelle, monate: t.monate }]);
      }
    }
  }
  return m;
}

function JahresDiagramm({ d, land, branche }: {
  d: MarktpulsDaten; land: string; branche: string;
}) {
  const { t } = useSprache();
  const j = d.jahre!;
  const achse = j.achse;
  const reihen = j.reihen[`${land}|${branche}`] ?? [];
  const linien = useMemo(() => linienBauen(reihen, achse), [reihen, achse]);
  const teil = useMemo(() => teiljahrKarte(linien), [linien]);
  const brueche = (j.brueche[land] ?? []).filter((b) => achse.includes(b.jahr));
  /* Ein Jahr trägt oft mehrere Brüche (2024: Quellen-Start, Formatwechsel UND eForms-
   * Pflicht — sie hängen ja zusammen). Eine Marke je EINTRAG legte drei Kreise exakt
   * übereinander; sichtbar blieb einer, die anderen waren stumm verdeckt. Deshalb eine
   * Marke je JAHR, und die Liste darunter führt auf, was in diesem Jahr zusammenkam. */
  const bruchJahre = useMemo(() => {
    const nach = new Map<number, MarktpulsBruch[]>();
    for (const b of brueche) nach.set(b.jahr, [...(nach.get(b.jahr) ?? []), b]);
    return [...nach.entries()].sort((a, b) => a[0] - b[0]);
  }, [brueche]);
  const vorlauf = j.vorlauf?.[land] ?? [];

  const gesamt = linien.reduce(
    (s, l) => s + l.werte.reduce((a: number, v) => a + (v ?? 0), 0), 0);
  if (!linien.length || gesamt < d.min_faelle) {
    return <p className="mp-note">{t(TXT.jahreLeer)}</p>;
  }

  const n = achse.length;
  // Nullbasis, wie beim Balkendiagramm: eine gekappte Achse macht aus 5 % eine Verdopplung.
  const max = Math.max(1, ...linien.flatMap((l) => l.werte.map((v) => v ?? 0)));
  const x = (i: number) => PAD_L + (i * (VB_W - PAD_L - PAD_R)) / Math.max(1, n - 1);
  const y = (v: number) => PAD_T + (1 - v / max) * (VB_H - PAD_T - PAD_B);
  // Bei 22 Jahren stehen 22 Beschriftungen übereinander — nur jede k-te bekommt eine.
  const schritt = Math.ceil(n / 12);
  const quelleName = (q: string) => t(QUELLE_LABEL[q] ?? q);

  function bruchText(b: MarktpulsBruch): string {
    if (b.typ === "schema_wechsel") return t(TXT.bruchSchema, { von: b.von ?? "", nach: b.nach ?? "" });
    if (b.typ === "quelle_start") return t(TXT.bruchQuelle, { quelle: quelleName(b.quelle ?? "") });
    if (b.typ === "land_start") return t(TXT.bruchLand, { land: t(LAND_LABEL[b.land ?? ""] ?? b.land ?? "") });
    // Der Beleg kommt als deutscher Satz aus dem JSON und ist damit selbst ein
    // Übersetzungsschlüssel (Projekt-Konvention). Kein Guard sieht das — `t(variable)`
    // ist die bekannte Grenze der i18n-Prüfungen —, die Einträge stehen deshalb von Hand
    // in `flat.{en,fr}.json`. Wer `REGEL_BRUECHE` erweitert, ergänzt sie dort mit.
    return t(TXT.bruchRegel, { beleg: t(b.beleg ?? "") });
  }

  return (
    <div className="mp-chart mp-jahre">
      <svg className="mp-svg" viewBox={`0 0 ${VB_W} ${VB_H}`} role="img"
           aria-label={t(TXT.jahreDiagramm, { von: j.von, bis: j.bis })}>
        {/* Waagerechtes Raster + Werteachse */}
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line className="mp-grid" x1={PAD_L} x2={VB_W - PAD_R} y1={y(max * f)} y2={y(max * f)} />
            <text className="mp-tick" x={PAD_L - 8} y={y(max * f) + 4} textAnchor="end">
              {zahl(Math.round(max * f))}
            </text>
          </g>
        ))}

        {/* Bruchstellen liegen HINTER den Linien — sie sind Kontext, nicht Inhalt. */}
        {bruchJahre.map(([jahr, eintraege], i) => {
          const bx = x(achse.indexOf(jahr));
          // Gestrichelt = gemessen, gepunktet = kuratiert. Kommt beides in einem Jahr
          // zusammen, gewinnt „gemessen": die Linie steht dann auf einem Befund aus den
          // Daten, nicht nur auf einer Fussnote.
          const art = eintraege.some((b) => b.art === "gemessen") ? "gemessen" : "kuratiert";
          return (
            <g key={jahr}>
              <line className="mp-bruch" data-art={art} x1={bx} x2={bx} y1={PAD_T} y2={VB_H - PAD_B} />
              <circle className="mp-bruch-nr" cx={bx} cy={PAD_T - 2} r={7.5} />
              <text className="mp-bruch-txt" x={bx} y={PAD_T + 1.5} textAnchor="middle">{i + 1}</text>
            </g>
          );
        })}

        {linien.map((l) => {
          const punkte = l.werte
            .map((v, i) => (v === null ? null : `${x(i)},${y(v)}`))
            .filter(Boolean) as string[];
          return (
            <g key={l.serie}>
              <polyline className="mp-linie" points={punkte.join(" ")} style={{ stroke: l.farbe }} />
              {l.werte.map((v, i) => v === null ? null : (
                <circle key={i} cx={x(i)} cy={y(v)} r={3}
                        className="mp-punkt"
                        data-teil={teil.has(`${l.serie}|${achse[i]}`) ? "ja" : "nein"}
                        style={{ stroke: l.farbe }}>
                  <title>{`${achse[i]}: ${zahl(v)}`}</title>
                </circle>
              ))}
            </g>
          );
        })}

        {achse.map((jahr, i) => (i % schritt === 0 || i === n - 1) ? (
          <text key={jahr} className="mp-tick" x={x(i)} y={VB_H - PAD_B + 16} textAnchor="middle">
            {jahr}
          </text>
        ) : null)}
      </svg>

      {/* Legende: eine Zeile je Serie, mit dem Grund ihrer Existenz. */}
      <ul className="mp-legende">
        {linien.map((l) => {
          const mehrere = l.quellen.length > 1;
          const eigen = l.quellen.find((q) => q.grund === "beginnt_spaeter");
          return (
            <li key={l.serie}>
              <i style={{ background: l.farbe }} aria-hidden="true" />
              <span className="mp-legende-name">
                {l.quellen.map((q) => quelleName(q.quelle)).join(" + ")}
                {" "}<em>{t(TXT.serieAb, { jahr: l.von })}</em>
              </span>
              <span className="mp-legende-grund">
                {mehrere
                  ? t(TXT.serieZusammengefuehrt,
                      { quellen: l.quellen.map((q) => quelleName(q.quelle)).join(" + ") })
                  : eigen
                    ? t(TXT.serieEigen, { quelle: quelleName(eigen.quelle), jahr: eigen.von })
                    /* Die Basis-Serie beginnt nach dem Achsenanfang: das ist der Beginn
                       unserer Erfassung (gemessen CH: 2016), nicht der des Marktes. Ohne
                       diesen Satz liest sich der leere linke Teil der Achse als „hier gab
                       es keine Ausschreibungen". */
                    : l.von > achse[0]
                      ? t(TXT.serieBestandSpaeter, { jahr: l.von })
                      : null}
              </span>
            </li>
          );
        })}
      </ul>

      <p className="mp-basis">
        {t(TXT.jahreBasis, {
          n: zahl(gesamt), jahre: n, von: j.von, bis: j.bis, laufend: j.laufendes_jahr,
        })}
        {[...teil.entries()].map(([k, qs]) => {
          const jahr = Number(k.split("|")[1]);
          return qs.map((q) => (
            <span key={`${k}-${q.quelle}`}>
              {" "}{t(TXT.teiljahrHinweis,
                     { jahr, quelle: quelleName(q.quelle), n: q.monate })}
            </span>
          ));
        })}
        {vorlauf.map((v) => (
          <span key={v.quelle}>
            {" "}{t(TXT.vorlaufHinweis, {
              quelle: quelleName(v.quelle), n: zahl(v.verfahren),
              jahr: linien.find((l) => l.quellen.some((q) => q.quelle === v.quelle))?.von ?? j.von,
            })}
          </span>
        ))}
      </p>

      {/* Bruchstellen als Text — die Marken im Diagramm allein sagen nichts. */}
      {bruchJahre.length ? (
        <div className="mp-brueche">
          <h5>{t(TXT.brueche)}</h5>
          <p className="mp-basis">{t(TXT.bruecheHinweis)}</p>
          {/* Nummerierung folgt der Reihenfolge der Marken im Diagramm — `ol` zählt selbst. */}
          <ol>
            {bruchJahre.map(([jahr, eintraege]) => (
              <li key={jahr}>
                <b>{jahr}</b>
                <ul>
                  {eintraege.map((b, k) => (
                    <li key={`${b.typ}-${b.quelle ?? b.land ?? b.code ?? k}`}>
                      <span className="mp-bruch-art" data-art={b.art}>
                        {b.art === "gemessen" ? t(TXT.bruchGemessen) : t(TXT.bruchKuratiert)}
                      </span>
                      <span>{bruchText(b)}</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {/* Barrierefreiheit: dieselben Werte als Tabelle — hier je QUELLE, nicht je Serie,
          damit die Zusammensetzung eines Jahres ablesbar bleibt (Entscheidung 5). */}
      <details className="mp-table">
        <summary>{t(TXT.tabelle)}</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">{t(TXT.spalteJahr)}</th>
              {reihen.map((r) => <th key={r.quelle} scope="col">{quelleName(r.quelle)}</th>)}
              <th scope="col">{t(TXT.spalteSumme)}</th>
            </tr>
          </thead>
          <tbody>
            {achse.map((jahr) => {
              const zellen = reihen.map((r) => {
                const idx = jahr - r.von;
                return idx >= 0 && idx < r.werte.length ? r.werte[idx] : null;
              });
              return (
                <tr key={jahr}>
                  <th scope="row">{jahr}</th>
                  {zellen.map((v, i) => (
                    <td key={reihen[i].quelle}>{v === null ? "—" : zahl(v)}</td>
                  ))}
                  <td>{zahl(zellen.reduce((a: number, v) => a + (v ?? 0), 0))}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </details>
    </div>
  );
}

/* ── Single-Bid-Ansicht ───────────────────────────────────────────────────────
 * Dieselbe SVG-Mechanik wie der Jahres-Layer, aber die Y-Achse ist ein Anteil. Auch hier
 * eine Linie je Quelle und keine Summe: gemessen springt eine Mischkurve 2018→2019 von
 * 20 % auf 27 %, und das ist der atverg-Start, kein Marktereignis. */
function BieterDiagramm({ d, land, branche }: {
  d: MarktpulsDaten; land: string; branche: string;
}) {
  const { t } = useSprache();
  const b = d.bieter!;
  const achse = b.achse;
  /* Nach Beginn sortiert, nicht alphabetisch: so trägt die tragende Quelle (TED) stabil
     dieselbe Farbe wie im Jahres-Layer, statt sie an eine neue nationale Quelle zu
     verlieren, nur weil deren Name vorne im Alphabet steht. */
  const reihen = [...(b.reihen[`${land}|${branche}`] ?? [])].sort((x, y) => x.von - y.von);
  const abd = b.abdeckung[land] ?? [];
  const quelleName = (q: string) => t(QUELLE_LABEL[q] ?? q);

  if (!reihen.length) return <p className="mp-note">{t(TXT.bieterLeer)}</p>;

  // Nur den Bereich zeichnen, in dem tatsächlich Werte liegen — sonst nimmt eine Achse ab
  // 2004 zwei Drittel der Breite für Jahre ein, in denen niemand Bieterzahlen meldete.
  const ersteJ = Math.min(...reihen.map((r) => r.von));
  const sicht = achse.filter((j) => j >= ersteJ);
  const n = sicht.length;
  /* Ein Anteil je Reihe und Jahr, aus den Zählern gerechnet — Jahre ohne Basis bleiben
     `null` und werden nicht gezeichnet, statt als 0 % eine Aussage vorzutäuschen. */
  const quoten = (r: MarktpulsBieterReihe) =>
    r.n.map((n, i) => (n > 0 ? (100 * r.sb[i]) / n : null));
  const werte = reihen.flatMap((r) => quoten(r).filter((v): v is number => v !== null));
  // Nullbasis auch hier: bei einem Anteil ist sie zwingend, sonst wirkt jeder Unterschied
  // wie eine Vervielfachung.
  const max = Math.max(20, Math.ceil(Math.max(...werte, 1) / 10) * 10);
  const x = (i: number) => PAD_L + (i * (VB_W - PAD_L - PAD_R)) / Math.max(1, n - 1);
  const y = (v: number) => PAD_T + (1 - v / max) * (VB_H - PAD_T - PAD_B);
  const schritt = Math.ceil(n / 12);

  return (
    <div className="mp-chart mp-jahre">
      <h4 className="mp-bieter-titel">{t(TXT.bieterTitel)}</h4>
      <svg className="mp-svg" viewBox={`0 0 ${VB_W} ${VB_H}`} role="img"
           aria-label={t(TXT.bieterDiagramm, { von: sicht[0], bis: sicht[n - 1] })}>
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line className="mp-grid" x1={PAD_L} x2={VB_W - PAD_R} y1={y(max * f)} y2={y(max * f)} />
            <text className="mp-tick" x={PAD_L - 8} y={y(max * f) + 4} textAnchor="end">
              {zahl(Math.round(max * f))} %
            </text>
          </g>
        ))}
        {reihen.map((r, ri) => {
          const farbe = SERIE_FARBE[ri % SERIE_FARBE.length];
          const q = quoten(r);
          const pkt = q
            .map((v, i) => (v === null ? null : `${x(sicht.indexOf(r.von + i))},${y(v)}`))
            .filter(Boolean) as string[];
          return (
            <g key={r.quelle}>
              <polyline className="mp-linie" points={pkt.join(" ")} style={{ stroke: farbe }} />
              {q.map((v, i) => v === null ? null : (
                <circle key={i} cx={x(sicht.indexOf(r.von + i))} cy={y(v)} r={3}
                        className="mp-punkt" data-teil="nein" style={{ stroke: farbe }}>
                  {/* Der Anteil allein sagt nichts über die Grössenordnung — die beiden
                      Zahlen dahinter gehören an denselben Punkt. */}
                  <title>{`${r.von + i}: ${zahl(v, 1)} % — ${zahl(r.sb[i])} von ${zahl(r.n[i])}`}</title>
                </circle>
              ))}
            </g>
          );
        })}
        {sicht.map((jahr, i) => (i % schritt === 0 || i === n - 1) ? (
          <text key={jahr} className="mp-tick" x={x(i)} y={VB_H - PAD_B + 16} textAnchor="middle">
            {jahr}
          </text>
        ) : null)}
      </svg>

      <ul className="mp-legende">
        {reihen.map((r, ri) => (
          <li key={r.quelle}>
            <i style={{ background: SERIE_FARBE[ri % SERIE_FARBE.length] }} aria-hidden="true" />
            <span className="mp-legende-name">
              {quelleName(r.quelle)} <em>{t(TXT.serieAb, { jahr: r.von })}</em>
            </span>
          </li>
        ))}
      </ul>

      {/* Die Frage, die ein Anteil immer offen lässt: wie viele Vergaben sind das?
          Zuletzt-Jahr für die Grössenordnung, Gesamtzeitraum für das Gewicht. */}
      {(() => {
        const haupt = reihen.reduce((a, r) => (r.n.at(-1) ?? 0) > (a?.n.at(-1) ?? 0) ? r : a,
                                    reihen[0]);
        const i = haupt.n.length - 1;
        if (!haupt.n[i]) return null;
        const nGes = reihen.reduce((a, r) => a + r.n.reduce((x, y) => x + y, 0), 0);
        const sbGes = reihen.reduce((a, r) => a + r.sb.reduce((x, y) => x + y, 0), 0);
        return (
          <p className="mp-befund">
            {t(TXT.bieterZahl, {
              jahr: haupt.von + i, sb: zahl(haupt.sb[i]), n: zahl(haupt.n[i]),
              pct: zahl((100 * haupt.sb[i]) / haupt.n[i], 1),
              sbGes: zahl(sbGes), nGes: zahl(nGes),
            })}
          </p>
        );
      })()}

      <p className="mp-basis">
        {b.offene_mit_bieterzahl === 0
          ? t(TXT.bieterRueckblickNull)
          : t(TXT.bieterRueckblick, { n: zahl(b.offene_mit_bieterzahl) })}
      </p>
      <p className="mp-basis">{t(TXT.bieterBasis)}</p>

      {/* Die Abdeckung IST der Vorbehalt — ohne sie liest sich der Wert als Aussage über
          den ganzen Markt. Ab 2023 fällt sie von ~88 % auf ~60 %, weil DÖE dazukam und
          dieses Feld nicht führt. */}
      {abd.length ? (
        <details className="mp-table">
          <summary>{t(TXT.bieterAbdeckungTitel)}</summary>
          <table>
            <thead>
              <tr>
                <th scope="col">{t(TXT.spalteJahr)}</th>
                <th scope="col">{t(TXT.spalteFaelle)}</th>
                <th scope="col">%</th>
              </tr>
            </thead>
            <tbody>
              {abd.filter((a) => a.jahr >= ersteJ).map((a) => (
                <tr key={a.jahr}>
                  <th scope="row">{a.jahr}</th>
                  <td>{zahl(a.cans)}</td>
                  <td>{zahl(a.pct, 1)} %</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      ) : null}

      <details className="mp-table">
        <summary>{t(TXT.tabelle)}</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">{t(TXT.spalteJahr)}</th>
              {reihen.map((r) => <th key={r.quelle} scope="col">{quelleName(r.quelle)}</th>)}
            </tr>
          </thead>
          <tbody>
            {sicht.map((jahr) => (
              <tr key={jahr}>
                <th scope="row">{jahr}</th>
                {reihen.map((r) => {
                  const i = jahr - r.von;
                  const da = i >= 0 && i < r.n.length && r.n[i] > 0;
                  return (
                    <td key={r.quelle}>
                      {da ? (
                        <>
                          {zahl((100 * r.sb[i]) / r.n[i], 1)} %
                          <span className="mp-abs">{zahl(r.sb[i])} / {zahl(r.n[i])}</span>
                        </>
                      ) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

/* ── Komponente ───────────────────────────────────────────────────────────── */
export default function Marktpuls({
  daten, src = "/api/marktpuls", titel, zeigeLage = true,
}: {
  daten?: MarktpulsDaten | null;
  src?: string;
  titel?: string;
  zeigeLage?: boolean;
}) {
  const { t } = useSprache();
  const [geholt, setGeholt] = useState<MarktpulsDaten | null>(null);
  const [fehler, setFehler] = useState(false);
  const d = daten ?? geholt;

  useEffect(() => {
    if (daten) return;                       // vorgeladen → kein Nachladen (Briefing §5)
    let lebt = true;
    fetch(src, { cache: "force-cache" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((j) => { if (lebt) setGeholt(j as MarktpulsDaten); })
      .catch(() => { if (lebt) setFehler(true); });
    return () => { lebt = false; };
  }, [daten, src]);

  const laenderTabs = useMemo(
    () => (d ? [d.gesamt_key, ...d.laender] : []), [d]);
  const [land, setLand] = useState<string | null>(null);
  const [branche, setBranche] = useState<string>(ALLE);
  const [ansicht, setAnsicht] = useState<"saison" | "jahre" | "bieter">("saison");
  const aktivesLand = land ?? d?.gesamt_key ?? "gesamt";
  // Eine Datei nach Stand 1 kennt `jahre` nicht — dann gibt es den Umschalter nicht,
  // statt auf eine leere Ansicht zu zeigen.
  const hatJahre = !!d?.jahre?.achse?.length;
  const hatBieter = !!d?.bieter && Object.keys(d.bieter.reihen).length > 0;
  const zeigeJahre = hatJahre && ansicht === "jahre";
  const zeigeBieter = hatBieter && ansicht === "bieter";

  if (fehler) return <div className="mp-wrap"><p className="mp-sub">{t(TXT.ladefehler)}</p></div>;
  if (!d) return <div className="mp-wrap"><p className="mp-sub">{t(TXT.laedt)}</p></div>;

  const block = d.saison[`${aktivesLand}|${branche}`];
  const lage = d.lage.je_land[aktivesLand];
  const branchen = d.lage.je_branche[aktivesLand] ?? [];
  const alt = tageSeit(d.erzeugt);
  const veraltet = alt > VERALTET_TAGE;
  const cov = d.coverage[aktivesLand];

  // Skalierung: der höchste Monatswert füllt die Fläche. Nullbasis ist Pflicht — eine
  // gekappte Achse liesse eine 5-%-Abweichung wie eine Verdopplung aussehen.
  const max = Math.max(1, ...(block?.monate ?? []).map((m) => m.avg));
  // Vier Stufen: Ausreisser (±25 %, der benannte Befund) und die einfache Frage „über oder
  // unter dem Jahresmittel" (Briefing §3.3). Ohne die zweite Stufe sähe eine gleichmässige
  // Verteilung komplett uniform aus, obwohl die Mittellinie sie sehr wohl teilt.
  const lvl = (pct: number) =>
    pct >= AUSREISSER ? "hoch" : pct <= -AUSREISSER ? "tief" : pct > 0 ? "ueber" : "unter";
  /* Ein grosser Balken, der jährlich die Richtung wechselt, ist keine Saison — er ist die
     Streuung eines dünnen Segments. Gemessen CH/Medizin: März +64 % im Fenster, über die
     Jahre ohne Bestand. Ohne diese Kennzeichnung widerspräche das Bild dem Satz darunter,
     der genau deshalb einen anderen Monat nennt. */
  const unsicher = (m: MarktpulsMonat) =>
    !m.stabil && Math.abs(m.pct) >= AUSREISSER;

  const landLabel = (k: string) =>
    k === d.gesamt_key ? t(TXT.alleLaender) : t(LAND_LABEL[k] ?? k);

  /* Der Begleittext entsteht HIER aus den Zahlen, nicht im Skript (AC5). */
  function befundText(b: MarktpulsBefund): string {
    const beleg = b.jahre && b.jahre_gleich && b.monat && b.spanne
      ? " " + t(TXT.befundBeleg, {
          gleich: b.jahre_gleich, jahre: b.jahre, monat: t(MONAT_LANG[b.monat - 1]),
          von: zahl(b.spanne[0], 0), bis: zahl(b.spanne[1], 0),
        })
      : "";
    if (b.typ === "spitze" && b.monat) {
      return t(TXT.befundSpitze,
        { monat: t(MONAT_LANG[b.monat - 1]), n: zahl(b.avg ?? 0), pct: zahl(b.pct ?? 0, 0) }) + beleg;
    }
    if (b.typ === "tief" && b.monat) {
      return t(TXT.befundTief,
        { monat: t(MONAT_LANG[b.monat - 1]), n: zahl(b.avg ?? 0), pct: zahl(Math.abs(b.pct ?? 0), 0) }) + beleg;
    }
    if (b.typ === "flach") {
      return t(TXT.befundFlach, {
        hoch: t(MONAT_LANG[(b.monat ?? 1) - 1]), pctHoch: mitVorzeichen(b.pct ?? 0),
      });
    }
    return t(TXT.befundLeer);
  }

  return (
    <section className="mp-wrap" aria-label={t(TXT.titel)}>
      <div className="mp-head">
        <h3>{titel ?? t(TXT.titel)}</h3>
        <span className="mp-stand" data-alt={veraltet ? "ja" : "nein"}>
          {t(TXT.stand, { datum: datum(d.stand) })}
        </span>
      </div>
      <p className="mp-sub">{t(TXT.frage)}</p>
      {veraltet ? (
        <p className="mp-note" role="status">
          {t(TXT.veraltet,
            { n: alt, datum: datum(d.stand) })}
        </p>
      ) : null}

      {/* ── Umschalter: arbeitet ausschliesslich auf dem geladenen JSON ── */}
      <div className="mp-switch">
        {hatJahre || hatBieter ? (
          <div className="mp-group" role="group" aria-label={t(TXT.zeitraum)}>
            <span className="mp-lbl">{t(TXT.zeitraum)}</span>
            {([["saison", true, TXT.ansichtSaison],
               ["jahre", hatJahre, TXT.ansichtJahre],
               ["bieter", hatBieter, TXT.ansichtBieter]] as const)
              .filter(([, da]) => da)
              .map(([a, , label]) => (
                <button key={a} type="button" aria-pressed={a === ansicht}
                        onClick={() => setAnsicht(a as typeof ansicht)}>
                  {t(label)}
                </button>
              ))}
          </div>
        ) : null}
        <div className="mp-group" role="group" aria-label={t(TXT.land)}>
          <span className="mp-lbl">{t(TXT.land)}</span>
          {laenderTabs.map((k) => {
            const c = d.coverage[k];
            const duenn = k !== d.gesamt_key && !!c && !c.belastbar;
            return (
              <button key={k} type="button" aria-pressed={k === aktivesLand} disabled={duenn}
                      title={duenn ? t(TXT.landZuDuenn,
                                       { n: zahl(c.verfahren_im_fenster) }) : undefined}
                      onClick={() => setLand(k)}>
                {landLabel(k)}
              </button>
            );
          })}
        </div>
        <div className="mp-group" role="group" aria-label={t(TXT.branche)}>
          <span className="mp-lbl">{t(TXT.branche)}</span>
          {[ALLE, ...d.branchen].map((b) => {
            const bl = d.saison[`${aktivesLand}|${b}`];
            // Die Schwelle gilt für die ANGEZEIGTE Achse: eine Branche kann im
            // 5-Jahres-Fenster zu dünn sein und über 22 Jahre reichlich Fälle haben.
            // Würde hier immer der Saison-Wert entscheiden, bliebe die Historie einer
            // Branche unerreichbar, obwohl sie vorliegt.
            const jr = d.jahre?.reihen[`${aktivesLand}|${b}`] ?? [];
            const jahreN = jr.reduce((s, r) => s + r.werte.reduce((a, v) => a + v, 0), 0);
            const zuwenig = zeigeBieter
              ? !(d.bieter?.reihen[`${aktivesLand}|${b}`]?.length)
              : zeigeJahre
                ? jahreN < d.min_faelle
                : !!bl && !bl.genug;
            return (
              <button key={b} type="button" aria-pressed={b === branche} disabled={zuwenig}
                      title={zuwenig ? t(TXT.brancheZuWenig,
                                         { n: zahl(zeigeJahre ? jahreN : bl?.verfahren_gesamt ?? 0),
                                           min: zahl(d.min_faelle) }) : undefined}
                      onClick={() => setBranche(b)}>
                {b === ALLE ? t(TXT.alleBranchen) : t(BRANCHE_LABEL[b] ?? b)}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Teil 1: Saisonalität ODER Jahres-Layer ── */}
      {zeigeBieter ? (
        <BieterDiagramm d={d} land={aktivesLand} branche={branche} />
      ) : zeigeJahre ? (
        <>
          <JahresDiagramm d={d} land={aktivesLand} branche={branche} />
          {/* Ohne `--ab-jahr` deckt der Jahres-Layer nur das Saison-Fenster ab. Das ist
              kein Fehler, aber es muss dastehen — sonst liest sich „Jahre" als „alles,
              was wir haben". */}
          {d.jahre!.von > 2004 && d.jahre!.von >= d.fenster.von ? (
            <p className="mp-basis">
              {t(TXT.achseNurFenster,
                 { von: d.jahre!.von, bis: d.jahre!.bis, frueh: 2004 })}
            </p>
          ) : null}
        </>
      ) : !block || !block.genug ? (
        <p className="mp-note">
          {t(TXT.kombiZuWenig,
            { min: zahl(d.min_faelle) })}
        </p>
      ) : (
        <div className="mp-chart">
          <div className="mp-bars" role="img"
               aria-label={t(TXT.diagramm, { von: d.fenster.von, bis: d.fenster.bis })}>
            <div className="mp-mean" style={{ bottom: `${(block.jahresmittel / max) * 100}%` }}>
              <span>{t(TXT.jahresmittelLinie, { n: zahl(block.jahresmittel) })}</span>
            </div>
            {block.monate.map((m) => (
              <div key={m.m} className="mp-bar" data-lvl={lvl(m.pct)}
                   data-unsicher={unsicher(m) ? "ja" : undefined}
                   title={unsicher(m) ? t(TXT.monatUnsicher) : undefined}>
                <b>{zahl(Math.round(m.avg))}</b>
                <i style={{ height: `${(m.avg / max) * 100}%` }} />
              </div>
            ))}
          </div>
          <div className="mp-axis" aria-hidden="true">
            {block.monate.map((m) => (
              <span key={m.m} data-lvl={lvl(m.pct)}>{t(MONAT_KURZ[m.m - 1])}</span>
            ))}
          </div>

          <p className="mp-befund">{befundText(block.befund)}</p>

          <p className="mp-basis">
            {t(TXT.basis,
              { n: zahl(block.verfahren_gesamt), jahre: d.fenster.jahre, von: d.fenster.von, bis: d.fenster.bis })}
          </p>

          {/* Barrierefreiheit: dieselben Werte als Tabelle (Briefing §5/AC10). */}
          <details className="mp-table">
            <summary>{t(TXT.tabelle)}</summary>
            <table>
              <thead>
                <tr>
                  <th scope="col">{t(TXT.spalteMonat)}</th>
                  <th scope="col">{t(TXT.spalteAvg)}</th>
                  <th scope="col">{t(TXT.spalteAbw)}</th>
                </tr>
              </thead>
              <tbody>
                {block.monate.map((m) => (
                  <tr key={m.m}>
                    <th scope="row">{t(MONAT_LANG[m.m - 1])}</th>
                    <td>{zahl(m.avg, 1)}</td>
                    <td>{mitVorzeichen(m.pct, 1)} %</td>
                  </tr>
                ))}
                <tr>
                  <th scope="row">{t(TXT.jahresmittel)}</th>
                  <td>{zahl(block.jahresmittel, 1)}</td>
                  <td>—</td>
                </tr>
              </tbody>
            </table>
          </details>
        </div>
      )}

      {/* ── Teil 2: Aktuelle Lage ── */}
      {zeigeLage && lage ? (
        <div className="mp-lage">
          <h4>{t(TXT.lage)}</h4>
          <p className="mp-befund">
            {aktivesLand === d.gesamt_key
              ? t(TXT.lageGesamt,
                  { n: zahl(lage.laufend) })
              : t(TXT.lageLand,
                  { n: zahl(lage.laufend), raum: t(LAND_IN[aktivesLand] ?? aktivesLand) })}
          </p>
          <div className="mp-kpis">
            <div className="mp-kpi"><b>{zahl(lage.laufend)}</b><span>{t(TXT.kpiLaufend)}</span></div>
            <div className="mp-kpi"><b>{zahl(lage.zuschlag_30d)}</b><span>{t(TXT.kpiZuschlag, { n: d.lage.fenster_tage })}</span></div>
            <div className="mp-kpi"><b>{zahl(lage.aufhebung_30d)}</b><span>{t(TXT.kpiAufhebung, { n: d.lage.fenster_tage })}</span></div>
            <div className="mp-kpi"><b>{zahl(lage.ohne_frist)}</b><span>{t(TXT.kpiOhneFrist)}</span></div>
          </div>

          {branchen.length ? (
            <ul className="mp-branchen">
              {branchen.map((b) => (
                <li key={b.key}>
                  <span>{t(BRANCHE_LABEL[b.key] ?? b.key)}</span>
                  <span className="mp-n">{zahl(b.n)}</span>
                  <span className="mp-track" aria-hidden="true">
                    <i style={{ width: `${Math.round((b.n / Math.max(1, branchen[0].n)) * 100)}%` }} />
                  </span>
                </li>
              ))}
            </ul>
          ) : null}

          {/* Herkunft der Frist ausweisen — Projekt-Konvention, nie stillschweigend schätzen. */}
          <p className="mp-basis">
            {t(TXT.fristBasis,
              { pct: zahl(lage.frist_abdeckung, 1) })}
          </p>
        </div>
      ) : null}

      {/* ── Herkunft der Zeitreihe ──
          Die Herkunfts-Zeile gehört zur ANGEZEIGTEN Achse. Der Ausschluss von DÖE/simap ist
          eine Regel des Monatsdurchschnitts; in der Jahresansicht stehen genau diese Quellen
          als eigene Reihen im Bild. Beides gleichzeitig zu behaupten war der erste Zustand
          dieser Zeile — er las sich als Widerspruch zum Diagramm direkt darüber. */}
      {zeigeBieter ? null : zeigeJahre ? (
        <p className="mp-quelle">
          {t(TXT.quellenJahre, {
            quellen: [...new Set((d.jahre!.reihen[`${aktivesLand}|${branche}`] ?? [])
              .map((r) => t(QUELLE_LABEL[r.quelle] ?? r.quelle)))].join(", "),
          })}
        </p>
      ) : cov ? (
        <p className="mp-quelle">
          {t(TXT.quellen, {
            quellen: cov.quellen_zeitreihe.map((q) => t(QUELLE_LABEL[q] ?? q)).join(", "),
          })}
          {cov.quellen_ausgeschlossen.length ? " " + cov.quellen_ausgeschlossen.map((q) =>
            t(TXT.quelleRaus,
              { quelle: t(QUELLE_LABEL[q.quelle] ?? q.quelle), jahr: q.von })).join(" ") : null}
          {cov.nicht_belastbar?.length
            ? " " + t(TXT.duenneLaender,
                { laender: cov.nicht_belastbar.map((k) => t(LAND_LABEL[k] ?? k)).join(", ") })
            : null}
          {aktivesLand !== d.gesamt_key && !cov.belastbar
            ? " " + t(TXT.landNichtBelastbar)
            : null}
        </p>
      ) : null}
    </section>
  );
}
