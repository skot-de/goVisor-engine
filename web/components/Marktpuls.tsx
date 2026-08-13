"use client";

import { useEffect, useMemo, useState } from "react";
import { useSprache } from "@/lib/i18n";
import "./marktpuls.css";

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
export type MarktpulsMonat = { m: number; avg: number; pct: number; pct_naiv: number };
export type MarktpulsBefund = {
  typ: "spitze" | "tief" | "flach" | "keine_daten";
  monat?: number; pct?: number; avg?: number; monat_tief?: number; pct_tief?: number;
};
export type MarktpulsSaison = {
  monate: MarktpulsMonat[]; jahresmittel: number; verfahren_gesamt: number;
  jahre: number[]; befund: MarktpulsBefund; genug: boolean;
};
export type MarktpulsCoverage = {
  verfahren_gesamt: number; verfahren_im_fenster: number;
  quellen_zeitreihe: string[];
  quellen_ausgeschlossen: { quelle: string; verfahren: number; von: number; bis: number }[];
  letzte_veroeffentlichung: string | null; belastbar: boolean;
  /** nur am Aggregat: Länder, die mitgezählt, aber für eine eigene Kurve zu dünn sind. */
  nicht_belastbar?: string[];
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
  DE: "Deutschland", AT: "Österreich", CH: "Schweiz", EU: "Übrige EU-Länder",
};
/* Eigene Form für „in …": „in der Schweiz", nicht „in Schweiz". Die Präposition steckt im
 * Satz, der Artikel am Land — zusammengesetzte Sätze aus Bausteinen brechen sonst in jeder
 * Sprache an genau dieser Stelle. */
const LAND_IN: Record<string, string> = { DE: "Deutschland", AT: "Österreich", CH: "der Schweiz" };
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
  frage: "Wann wird ausgeschrieben — und was läuft gerade?",
  stand: "Stand: {datum}",
  ladefehler: "Marktpuls derzeit nicht verfügbar.",
  laedt: "Marktpuls wird geladen …",
  veraltet: "Der nächtliche Lauf ist seit {n} Tagen nicht durchgelaufen. Angezeigt wird der letzte erfolgreiche Stand vom {datum} — nicht der heutige.",
  land: "Land",
  branche: "Branche",
  alleLaender: "Alle Länder",
  alleBranchen: "Alle Branchen",
  landZuDuenn: "Zu wenige Verfahren im Fenster ({n}) — für dieses Land gibt es noch keine belastbare Kurve.",
  brancheZuWenig: "Zu wenige Verfahren ({n}, Mindestzahl {min}).",
  kombiZuWenig: "Zu wenige Verfahren für diese Kombination — die Kurve wäre nicht belastbar (Mindestzahl {min}).",
  diagramm: "Ø Ausschreibungen je Kalendermonat, {von} bis {bis}",
  jahresmittelLinie: "Jahresmittel {n}",
  befundSpitze: "Der stärkste Monat ist {monat} mit Ø {n} Ausschreibungen — {pct} % über dem Jahresmittel.",
  befundTief: "Der schwächste Monat ist {monat} mit Ø {n} Ausschreibungen — {pct} % unter dem Jahresmittel.",
  befundFlach: "Die Ausschreibungen verteilen sich über das Jahr gleichmäßiger als oft angenommen: kein Monat weicht um mehr als {schwelle} % vom Jahresmittel ab. Stärkster Monat {hoch} ({pctHoch} %), schwächster {tief} ({pctTief} %).",
  befundLeer: "Für diese Auswahl liegen keine Werte vor.",
  basis: "Grundlage: {n} Verfahren aus {jahre} vollen Jahren ({von}–{bis}). Gezählt wird das Verfahren, nicht die Bekanntmachung — Korrektur- und Folgebekanntmachungen desselben Verfahrens zählen einmal.",
  tabelle: "Werte als Tabelle",
  spalteMonat: "Monat",
  spalteAvg: "Ø Ausschreibungen",
  spalteAbw: "Abweichung vom Jahresmittel",
  jahresmittel: "Jahresmittel",
  lage: "Aktuelle Lage",
  lageGesamt: "Aktuell laufen {n} Ausschreibungen, auf die geboten werden kann — über alle erfassten Länder.",
  lageLand: "Aktuell laufen in {raum} {n} Ausschreibungen, auf die geboten werden kann.",
  kpiLaufend: "laufende Ausschreibungen",
  kpiZuschlag: "Zuschläge (letzte {n} Tage)",
  kpiAufhebung: "Aufhebungen (letzte {n} Tage)",
  kpiOhneFrist: "frisch, aber ohne veröffentlichte Frist",
  fristBasis: "„Laufend“ steht auf der Angebotsfrist aus der Bekanntmachung ({pct} % der frisch veröffentlichten Verfahren tragen eine). Verfahren ohne veröffentlichte Frist sind nicht mitgezählt — die Zahl ist eine Untergrenze, keine Vollzählung.",
  quellen: "Zeitreihe aus: {quellen}.",
  quelleRaus: "{quelle} ist erst ab {jahr} im Bestand und bleibt aus der Zeitreihe heraus — ein Quellen-Start ist ein Ingest-Sprung, kein Marktsignal.",
  duenneLaender: "Mitgezählt, aber für eine eigene Kurve zu dünn: {laender}.",
  landNichtBelastbar: "Für dieses Land reicht die Datenlage im Fenster nicht für eine belastbare Kurve.",
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
  const aktivesLand = land ?? d?.gesamt_key ?? "gesamt";

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

  const landLabel = (k: string) =>
    k === d.gesamt_key ? t(TXT.alleLaender) : t(LAND_LABEL[k] ?? k);

  /* Der Begleittext entsteht HIER aus den Zahlen, nicht im Skript (AC5). */
  function befundText(b: MarktpulsBefund): string {
    if (b.typ === "spitze" && b.monat) {
      return t(TXT.befundSpitze,
        { monat: t(MONAT_LANG[b.monat - 1]), n: zahl(b.avg ?? 0), pct: zahl(b.pct ?? 0, 0) });
    }
    if (b.typ === "tief" && b.monat) {
      return t(TXT.befundTief,
        { monat: t(MONAT_LANG[b.monat - 1]), n: zahl(b.avg ?? 0), pct: zahl(Math.abs(b.pct ?? 0), 0) });
    }
    if (b.typ === "flach") {
      return t(TXT.befundFlach, {
        schwelle: AUSREISSER,
        hoch: t(MONAT_LANG[(b.monat ?? 1) - 1]), pctHoch: mitVorzeichen(b.pct ?? 0),
        tief: t(MONAT_LANG[(b.monat_tief ?? 1) - 1]), pctTief: mitVorzeichen(b.pct_tief ?? 0),
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
            const zuwenig = !!bl && !bl.genug;
            return (
              <button key={b} type="button" aria-pressed={b === branche} disabled={zuwenig}
                      title={zuwenig ? t(TXT.brancheZuWenig,
                                         { n: zahl(bl!.verfahren_gesamt), min: zahl(d.min_faelle) }) : undefined}
                      onClick={() => setBranche(b)}>
                {b === ALLE ? t(TXT.alleBranchen) : t(BRANCHE_LABEL[b] ?? b)}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Teil 1: Saisonalität ── */}
      {!block || !block.genug ? (
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
              <div key={m.m} className="mp-bar" data-lvl={lvl(m.pct)}>
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

      {/* ── Herkunft der Zeitreihe ── */}
      {cov ? (
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
