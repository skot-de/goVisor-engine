"use client";

import { useEffect, useMemo, useState } from "react";
import { applyState, nutzerLand, renderProfil, setNachbarn } from "@/lib/explorerCore";
import { useSprache } from "@/lib/i18n";
import { ContractsEditor } from "./ContractsEditor";
import { Trefferguete } from "./Trefferguete";
import { Regionen } from "./Regionen";

/* Strategie (Ticket #10) — unternehmerische Sicht, nicht operative.
   Acht Sektionen in zwei Gruppen, vertikale Abschnittsnavigation (keine zweite Tab-Ebene). */

type Quartal = {
  q: string; nGesamt: number; volEcht: number; nEcht: number;
  volSchaetz: number; nSchaetz: number; nUnbekannt: number;
  nRahmenOhneWb: number; nEndeGeschaetzt: number;
};
type Posten = {
  id: string; titel: string; buyer: string; wert: string; wertSrc: string;
  ende: string; endeSrc: string; rahmen: boolean;
};
type Quote = { pct: number; n: number; treffer: number } | null;
type Stelle = {
  id: string; name: string; vergaben36: number; vergabenFeld: number; vergabenJahr: number;
  volEcht: number | null; volN: number; bieterMedian: number | null; bieterN: number;
  kmu: Quote; preis: Quote; wechsel: Quote; neuAnteil: Quote;
  neuzugangJahr: number | null; neueAnbieter: number; anbieterGesamt: number;
  top1: number | null; top: { n: string; wins: number; pct: number }[];
};
type Fenster = {
  id: string; titel: string; buyer: string; ende: string; fenster: string; tage: number;
  wert: string | null; wertSrc: string; endeSrc: string; nGelistet: number; gelistete: string[];
};
type Feld = {
  cpv4: string; label: string; vergaben36: number; vergabenJahr: number;
  trend: number | null; bieterMedian: number | null; bieterN: number;
  kleinstesLos: number | null; losN: number; buergschaft: Quote;
  volEcht: number | null; volN: number;
};
type Nachbar = { cpv4: string; label: string; naehe: number; firmen: number };
type Einstieg = {
  id: string; titel: string; buyer: string; wert: string; wertSrc: string;
  frist: string; bieterFeld: number | null;
};
type Anbieter = {
  id: string; name: string; wins: number; stellen: number; vol: number | null; trend: number | null;
};
type ProfilZeile = { buyer: string; wins: number; anteil: number; markt: number; ueber: number };
type Matrix = {
  buyers: { id: string; name: string }[];
  supplier: { id: string; name: string }[];
  cells: number[][];
};
type Wett = { anbieter: Anbieter[]; profile: Record<string, ProfilZeile[]>; matrix: Matrix | [] | null; _anbieterTotal?: number };
type Faehig = {
  nLeads: number;
  regime: { code: string; label: string; n: number; vol: number | null }[];
  buergschaft: { treffer: number; vol: number | null; n: number };
  nachweise: { code: string; n: number }[];
};
type Strat = {
  quartale: Quartal[]; top: Posten[]; stellen: Stelle[];
  felder: Feld[]; nachbarn: Nachbar[]; einstieg: Einstieg[]; wettbewerb: Wett; faehigkeiten: Faehig;
  bindung: {
    rahmen: number; belegtGesperrt: number; gelisteteUnbekannt: number;
    volGesperrt: number | null; volN: number; fenster: Fenster[];
  };
  summe: { nGesamt: number; volEcht: number; volSchaetz: number; nUnbekannt: number; nRahmenOhneWb: number };
  _pro?: boolean;                 // Härtung 4: false = Free (Teaser-Redaktion aktiv)
};

// Teaser-Bausteine für die abgestufte Paywall (Härtung 4).
const isPro = (d: { _pro?: boolean } | null | undefined) => d?._pro !== false;
function Lock() {
  const { t } = useSprache();
  return <span className="st-lock" title={t("Im Pro-Zugang sichtbar")}>•••</span>;
}
// `titel`/`frage`/`was` kommen als deutsche Literale von der Aufrufstelle — hier, beim
// Rendern, übersetzt, nicht an der Definition (sonst fröre die Sprache beim Import ein).
function ProGate({ titel, frage, was }: { titel: string; frage: string; was: string }) {
  const { t } = useSprache();
  return (
    <>
      <div className="st-head"><div><h4>{t(titel)}</h4><p className="st-frage">{t(frage)}</p></div></div>
      <div className="st-progate">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="10" width="16" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
        <div className="st-progate-t">{t(was)}</div>
        <div className="st-progate-s">{t("Im Pro-Zugang vollständig sichtbar.")}</div>
      </div>
    </>
  );
}

/* Fallzahl-Schwellen (Ticket §3.1). Eine Quote aus 2 Fällen als „50 %" auszuweisen ist
   genau die Falschpräzision, die das Produkt vermeidet — deshalb entscheidet n über die
   Darstellungsform, nicht nur über einen Tooltip. */
function Q({ q, suffix = "" }: { q: Quote; suffix?: string }) {
  const { t } = useSprache();
  if (!q || q.n === 0) return <span style={{ color: "var(--ink-300)" }}>—</span>;
  if (q.n <= 2) {
    return (
      <span className="val" data-src="duenn" title={t("Dünn · gemessen, aber nur {n} Fälle, für eine Quote zu wenig", { n: q.n })}>
        {t("{treffer} von {n}", { treffer: q.treffer, n: q.n })}
      </span>
    );
  }
  if (q.n <= 7) {
    return (
      <span className="val" data-src="duenn" title={t("Dünn · gemessen aus {n} Vergaben", { n: q.n })}>
        <span className="v-num">{q.pct} %</span>
        <span className="q-n">{t("aus {n}", { n: q.n })}</span>
      </span>
    );
  }
  return <span className="v-num">{q.pct} %{suffix}</span>;
}

export const SEKTIONEN = [
  { group: "Markt", items: [
    { key: "pipeline", label: "Pipeline", frage: "Was kommt in 12/24/36 Monaten?" },
    { key: "felder", label: "Felder", frage: "Wo ist Platz, wo ist es eng?" },
    { key: "stellen", label: "Vergabestellen", frage: "Wo lohnt Beziehungsaufbau?" },
    { key: "region", label: "Region", frage: "Wo steht der Markt geografisch?" },
    { key: "wettbewerb", label: "Wettbewerb", frage: "Wer holt was, wer hält was?" },
  ]},
  { group: "Wir", items: [
    { key: "position", label: "Position", frage: "Wo stehen wir?" },
    { key: "faehigkeiten", label: "Fähigkeiten", frage: "Was blockiert uns?" },
    { key: "bindung", label: "Bindung", frage: "Was ist uns verschlossen?" },
    { key: "trefferguete", label: "Treffergüte", frage: "Warum passt manches nicht, und was ändert das?" },
    { key: "profil", label: "Profil", frage: "Wer sind wir?" },
  ]},
];

function eur(v: number): string {
  if (v >= 1e9) return (v / 1e9).toFixed(2).replace(".", ",") + " Mrd €";
  if (v >= 1e6) return (v / 1e6).toFixed(1).replace(".", ",") + " Mio €";
  return Math.round(v).toLocaleString("de-DE") + " €";
}
function qLabel(iso: string): string {
  const d = new Date(iso);
  return `Q${Math.floor(d.getMonth() / 3) + 1}/${String(d.getFullYear()).slice(2)}`;
}

/* ── Pipeline ───────────────────────────────────────────────────────────────
   Drei Herkunftsklassen gestapelt — NIE addiert (Ticket §3.3). Quartale ohne
   Datenlage bleiben leer, werden nicht interpoliert. */
function Pipeline({ data }: { data: Strat }) {
  const { t } = useSprache();
  const [monate, setMonate] = useState(24);
  const q = useMemo(() => data.quartale.slice(0, Math.ceil(monate / 3)), [data, monate]);
  const max = Math.max(1, ...q.map((x) => x.volEcht + x.volSchaetz));
  const sum = {
    echt: q.reduce((a, x) => a + x.volEcht, 0),
    schaetz: q.reduce((a, x) => a + x.volSchaetz, 0),
    unbekannt: q.reduce((a, x) => a + x.nUnbekannt, 0),
    gesamt: q.reduce((a, x) => a + x.nGesamt, 0),
    rahmen: q.reduce((a, x) => a + x.nRahmenOhneWb, 0),
  };

  return (
    <>
      <div className="st-head">
        <div>
          <h4>{t("Pipeline")}</h4>
          <p className="st-frage">{t("Was kommt in den nächsten {n} Monaten auf euch zu?", { n: monate })}</p>
        </div>
        <div className="fp-chips">
          {[12, 24, 36].map((m) => (
            <button key={m} className={`fp-chip ${monate === m ? "on" : ""}`} onClick={() => setMonate(m)}>{t("{n} Mon.", { n: m })}</button>
          ))}
        </div>
      </div>

      <div className="bstats">
        <div className="bstat">
          <span className="bstat-k">{t("Auslaufende Verträge")}</span>
          <span className="bstat-v"><span className="v-num">{sum.gesamt.toLocaleString("de-DE")}</span></span>
        </div>
        <div className="bstat">
          <span className="bstat-k">{t("Volumen belegt")}</span>
          <span className="bstat-v"><span className="v-num">{eur(sum.echt)}</span></span>
          <span className="bstat-m">{t("veröffentlichter Auftragswert")}</span>
        </div>
        <div className="bstat">
          <span className="bstat-k">{t("Volumen geschätzt")}</span>
          <span className="bstat-v"><span className="val" data-src="schaetz"><span className="v-num">{eur(sum.schaetz)}</span></span></span>
          <span className="bstat-m">{t("abgeleitet, nicht veröffentlicht")}</span>
        </div>
        <div className="bstat bstat-wide">
          <span className="bstat-k">{t("Ohne Wertangabe")}</span>
          <span className="bstat-v"><span className="v-num">{sum.unbekannt.toLocaleString("de-DE")}</span> {t("Verträge")}</span>
          <span className="bstat-flag">{t("Diese drei Klassen werden nicht addiert. Der Gesamtwert ist unbekannt, nicht die Summe der belegten.")}</span>
        </div>
      </div>

      <div className="st-chart">
        <div className="st-legend">
          <span><i className="lg lg-echt" />{t("belegt")}</span>
          <span><i className="lg lg-schaetz" />{t("geschätzt")}</span>
          <span><i className="lg lg-unk" />{t("ohne Wert (Anzahl)")}</span>
        </div>
        <div className="st-bars">
          {q.map((x) => {
            const hE = (x.volEcht / max) * 100;
            const hS = (x.volSchaetz / max) * 100;
            const leer = x.nGesamt === 0;
            return (
              <div key={x.q} className="st-bar" title={t("{q} · {n} Verträge · belegt {echt} · geschätzt {schaetz} · ohne Wert {unk}", { q: qLabel(x.q), n: x.nGesamt, echt: eur(x.volEcht), schaetz: eur(x.volSchaetz), unk: x.nUnbekannt })}>
                <div className="st-stack">
                  {leer ? <span className="st-empty" /> : (
                    <>
                      <i className="st-seg st-schaetz" style={{ height: `${hS}%` }} />
                      <i className="st-seg st-echt" style={{ height: `${hE}%` }} />
                    </>
                  )}
                </div>
                {x.nUnbekannt > 0 ? <span className="st-unk">{x.nUnbekannt}</span> : <span className="st-unk st-unk-0">—</span>}
                <span className="st-qlbl">{qLabel(x.q)}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="bhero bhero-mid" style={{ marginTop: "var(--s4)" }}>
        <div className="bhero-val" style={{ fontSize: 26, minWidth: 64 }}>{sum.rahmen.toLocaleString("de-DE")}</div>
        <div className="bhero-lbl">
          <span className="bhero-title">{t("davon in")} <b>{t("Rahmenvereinbarungen ohne erneuten Wettbewerb")}</b></span>
          <span className="bhero-note">
            {t("Volumen, das zwar ausläuft, aber nur für bereits Gelistete abrufbar ist. Wer nicht gelistet ist, kommt hier nicht zum Zug, unabhängig vom Angebot.")}
          </span>
        </div>
      </div>

      <section className="bsec" style={{ marginTop: "var(--s5)" }}>
        <h4>{t("Größte Einzelposten")}</h4>
        <div className="st-table">
          <div className="st-row st-row-h">
            <span>{t("Ausschreibung")}</span><span>{t("Vergabestelle")}</span><span>{t("Wert")}</span><span>{t("Vertragsende")}</span>
          </div>
          {data.top.map((p) => (
            <div key={p.id} className="st-row">
              <span className="st-t">
                {p.titel}
                {p.rahmen ? <span className="st-tag" title={t("Rahmen ohne erneuten Wettbewerb")}>{t("Rahmen")}</span> : null}
              </span>
              <span className="st-b">{p.buyer}</span>
              <span className="st-w"><span className="val" data-src={p.wertSrc}><span className="v-num">{p.wert}</span></span></span>
              <span className="st-e"><span className="val" data-src={p.endeSrc}>{p.ende}</span></span>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

/* ── Vergabestellen (Ticket §5.3) ──────────────────────────────────────────
   Leit-KPI ist die Offenheit (Anteil neuer Anbieter) — gemessen der belastbarste
   Wert: er braucht keine Nachfolge-Verkettung. Die Wechselquote steht daneben,
   trägt aber ihre Fallzahl sichtbar mit. */
const STELLEN_SPALTEN: { key: string; label: string; wert: (s: Stelle) => number }[] = [
  { key: "feld", label: "Vergabestelle", wert: (s) => s.vergabenFeld },
  { key: "jahr", label: "Vergaben/Jahr", wert: (s) => s.vergabenJahr },
  { key: "offen", label: "Offenheit", wert: (s) => s.neuAnteil?.pct ?? -1 },
  { key: "bieter", label: "Ø Bieter", wert: (s) => s.bieterMedian ?? -1 },
  { key: "kmu", label: "KMU", wert: (s) => s.kmu?.pct ?? -1 },
  { key: "preis", label: "nur Preis", wert: (s) => s.preis?.pct ?? -1 },
  { key: "wechsel", label: "Wechsel", wert: (s) => s.wechsel?.pct ?? -1 },
];

function Vergabestellen({ data, onOpenBuyer }: { data: Strat; onOpenBuyer: (s: Stelle) => void }) {
  const { t } = useSprache();
  const [sortKey, setSortKey] = useState("feld");
  const [sortDir, setSortDir] = useState(-1);   // -1 = absteigend

  const stellen = useMemo(() => {
    const sp = STELLEN_SPALTEN.find((c) => c.key === sortKey)!;
    return [...data.stellen].sort((a, b) => (sp.wert(a) - sp.wert(b)) * sortDir);
  }, [data, sortKey, sortDir]);

  function sortiere(k: string) {
    if (k === sortKey) setSortDir((d) => -d);
    else { setSortKey(k); setSortDir(-1); }
  }

  return (
    <>
      <div className="st-head">
        <div>
          <h4>{t("Vergabestellen")}</h4>
          <p className="st-frage">{t("Wo lohnt Beziehungsaufbau?")}</p>
        </div>
      </div>

      <div className="st-table st-stellen">
        <div className="st-row st-row-h">
          {STELLEN_SPALTEN.map((c) => (
            <span key={c.key} className="st-sortbar" onClick={() => sortiere(c.key)}
              data-sorted={sortKey === c.key ? "" : undefined}>
              {t(c.label)}
              <i className="st-arrow">{sortKey === c.key ? (sortDir < 0 ? "▼" : "▲") : "↕"}</i>
            </span>
          ))}
        </div>
        {stellen.map((s) => (
          <div key={s.id} className="st-row st-clickable" onClick={() => onOpenBuyer(s)}>
            <span className="st-t">
              {s.name}
              <span className="st-sub">{t("{feld} in eurem Feld · {gesamt} gesamt", { feld: s.vergabenFeld, gesamt: s.vergaben36 })}</span>
            </span>
            <span className="st-w"><span className="v-num">{s.vergabenJahr}</span></span>
            <span className="st-w">
              {s.neuAnteil
                ? <Q q={s.neuAnteil} />
                : <span className="v-sparse" title={t('Die Stelle taucht selbst erst im Beobachtungsfenster auf — dann wären zwangsläufig alle Anbieter „neu".')}>{t("nicht messbar")}</span>}
            </span>
            <span className="st-w">{s.bieterMedian != null ? <span className="v-num">{s.bieterMedian}</span> : <span style={{ color: "var(--ink-300)" }}>—</span>}</span>
            <span className="st-w"><Q q={s.kmu} /></span>
            <span className="st-w"><Q q={s.preis} /></span>
            <span className="st-w"><Q q={s.wechsel} /></span>
          </div>
        ))}
      </div>
    </>
  );
}

/* ── Marktüblich ────────────────────────────────────────────────────────────────────────
 * Der Median über die Vergabestellen DERSELBEN Branche. Genau die Rechnung, die die
 * Käufersicht (`VergabeblickView`) unter „Marktüblich" schon zeigt; sie stand dort seit
 * jeher und in der Anbieter-Sicht nicht, obwohl beide dieselbe Datei lesen
 * (`/api/strategie`) und `stellen` auch im Bieter-Kontext unredigiert bleibt.
 *
 * ⚠ ZWEI SCHWELLEN, BEIDE GEMESSEN, NICHT GERATEN.
 * 1 · Eine einzelne Quote zählt nur mit `n >= 8` mit. Das ist dieselbe Grenze, die `Q` in
 *     dieser Datei für „nicht mehr dünn" benutzt. Ein Median aus dünnen Quoten wäre eine
 *     glatte Zahl über lauter Unsicherheiten.
 * 2 · Unter zehn beitragenden Stellen gibt es GAR KEINEN Marktwert. Am 2026-09-01
 *     nachgemessen: in DE tragen 39 bis 60 Stellen je Kennzahl, in AT 13 bis 59, in der
 *     **Schweiz aber nur 1 bis 6 bei der Wechselquote**. Ein „marktüblich" aus drei Stellen
 *     wäre dort eine erfundene Zahl mit dem Anschein einer Messung. Lieber keine Zeile.
 *
 * ⚠ KEINE WERTUNG. Die Käufersicht färbt „schlechter als der Markt" rot, weil eine
 * Vergabestelle ein normatives Ziel hat: mehr Bieter ist besser. Ein Anbieter hat das
 * nicht. Eine Stelle mit wenigen Bietern ist für ihn ATTRAKTIV, nicht schlecht; „nur über
 * den Preis" ist gut, wenn er günstig ist, und schlecht, wenn er über Qualität punktet.
 * Hier steht deshalb nur, wo die Stelle liegt, nie ob das gut ist. */
const MIND_STELLEN = 10;
const MIND_FAELLE = 8;

type Lage = { med: number; unten: number; oben: number; n: number; gleich: boolean };

function marktLage(alle: Stelle[], pick: (s: Stelle) => number | null | undefined): Lage | null {
  const v = alle.map(pick).filter((x): x is number => x != null && Number.isFinite(x))
                .sort((a, b) => a - b);
  if (v.length < MIND_STELLEN) return null;
  const bei = (p: number) => v[Math.min(v.length - 1, Math.floor(v.length * p))];
  return { med: bei(0.5), unten: bei(0.25), oben: bei(0.75), n: v.length,
           gleich: v[0] === v[v.length - 1] };
}

/** Quoten-Feld als Zahl, aber nur wenn es belastbar ist. */
const ausQuote = (feld: "kmu" | "preis" | "wechsel" | "neuAnteil") => (s: Stelle) => {
  const q = s[feld] as Quote | undefined;
  return q && q.n >= MIND_FAELLE ? q.pct : null;
};

function Marktzeile({ eigen, lage, einheit = "" }: {
  eigen: number | null | undefined; lage: Lage | null; einheit?: string;
}) {
  const { t } = useSprache();
  if (lage == null) return null;
  const zahl = (v: number) => v.toLocaleString("de-DE", { maximumFractionDigits: 1 }) + einheit;
  // Viertel statt erfundener Schwelle: „weicht ab" braucht sonst eine Grenze, die niemand
  // begründen kann. Die Verteilung liefert sie mit.
  // ⚠ OHNE STREUUNG GIBT ES KEINE LAGE. Liegen oberes und unteres Viertel auf demselben
  // Wert, ist jede Stelle gleichzeitig in beiden, und die Bedingung unten stempelte JEDER
  // Stelle „oberes Viertel" auf. Am 2026-09-01 gemessen: in der Schweiz tragen alle 104
  // ausgewerteten Stellen denselben KMU-Anteil von 100 %; DE hat 64 verschiedene Werte,
  // AT 31. Die Schweizer KMU-Kennzeichnung unterscheidet dort also nichts, und das
  // gehoert gesagt statt in ein Viertel-Etikett verpackt.
  const streuung = lage.oben > lage.unten;
  const pos = lage.gleich ? t("bei allen Stellen gleich")
    : !streuung || eigen == null ? null
    : eigen >= lage.oben ? t("oberes Viertel")
    : eigen <= lage.unten ? t("unteres Viertel") : null;
  return (
    <span className="bstat-markt" title={t("Median aus {n} Vergabestellen derselben Branche", { n: lage.n })}>
      {t("marktüblich")} <b>{zahl(lage.med)}</b>
      {pos ? <em>{pos}</em> : null}
    </span>
  );
}

/* Detailansicht je Stelle — Lieferantenbild + Konzentration (§5.3) */
function StelleDetail({ s, alle, onBack }: { s: Stelle; alle: Stelle[]; onBack: () => void }) {
  const { t } = useSprache();
  // Marktüblich je Kennzahl: EINMAL rechnen, nicht sechsmal in der Darstellung.
  const m = useMemo(() => ({
    vergabenJahr: marktLage(alle, (x) => x.vergabenJahr),
    neuAnteil: marktLage(alle, ausQuote("neuAnteil")),
    bieterMedian: marktLage(alle, (x) => x.bieterMedian),
    kmu: marktLage(alle, ausQuote("kmu")),
    preis: marktLage(alle, ausQuote("preis")),
    wechsel: marktLage(alle, ausQuote("wechsel")),
  }), [alle]);
  // `konz` bleibt der deutsche Vergleichsschlüssel (s. `konzCls`) — übersetzt wird erst beim Rendern.
  const konz = s.top1 == null ? null : s.top1 < 25 ? "fragmentiert" : s.top1 <= 50 ? "moderat" : "oligopol";
  const konzCls = konz === "fragmentiert" ? "ok" : konz === "moderat" ? "mid" : "risk";
  return (
    <>
      <button className="sec-link" onClick={onBack} style={{ marginBottom: "var(--s3)" }}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5M11 18l-6-6 6-6" /></svg>
        {t("Alle Vergabestellen")}
      </button>
      <div className="st-head"><div><h4>{s.name}</h4>
        <p className="st-frage">{t("{n} Vergaben in 36 Monaten · {anbieter} verschiedene Anbieter", { n: s.vergaben36, anbieter: s.anbieterGesamt })}</p></div></div>

      <div className="bstats">
        <div className="bstat"><span className="bstat-k">{t("Vergaben pro Jahr")}</span>
          <span className="bstat-v"><span className="v-num">{s.vergabenJahr}</span></span>
          <Marktzeile eigen={s.vergabenJahr} lage={m.vergabenJahr} /></div>
        <div className="bstat"><span className="bstat-k">{t("Neue Anbieter (36 Mon.)")}</span>
          <span className="bstat-v">{s.neuAnteil ? <Q q={s.neuAnteil} /> : <span className="v-sparse">{t("nicht messbar")}</span>}</span>
          <span className="bstat-m">{s.neuAnteil ? t("{neu} von {gesamt} Anbietern", { neu: s.neueAnbieter, gesamt: s.anbieterGesamt }) : t("Stelle zu kurz in den Daten")}</span>
          <Marktzeile eigen={s.neuAnteil?.pct} lage={m.neuAnteil} einheit=" %" /></div>
        <div className="bstat"><span className="bstat-k">{t("Ø Bieter je Vergabe")}</span>
          <span className="bstat-v">{s.bieterMedian != null ? <span className="v-num">{s.bieterMedian}</span> : <span className="v-sparse">{t("zu wenig Daten")}</span>}</span>
          <span className="bstat-m">{s.bieterN ? t("aus {n} Vergaben", { n: s.bieterN }) : ""}</span>
          <Marktzeile eigen={s.bieterMedian} lage={m.bieterMedian} /></div>
        <div className="bstat"><span className="bstat-k">{t("Zuschläge an KMU")}</span>
          <span className="bstat-v"><Q q={s.kmu} /></span>
          <Marktzeile eigen={s.kmu?.pct} lage={m.kmu} einheit=" %" /></div>
        <div className="bstat"><span className="bstat-k">{t("Nur über den Preis entschieden")}</span>
          <span className="bstat-v"><Q q={s.preis} /></span>
          <Marktzeile eigen={s.preis?.pct} lage={m.preis} einheit=" %" /></div>
        <div className="bstat"><span className="bstat-k">{t("Wechsel bei Nachfolgevergaben")}</span>
          <span className="bstat-v"><Q q={s.wechsel} /></span>
          <span className="bstat-m">{t("braucht verkettete Vorgänger, oft dünn")}</span>
          <Marktzeile eigen={s.wechsel?.pct} lage={m.wechsel} einheit=" %" /></div>
      </div>

      {konz ? (
        <div className={`bhero bhero-${konzCls}`} style={{ marginTop: "var(--s4)" }}>
          <div className="bhero-val">{s.top1} %</div>
          <div className="bhero-lbl">
            <span className="bhero-title">{t("Der stärkste Anbieter hält")} <b>{s.top1} %</b> {t("der Zuschläge")} — {t(konz)}</span>
            <span className="bhero-note">
              {konz === "fragmentiert" ? t("Kein Anbieter dominiert. Als Neuer sind die Chancen strukturell offen.")
                : konz === "moderat" ? t("Einige feste Größen, aber es gibt Raum.")
                : t("Wenige teilen fast alles unter sich auf.")}
            </span>
          </div>
        </div>
      ) : null}

      <section className="bsec" style={{ marginTop: "var(--s5)" }}>
        <h4>{t("Wer gewinnt dort?")}</h4>
        <div className="bwinners">
          <span className="bwin-k">{t("Zuschlagsanteil der stärksten Anbieter. Keine Aussage über Beziehung, nur gezählte Zuschläge")}</span>
          <div className="bwin-list">
            {s.top.length ? s.top.map((w, i) => (
              <div key={i} className="bwin-row">
                <span className="bwin-bar"><i style={{ width: `${Math.min(100, w.pct * 2)}%` }} /></span>
                <span className="bwin-name">{w.n}</span>
                <span className="bwin-p"><span className="v-num">{w.pct} %</span></span>
                <span className="bwin-c"><span className="v-num">{w.wins}</span> {t("Zuschläge")}</span>
              </div>
            )) : <span className="v-sparse">{t("keine belegten Gewinner erfasst")}</span>}
          </div>
        </div>
      </section>
    </>
  );
}

/* ── Felder (Ticket §5.2) ──────────────────────────────────────────────────
   Wo ist Platz, wo ist es eng? CPV-Fachgebiete mit Nachfrage, Trend, Wettbewerbs-
   dichte und Einstiegshürden. Plus die aus `Chancen` übernommenen Blöcke. */
const FELD_SPALTEN: { key: string; label: string; wert: (f: Feld) => number }[] = [
  { key: "name", label: "Fachgebiet", wert: (f) => f.vergaben36 },
  { key: "jahr", label: "Vergaben/Jahr", wert: (f) => f.vergabenJahr },
  { key: "trend", label: "Trend 12M", wert: (f) => f.trend ?? -999 },
  { key: "bieter", label: "Ø Bieter", wert: (f) => f.bieterMedian ?? -1 },
  { key: "los", label: "kleinstes Los", wert: (f) => f.kleinstesLos ?? -1 },
  { key: "buerg", label: "Bürgschaft", wert: (f) => f.buergschaft?.pct ?? -1 },
];

function Felder({ data }: { data: Strat }) {
  const { t } = useSprache();
  const [sortKey, setSortKey] = useState("name");
  const [sortDir, setSortDir] = useState(-1);
  const felder = useMemo(() => {
    const sp = FELD_SPALTEN.find((c) => c.key === sortKey)!;
    return [...data.felder].sort((a, b) => (sp.wert(a) - sp.wert(b)) * sortDir);
  }, [data, sortKey, sortDir]);
  const pro = isPro(data);   // Härtung 4: Free sieht Feld-Identität, aber nicht die Zahlen

  function sortiere(k: string) {
    if (k === sortKey) setSortDir((d) => -d);
    else { setSortKey(k); setSortDir(-1); }
  }

  return (
    <>
      <div className="st-head"><div>
        <h4>{t("Felder")}</h4>
        <p className="st-frage">{t("Wo ist Platz, wo ist es eng?")}{pro ? "" : ` — ${t("Werte im Pro-Zugang")}`}</p>
      </div></div>

      <div className="st-table st-felder">
        <div className="st-row st-row-h">
          {FELD_SPALTEN.map((c) => (
            <span key={c.key} className="st-sortbar" onClick={() => sortiere(c.key)}
              data-sorted={sortKey === c.key ? "" : undefined}>
              {t(c.label)}
              <i className="st-arrow">{sortKey === c.key ? (sortDir < 0 ? "▼" : "▲") : "↕"}</i>
            </span>
          ))}
        </div>
        {felder.map((f) => (
          <div key={f.cpv4} className="st-row">
            <span className="st-t">{f.label}
              <span className="st-sub">{t("CPV {cpv} · {n} Vergaben in 36 Mon.", { cpv: f.cpv4, n: f.vergaben36.toLocaleString("de-DE") })}</span>
            </span>
            <span className="st-w">{pro ? <span className="v-num">{f.vergabenJahr}</span> : <Lock />}</span>
            <span className="st-w">
              {!pro ? <Lock />
                : f.trend == null
                ? <span className="v-sparse" title={t("Nicht über alle drei Zeitfenster durchgehend belegt")}>n/a</span>
                : <span className={`st-trend ${f.trend > 5 ? "up" : f.trend < -5 ? "down" : ""}`}>
                    {f.trend > 0 ? "+" : ""}{f.trend} %
                  </span>}
            </span>
            <span className="st-w">{!pro ? <Lock /> : f.bieterMedian != null ? <span className="v-num">{f.bieterMedian}</span> : <span style={{ color: "var(--ink-300)" }}>—</span>}</span>
            <span className="st-w">{!pro ? <Lock /> : f.kleinstesLos ? <span className="v-num">{eur(f.kleinstesLos)}</span> : <span style={{ color: "var(--ink-300)" }}>—</span>}</span>
            <span className="st-w">{pro ? <Q q={f.buergschaft} /> : <Lock />}</span>
          </div>
        ))}
      </div>

      <section className="bsec" style={{ marginTop: "var(--s5)" }}>
        <h4>{t("Benachbarte Felder")}</h4>
        <p className="st-frage" style={{ marginBottom: "var(--s3)" }}>
          {t("Bereiche, die dieselben Anbieter zusätzlich bedienen. Abgeleitet daraus, welche Felder gemeinsam abgedeckt werden.")}
        </p>
        <div className="st-table st-nachbarn">
          <div className="st-row st-row-h"><span>{t("Feld")}</span><span>{t("Nähe")}</span><span>{t("gemeinsame Anbieter")}</span></div>
          {data.nachbarn.map((n) => (
            <div key={n.cpv4} className="st-row">
              <span className="st-t">{n.label}<span className="st-sub">{t("CPV {cpv}", { cpv: n.cpv4 })}</span></span>
              <span className="st-w"><span className={`pr-tag ${n.naehe >= 40 ? "" : "mut"}`}>{n.naehe} %</span></span>
              <span className="st-w"><span className="v-num">{n.firmen.toLocaleString("de-DE")}</span></span>
            </div>
          ))}
        </div>
      </section>

      <section className="bsec" style={{ marginTop: "var(--s5)" }}>
        <h4>{t("Einstiegsfreundlich")}</h4>
        <p className="st-frage" style={{ marginBottom: "var(--s3)" }}>
          {t("Offene Ausschreibungen mit kleinem Volumen. Die Bieterzahl ist der historische Median des Fachgebiets, bei laufenden Verfahren hat noch niemand geboten.")}
        </p>
        <div className="st-table st-einstieg">
          <div className="st-row st-row-h"><span>{t("Ausschreibung")}</span><span>{t("Wert")}</span><span>{t("Bieter (Feld)")}</span><span>{t("Frist")}</span></div>
          {data.einstieg.map((e) => (
            <div key={e.id} className="st-row">
              <span className="st-t">{e.titel}<span className="st-sub">{e.buyer}</span></span>
              <span className="st-w"><span className="val" data-src={e.wertSrc}><span className="v-num">{e.wert}</span></span></span>
              <span className="st-w">{e.bieterFeld != null ? <span className="v-num">{e.bieterFeld}</span> : <span style={{ color: "var(--ink-300)" }}>—</span>}</span>
              <span className="st-w">{e.frist}</span>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

/* ── Bindung (Ticket §5.7) ─────────────────────────────────────────────────
   „Gesperrt" wird NUR behauptet, wo die Gelisteten-Liste vorliegt. Wo nur bekannt
   ist, dass es ein Rahmen ohne Wettbewerb ist, steht das ehrlich daneben. */
function Bindung({ data }: { data: Strat }) {
  const { t } = useSprache();
  const b = data.bindung;
  const anteilBelegt = b.rahmen ? Math.round((b.belegtGesperrt / b.rahmen) * 100) : 0;

  return (
    <>
      <div className="st-head"><div>
        <h4>{t("Bindung")}</h4>
        <p className="st-frage">{t("Was ist euch verschlossen?")}</p>
      </div></div>

      <div className="bhero bhero-risk">
        <div className="bhero-val">{b.volGesperrt ? eur(b.volGesperrt) : b.belegtGesperrt.toLocaleString("de-DE")}</div>
        <div className="bhero-lbl">
          <span className="bhero-title">
            {t("gebunden in")} <b>{b.belegtGesperrt.toLocaleString("de-DE")} {t("Rahmenvereinbarungen ohne erneuten Wettbewerb")}</b>
          </span>
          <span className="bhero-note">
            {t("Diese Aufträge laufen noch, werden aber nicht neu ausgeschrieben. Sie werden aus dem Rahmen abgerufen. Wer nicht gelistet ist, kann hier nicht anbieten, egal wie gut das Angebot wäre.")}
          </span>
        </div>
      </div>

      <div className="bstats" style={{ marginTop: "var(--s4)" }}>
        <div className="bstat">
          <span className="bstat-k">{t("Belegt gesperrt")}</span>
          <span className="bstat-v"><span className="v-num">{b.belegtGesperrt.toLocaleString("de-DE")}</span></span>
          <span className="bstat-m">{t("Gelistete namentlich bekannt ({pct} % der Rahmen)", { pct: anteilBelegt })}</span>
        </div>
        <div className="bstat">
          <span className="bstat-k">{t("Gelistete unbekannt")}</span>
          <span className="bstat-v"><span className="val" data-src="unsicher"><span className="v-num">{b.gelisteteUnbekannt.toLocaleString("de-DE")}</span></span></span>
          <span className="bstat-flag">{t("Rahmen ohne Wettbewerb, aber wir wissen nicht wer gelistet ist. Wir nehmen nicht an, dass ihr draußen seid.")}</span>
        </div>
        <div className="bstat">
          <span className="bstat-k">{t("Volumen belegt")}</span>
          <span className="bstat-v">{b.volGesperrt ? <span className="v-num">{eur(b.volGesperrt)}</span> : <span className="v-sparse">{t("kein Wert veröffentlicht")}</span>}</span>
          <span className="bstat-m">{b.volN ? t("aus {n} Rahmen mit Wertangabe", { n: b.volN }) : ""}</span>
        </div>
      </div>

      <section className="bsec" style={{ marginTop: "var(--s5)" }}>
        <h4>{t("Nächste Einstiegsfenster")}</h4>
        <p className="st-frage" style={{ marginBottom: "var(--s3)" }}>
          {t("Wann ihr euch bewegen müsst, um beim Auslaufen dabei zu sein. Vertragsende minus üblichem Vorlauf (Median Bekanntmachung→Zuschlag 87 Tage, plus Positionierung).")}
        </p>
        <div className="st-table st-fenster">
          <div className="st-row st-row-h">
            <span>{t("Rahmenvereinbarung")}</span><span>{t("Gelistet")}</span><span>{t("Wert")}</span>
            <span>{t("Läuft aus")}</span><span>{t("Fenster ab")}</span>
          </div>
          {b.fenster.map((f) => (
            <div key={f.id} className="st-row">
              <span className="st-t">
                {f.titel}
                <span className="st-sub">{f.buyer}{f.gelistete.length ? ` · ${f.gelistete.slice(0, 2).join(", ")}` : ""}</span>
              </span>
              <span className="st-w"><span className="v-num">{f.nGelistet}</span></span>
              <span className="st-w">{f.wert ? <span className="val" data-src={f.wertSrc}><span className="v-num">{f.wert}</span></span> : <span style={{ color: "var(--ink-300)" }}>—</span>}</span>
              <span className="st-w"><span className="val" data-src={f.endeSrc}>{f.ende}</span></span>
              <span className="st-w"><span className="st-fen">{f.fenster}</span></span>
            </div>
          ))}
        </div>
      </section>

      <section className="bsec" style={{ marginTop: "var(--s5)" }}>
        <h4>{t("Euer eigener Vertragsbestand")}</h4>
        <p className="st-frage" style={{ marginBottom: "var(--s3)" }}>
          {t("Eure laufenden (Rahmen-)Verträge binden beim Auslaufen wieder Kapazität und müssen verteidigt werden. Pflegt sie hier, „Als gewonnen markieren\" an einem Lead legt automatisch eine Zeile an.")}
        </p>
        <ContractsEditor />
      </section>
    </>
  );
}

/* ── Wettbewerb (Ticket §5.4) ──────────────────────────────────────────────
   Zwei Sichten auf dieselbe Kante. Ebene 1 Anbieter-Übersicht, Ebene 2 Profil.
   Keine Wertung im Text: „12 von 19 Vergaben, Marktdurchschnitt 14 %", nicht „starke
   Beziehung". Das Feld heißt Zuschlagsanteil, nicht Beziehung. */
const WETT_SPALTEN: { key: string; label: string; wert: (a: Anbieter) => number }[] = [
  { key: "name", label: "Anbieter", wert: (a) => a.wins },
  { key: "wins", label: "Zuschläge 36M", wert: (a) => a.wins },
  { key: "stellen", label: "Stellen", wert: (a) => a.stellen },
  { key: "trend", label: "Trend 12M", wert: (a) => a.trend ?? -999 },
  { key: "vol", label: "Volumen belegt", wert: (a) => a.vol ?? -1 },
];

function Wettbewerb({ data }: { data: Strat }) {
  const { t } = useSprache();
  const w = data.wettbewerb;
  const [sortKey, setSortKey] = useState("name");
  const [sortDir, setSortDir] = useState(-1);
  const [offen, setOffen] = useState<Anbieter | null>(null);

  const anbieter = useMemo(() => {
    const sp = WETT_SPALTEN.find((c) => c.key === sortKey)!;
    return [...w.anbieter].sort((a, b) => (sp.wert(a) - sp.wert(b)) * sortDir);
  }, [w, sortKey, sortDir]);
  const pro = isPro(data);
  const restAnbieter = (w._anbieterTotal ?? anbieter.length) - anbieter.length;   // im Pro verborgene Zeilen

  function sortiere(k: string) {
    if (k === sortKey) setSortDir((d) => -d);
    else { setSortKey(k); setSortDir(-1); }
  }

  const matrix = Array.isArray(w.matrix) ? null : w.matrix;

  if (offen) {
    const zeilen = w.profile[offen.id] || [];
    return (
      <>
        <button className="sec-link" onClick={() => setOffen(null)} style={{ marginBottom: "var(--s3)" }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5M11 18l-6-6 6-6" /></svg>
          {t("Alle Anbieter")}
        </button>
        <div className="st-head"><div><h4>{offen.name}</h4>
          <p className="st-frage">{t("{wins} Zuschläge bei {stellen} Vergabestellen (36 Mon.)", { wins: offen.wins, stellen: offen.stellen })}</p></div>
          {/* #25 Einstieg aus der Wettbewerbstabelle → volles Firmenprofil */}
          <a className="sec-link" href={`/firma?id=${encodeURIComponent(offen.id)}`}>{t("Firmenprofil ansehen ›")}</a>
        </div>

        <section className="bsec">
          <h4>{t("Zuschlagsanteil je Stelle")}</h4>
          <p className="st-frage" style={{ marginBottom: "var(--s3)" }}>
            {t("Wie groß der Anteil dieses Anbieters an den Zuschlägen der Stelle ist, gegen den Marktdurchschnitt (1 geteilt durch die Zahl aktiver Anbieter dort). Ein hoher Anteil kann Beziehung, fachliche Passung oder einen Rahmenvertrag bedeuten, die Deutung bleibt euch.")}
          </p>
          <div className="st-table st-profil">
            <div className="st-row st-row-h"><span>{t("Vergabestelle")}</span><span>{t("Zuschläge")}</span><span>{t("Anteil")}</span><span>{t("vs. Markt")}</span></div>
            {zeilen.length ? zeilen.map((z, i) => (
              <div key={i} className="st-row">
                <span className="st-t">{z.buyer}</span>
                <span className="st-w">{pro ? <span className="v-num">{z.wins}</span> : <Lock />}</span>
                <span className="st-w">
                  {pro ? <>
                    <span className="st-anteilbar"><i style={{ width: `${Math.min(100, z.anteil)}%` }} /></span>
                    <span className="v-num">{z.anteil} %</span>
                  </> : <Lock />}
                </span>
                <span className="st-w">
                  {pro ? <>
                    <span className="v-num" style={{ color: "var(--ink-400)" }}>{z.markt} %</span>
                    <span className={`st-ueber ${z.ueber > 0 ? "up" : ""}`}>{z.ueber > 0 ? "+" : ""}{z.ueber}</span>
                  </> : <Lock />}
                </span>
              </div>
            )) : <span className="v-sparse">{t("keine Stellen-Zuordnung erfasst")}</span>}
          </div>
        </section>
      </>
    );
  }

  return (
    <>
      <div className="st-head"><div>
        <h4>{t("Wettbewerb")}</h4>
        <p className="st-frage">{t("Wer holt was, wer hält was?")}</p>
      </div></div>

      <div className="st-table st-wett">
        <div className="st-row st-row-h">
          {WETT_SPALTEN.map((c) => (
            <span key={c.key} className="st-sortbar" onClick={() => sortiere(c.key)}
              data-sorted={sortKey === c.key ? "" : undefined}>
              {t(c.label)}<i className="st-arrow">{sortKey === c.key ? (sortDir < 0 ? "▼" : "▲") : "↕"}</i>
            </span>
          ))}
        </div>
        {anbieter.map((a) => (
          <div key={a.id} className="st-row st-clickable" onClick={() => setOffen(a)}>
            <span className="st-t">{a.name}</span>
            <span className="st-w"><span className="v-num">{a.wins}</span></span>
            <span className="st-w"><span className="v-num">{a.stellen}</span></span>
            <span className="st-w">
              {a.trend == null ? <span style={{ color: "var(--ink-300)" }}>—</span>
                : <span className={`st-trend ${a.trend > 5 ? "up" : a.trend < -5 ? "down" : ""}`}>{a.trend > 0 ? "+" : ""}{a.trend} %</span>}
            </span>
            <span className="st-w">{a.vol ? <span className="v-num">{eur(a.vol)}</span> : <span style={{ color: "var(--ink-300)" }}>—</span>}</span>
          </div>
        ))}
        {!pro && restAnbieter > 0 ? (
          <div className="st-row st-teaser">
            <span className="st-t">{t("+ {n} weitere Anbieter", { n: restAnbieter.toLocaleString("de-DE") })}</span>
            <span className="st-w st-teaser-pro" style={{ gridColumn: "2 / -1" }}>{t("vollständige Rangliste im Pro-Zugang")}</span>
          </div>
        ) : null}
      </div>

      {matrix ? (
        <section className="bsec" style={{ marginTop: "var(--s5)" }}>
          <h4>{t("Wer holt wo")}</h4>
          <p className="st-frage" style={{ marginBottom: "var(--s3)" }}>
            {t("Zuschlagsanteil je Stelle × Anbieter. Leere Zellen bei hohem Zeilenvolumen sind das Signal: dort dominiert niemand.")}
          </p>
          <div className="st-matrixwrap">
            <table className="st-matrix">
              <thead>
                <tr>
                  <th />
                  {matrix.supplier.map((s) => (
                    <th key={s.id} title={s.name}><span>{s.name}</span></th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrix.buyers.map((b, ri) => (
                  <tr key={b.id}>
                    <th title={b.name}>{b.name}</th>
                    {matrix.cells[ri].map((c, ci) => (
                      <td key={ci} title={`${c} %`}>
                        <span className="st-cell" style={{ opacity: c ? 0.15 + Math.min(0.85, c / 40) : 0 }} />
                        {c >= 8 ? <em>{c}</em> : null}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </>
  );
}

/* ── Fähigkeiten (Ticket §5.6) ─────────────────────────────────────────────
   Was blockiert uns? Eignungskriterien liegen überwiegend im Freitext (~37 %) —
   jede Aussage ist deshalb eine UNTERGRENZE, nie eine Vollzählung. */
const NACHWEIS_LABEL: Record<string, string> = {
  "sui-act": "Berufs-/Handelsregister-Eintrag", SUITABILITY: "Eignung (allgemein)",
  "ef-stand": "Wirtschaftliche Mindeststandards", "tp-abil": "Technische Leistungsfähigkeit",
  TECHNICAL_PROFESSIONAL_INFO: "Technische Angaben", ECONOMIC_FINANCIAL_INFO: "Wirtschaftliche Angaben",
  TECHNICAL_PROFESSIONAL_MIN_LEVEL: "Technisches Mindestniveau",
  ECONOMIC_FINANCIAL_MIN_LEVEL: "Wirtschaftliches Mindestniveau",
};

function Faehigkeiten({ data }: { data: Strat }) {
  const { t } = useSprache();
  const f = data.faehigkeiten;
  const b = f.buergschaft;
  const buergPct = b.n ? Math.round((b.treffer / b.n) * 100) : 0;

  return (
    <>
      <div className="st-head"><div>
        <h4>{t("Fähigkeiten")}</h4>
        <p className="st-frage">{t("Was blockiert uns?")}</p>
      </div></div>

      <div className="mnote" style={{ marginBottom: "var(--s4)" }}>
        {t("Eignungsanforderungen stehen überwiegend im Freitext der Vergabeunterlagen (rund ein Drittel maschinell erfasst). Jede Zahl hier ist deshalb eine")} <b>{t("Untergrenze")}</b> {t("„mindestens so viele\", nie „genau so viele\". Ob ihr die Anforderungen erfüllt, prüfen wir, sobald euer Firmenprofil steht.")}
      </div>

      <section className="bsec">
        <h4>{t("Formaler Rahmen")}</h4>
        <p className="st-frage" style={{ marginBottom: "var(--s3)" }}>
          {t("Nach welchem Vergaberecht ausgeschrieben wird. Bestimmt Nachweispflichten, Fristen und Präqualifikation.")}{" "}
          {t("{n} Ausschreibungen im Feld.", { n: f.nLeads.toLocaleString("de-DE") })}
        </p>
        <div className="st-table st-regime">
          <div className="st-row st-row-h"><span>{t("Regelwerk")}</span><span>{t("Ausschreibungen")}</span><span>{t("Volumen belegt")}</span></div>
          {f.regime.map((r) => (
            <div key={r.code} className="st-row">
              <span className="st-t">{r.label}</span>
              <span className="st-w"><span className="v-num">{t("mind. {n}", { n: r.n.toLocaleString("de-DE") })}</span></span>
              <span className="st-w">{r.vol ? <span className="v-num">{eur(r.vol)}</span> : <span style={{ color: "var(--ink-300)" }}>—</span>}</span>
            </div>
          ))}
        </div>
      </section>

      <div className="bhero bhero-mid" style={{ marginTop: "var(--s5)" }}>
        <div className="bhero-val" style={{ fontSize: 24 }}>{b.vol ? eur(b.vol) : `${b.treffer}`}</div>
        <div className="bhero-lbl">
          <span className="bhero-title">
            <b>{t("Mindestens {n}", { n: b.treffer })}</b> {t("Ausschreibungen fordern eine")} <b>{t("Bürgschaft")}</b>{b.n ? ` ${t("({pct} % der belegten)", { pct: buergPct })}` : ""}
          </span>
          <span className="bhero-note">
            {t("Kapitalhürde: wer keine Bürgschaft stellen kann, ist von diesem Volumen ausgeschlossen. Erfasst aus dem strukturierten Feld, die Dunkelziffer im Freitext liegt darüber.")}
          </span>
        </div>
      </div>

      <section className="bsec" style={{ marginTop: "var(--s5)" }}>
        <h4>{t("Geforderte Nachweise")}</h4>
        <p className="st-frage" style={{ marginBottom: "var(--s3)" }}>
          {t("Maschinell erfasste Eignungsnachweise im Feld. Dünn, das meiste steht im Freitext.")}
        </p>
        {f.nachweise.length ? (
          <div className="st-table st-nachweis">
            <div className="st-row st-row-h"><span>{t("Nachweis")}</span><span>{t("gefordert in")}</span></div>
            {f.nachweise.map((nw) => (
              <div key={nw.code} className="st-row">
                <span className="st-t">{t(NACHWEIS_LABEL[nw.code] || nw.code)}<span className="st-sub">{nw.code}</span></span>
                <span className="st-w"><span className="v-num">{t("mind. {n}", { n: nw.n })}</span></span>
              </div>
            ))}
          </div>
        ) : <span className="v-sparse">{t("keine typisierten Nachweise im Feld erfasst")}</span>}
      </section>
    </>
  );
}

function NochNicht({ label, frage }: { label: string; frage: string }) {
  const { t } = useSprache();
  return (
    <>
      <div className="st-head"><div><h4>{t(label)}</h4><p className="st-frage">{t(frage)}</p></div></div>
      <div className="mwarn">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
        </svg>
        <span><b>{t("Diese Sektion ist noch nicht gebaut.")}</b> {t("Sie braucht eigene Aggregate über Vergabestellen und Anbieter. Wir zeigen hier nichts Vorläufiges, lieber leer als falsch.")}</span>
      </div>
    </>
  );
}

export function StrategieView({
  aktiveBranche, potTab, profilStufe, offenerPicker, accountLimit, tick, onBodyAction,
  aktiveSektion,
}: {
  aktiveBranche: string; potTab: string; profilStufe: string; offenerPicker: string | null;
  /** Der gewaehlte Abschnitt — gefuehrt von der Shell, weil die Navigation in der
   *  Bereichsleiste steht und damit ausserhalb dieser Komponente. */
  aktiveSektion: string;
  accountLimit: boolean; tick: number;
  onBodyAction: (action: string, value: string, el: HTMLElement) => void;
}) {
  const { t } = useSprache();
  // Der Abschnitt wird von der Shell gefuehrt, weil die Navigation in der Bereichsleiste
  // steht — also AUSSERHALB dieser Komponente. Ihn hier zu halten und nach oben zu melden
  // waere zwei Quellen fuer denselben Wert.
  const sektion = aktiveSektion;
  const [strat, setStrat] = useState<Record<string, Strat> | null>(null);
  const [offeneStelle, setOffeneStelle] = useState<Stelle | null>(null);

  // Aggregate des EIGENEN Landes. Ohne `land` liefert die Route DE — was fuer einen
  // oesterreichischen Bieter deutsche Vergabestellen und deutsche Wettbewerbsdichte
  // waere, ausgegeben als seine.
  useEffect(() => {
    const land = nutzerLand();
    fetch(`/api/strategie?ctx=provider&land=${land}`)
      .then((r) => r.json()).then(setStrat).catch(() => {});
  }, []);

  // Position + Profil kommen unverändert aus dem Bestand (Ticket §5.5 / §5.8)
  const bestandHtml = useMemo(() => {
    if (sektion !== "position" && sektion !== "profil") return "";
    applyState({ potTab: sektion, profilStufe, offenerPicker, aktiveBranche, accountLimit });
    // Die Nachbarfelder liegen in denselben Aggregaten, die diese Ansicht ohnehin geladen
    // hat. Der Kern kennt sie nicht von sich aus, also reichen wir sie hier herein.
    setNachbarn(strat?.[aktiveBranche]?.nachbarn);
    return renderProfil();
  }, [sektion, profilStufe, offenerPicker, aktiveBranche, accountLimit, tick]);

  function handleClick(e: React.MouseEvent<HTMLDivElement>) {
    // NICHT `t` nennen — das würde die Übersetzungsfunktion oben beschatten.
    const ziel = e.target as HTMLElement;
    for (const a of ["editprofil", "partner", "angadd", "angset", "angrm", "editbestand", "pstufe", "openlead"]) {
      const el = ziel.closest<HTMLElement>(`[data-${a}]`);
      if (el) { onBodyAction(a, el.dataset[a] || "", el); return; }
    }
  }

  const data = strat?.[aktiveBranche];
  const meta = SEKTIONEN.flatMap((g) => g.items).find((i) => i.key === sektion)!;

  return (
    <div className="stwrap">
      {/* Die Abschnittsnavigation stand hier als zweite Spalte links — neben der Rail,
          also eine Leiste neben der Leiste, und in einer Bauform, die kein anderer Bereich
          benutzte. Sie liegt jetzt in der Bereichsleiste (s. ExplorerShell). */}

      <div className="stmain">
        {sektion === "pipeline"
          ? (data ? <Pipeline data={data} /> : <div className="st-head"><div><h4>{t("Pipeline")}</h4><p className="st-frage">{t("Lade Aggregate …")}</p></div></div>)
          : sektion === "stellen"
          ? (!data ? <div className="st-head"><div><h4>{t("Vergabestellen")}</h4><p className="st-frage">{t("Lade Aggregate …")}</p></div></div>
             : offeneStelle ? <StelleDetail s={offeneStelle} alle={data?.stellen ?? []} onBack={() => setOffeneStelle(null)} />
             : <Vergabestellen data={data} onOpenBuyer={setOffeneStelle} />)
          : sektion === "felder"
          ? (data ? <Felder data={data} /> : <div className="st-head"><div><h4>{t("Felder")}</h4><p className="st-frage">{t("Lade Aggregate …")}</p></div></div>)
          : sektion === "wettbewerb"
          ? (data ? <Wettbewerb data={data} /> : <div className="st-head"><div><h4>{t("Wettbewerb")}</h4><p className="st-frage">{t("Lade Aggregate …")}</p></div></div>)
          : sektion === "bindung"
          ? (!data ? <div className="st-head"><div><h4>{t("Bindung")}</h4><p className="st-frage">{t("Lade Aggregate …")}</p></div></div>
             : !isPro(data) ? <ProGate titel="Bindung" frage="Was ist euch verschlossen?" was="Gesperrtes Volumen, Gelisteten-Analyse und die nächsten Einstiegsfenster." />
             : <Bindung data={data} />)
          : sektion === "faehigkeiten"
          ? (!data ? <div className="st-head"><div><h4>{t("Fähigkeiten")}</h4><p className="st-frage">{t("Lade Aggregate …")}</p></div></div>
             : !isPro(data) ? <ProGate titel="Fähigkeiten" frage="Was blockiert uns?" was="Geforderte Nachweise, Bürgschafts-Hürde und der formale Rahmen im Feld." />
             : <Faehigkeiten data={data} />)
          : sektion === "region"
          ? <Regionen />
          : sektion === "trefferguete"
          ? <Trefferguete aktiveBranche={aktiveBranche} />
          : sektion === "position" || sektion === "profil"
          ? <div onClick={handleClick} dangerouslySetInnerHTML={{ __html: bestandHtml }} />
          : <NochNicht label={meta.label} frage={meta.frage} />}
      </div>
    </div>
  );
}
