"use client";
import { useEffect, useMemo, useState } from "react";
import { useSprache } from "@/lib/i18n";

/* Regionalansicht — Sektion „Region" in der Gruppe Markt.
 *
 * Sie beantwortet eine Frage, die keine andere Sektion beantwortet: WO lohnt sich der
 * Aufwand geografisch? Pipeline und Felder sagen was, Vergabestellen sagt bei wem — die
 * Region sagt wo, und zwar zusammen mit dem, was ausserhalb unserer Daten über diese
 * Region bekannt ist (Baugenehmigungen als Vorlauf, Investitionen und Schulden als
 * Finanzkraft, Baubetriebe als Angebotsseite).
 *
 * ⚠ ZWEI DINGE, DIE MAN HIER FALSCH LESEN KANN, und deshalb beide beschriftet sind:
 *
 * 1. Die Nachfragezahlen zählen ALLE Vergaben der Region, nicht nur euer Fachgebiet.
 *    `region_kpi` aggregiert über den Leistungsort, ohne CPV-Schnitt. Wer „312 offene"
 *    als „312 für uns" liest, plant falsch.
 * 2. `jeBetrieb` ist Struktur, kein Chancensignal. Die naheliegende These „wenig Betriebe
 *    → wenig Wettbewerb → gute Chance" wurde gemessen und WIDERLEGT: Single-Bieter-Quote
 *    je Dichte-Quartil 21/21/19/22 %, Korrelation 0,099 (n=322). Baufirmen sind mobil.
 *
 * Der Median jeder Kontextgrösse steht daneben, weil eine nackte Zahl („418
 * Baugenehmigungen") ohne Vergleich keine Aussage ist — und weil die grossen Städte
 * Ausreisser sind, an denen man sich sonst automatisch orientiert.
 */

type Region = {
  id: string; name: string; land: string;
  offen: number | null; vergeben: number | null; stellen: number | null;
  volumen: number | null; volumenDeckung: number | null; singleBieter: number | null;
  genehmigungen: number | null; investitionen: number | null; investitionKopf: number | null;
  schuldenKopf: number | null; einwohner: number | null; baubetriebe: number | null;
  bauBeschaeftigte: number | null; je1000: number | null; jeBetrieb: number | null;
  intensitaet: number | null;
};
type Daten = { stand: string; kontextJahr: number; median: Record<string, number | null>; regionen: Region[] };

const nf = (v: number | null | undefined, k = 0) =>
  v == null ? "—" : v.toLocaleString("de-DE", { minimumFractionDigits: k, maximumFractionDigits: k });
const eur = (v: number | null | undefined) =>
  v == null ? "—"
    : v >= 1e9 ? (v / 1e9).toFixed(2).replace(".", ",") + " Mrd €"
    : v >= 1e6 ? (v / 1e6).toFixed(1).replace(".", ",") + " Mio €"
    : Math.round(v).toLocaleString("de-DE") + " €";

/* Spalten der Übersicht. Bewusst sieben und nicht sechzehn: die Tabelle soll den Einstieg
   ordnen, nicht das Dossier ersetzen. Alles Weitere steht im Detail. */
const SPALTEN: { key: keyof Region | "name"; label: string; wert: (r: Region) => number }[] = [
  { key: "name", label: "Region", wert: (r) => r.offen ?? 0 },
  { key: "offen", label: "offen", wert: (r) => r.offen ?? -1 },
  { key: "vergeben", label: "vergeben", wert: (r) => r.vergeben ?? -1 },
  { key: "stellen", label: "Stellen", wert: (r) => r.stellen ?? -1 },
  { key: "singleBieter", label: "1 Bieter", wert: (r) => r.singleBieter ?? -1 },
  { key: "je1000", label: "je 1.000 EW", wert: (r) => r.je1000 ?? -1 },
  { key: "genehmigungen", label: "Genehmig.", wert: (r) => r.genehmigungen ?? -1 },
];

/** Kennzahl mit ihrem Vergleichswert. Ohne Median wäre jede Zeile eine Zahl ohne Massstab. */
function Kennzahl({ label, wert, median, einheit = "", hinweis }: {
  label: string; wert: string; median?: string | null; einheit?: string;
  /* Schon uebersetzt, wenn er ankommt. Ein Hinweis, der eine Zahl traegt, muss an der
     Aufrufstelle durch `t()` mit Platzhalter laufen; hier nochmal `t(hinweis)` zu rufen
     hiesse, den fertigen Satz als Katalogschluessel zu suchen, und der steht dort nie. */
  hinweis?: React.ReactNode;
}) {
  const { t } = useSprache();
  return (
    <div className="bstat">
      <span className="bstat-k">{t(label)}</span>
      <span className="bstat-v"><span className="v-num">{wert}</span>{einheit ? ` ${einheit}` : ""}</span>
      {median ? <span className="bstat-m">{t("Median der Kreise: {v}", { v: median })}</span> : null}
      {hinweis ? <span className="bstat-m">{hinweis}</span> : null}
    </div>
  );
}

function Detail({ r, d, onBack }: { r: Region; d: Daten; onBack: () => void }) {
  const { t } = useSprache();
  const m = d.median;
  // Ohne Einwohnerzahl gibt es für diese Region gar keinen Destatis-Treffer. Das ist keine
  // Panne, sondern die dokumentierte Lücke bei gleichnamigen Kreisen (München Stadt vs.
  // Landkreis): dort wird bewusst NICHTS zugeordnet, statt das Falsche zuzuordnen.
  const ohneKontext = r.einwohner == null;
  return (
    <>
      <button className="sec-link" onClick={onBack} style={{ marginBottom: "var(--s3)" }}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5M11 18l-6-6 6-6" /></svg>
        {t("Alle Regionen")}
      </button>
      <div className="st-head">
        <div>
          <h4>{r.name}</h4>
          <p className="st-frage">{r.land} · {r.id}</p>
        </div>
      </div>

      <div className="bstats">
        <Kennzahl label="Offene Ausschreibungen" wert={nf(r.offen)} />
        <Kennzahl label="Vergeben (Bestand)" wert={nf(r.vergeben)} />
        <Kennzahl label="Vergabestellen" wert={nf(r.stellen)} />
        <Kennzahl label="Volumen belegt" wert={eur(r.volumen)}
          hinweis={r.volumenDeckung != null
            ? t("Untergrenze: nur {p} % der Vergaben tragen einen Wert", { p: nf(r.volumenDeckung) })
            : undefined} />
        <Kennzahl label="Nur ein Bieter" wert={r.singleBieter == null ? "—" : `${nf(r.singleBieter)} %`}
          median={m.singleBieter != null ? `${nf(m.singleBieter)} %` : null} />
        <Kennzahl label="Vergaben je 1.000 Einwohner" wert={nf(r.je1000, 2)}
          median={m.je1000 != null ? nf(m.je1000, 2) : null} />
      </div>

      <p className="st-frage" style={{ marginTop: "var(--s4)" }}>
        {t("Was ausserhalb unserer Daten über die Region bekannt ist. Alle Werte Stand {jahr}.", { jahr: d.kontextJahr })}
      </p>

      {ohneKontext ? (
        <p className="st-hinweis">
          {t("Für diese Region ordnen wir keinen Regionalkontext zu. Der Kreisname kommt in der amtlichen Statistik mehrfach vor, Stadt und Landkreis gleichen Namens. Eine Zuordnung wäre geraten, und lieber nichts als das Falsche.")}
        </p>
      ) : (
        <div className="bstats">
          <Kennzahl label="Baugenehmigungen" wert={nf(r.genehmigungen)}
            median={m.genehmigungen != null ? nf(m.genehmigungen) : null}
            hinweis={t("Vorlaufindikator: Genehmigungen laufen Bau-Ausschreibungen voraus.")} />
          <Kennzahl label="Investitionen des Kreises" wert={eur(r.investitionen)}
            hinweis={t("Haushalt des ganzen Kreises, nicht Budget einer einzelnen Stelle.")} />
          <Kennzahl label="Investition je Kopf" wert={r.investitionKopf == null ? "—" : eur(r.investitionKopf)}
            median={m.investitionKopf != null ? eur(m.investitionKopf) : null} />
          <Kennzahl label="Schulden je Kopf" wert={r.schuldenKopf == null ? "—" : eur(r.schuldenKopf)}
            median={m.schuldenKopf != null ? eur(m.schuldenKopf) : null}
            hinweis={t("Hohe Schulden je Kopf drücken die Investitionsfähigkeit.")} />
          <Kennzahl label="Baubetriebe" wert={nf(r.baubetriebe)}
            median={m.baubetriebe != null ? nf(m.baubetriebe) : null}
            hinweis={t("Struktur der Region, kein Chancensignal: die Dichte erklärt die Single-Bieter-Quote messbar nicht (Korrelation 0,10).")} />
          <Kennzahl label="Einwohner" wert={nf(r.einwohner)} />
        </div>
      )}

      {r.intensitaet != null ? (
        <p className="st-hinweis">
          {t("Sichtbares Auftragsvolumen entspricht {p} % des Investitionsbudgets. Als Signal lesen, nicht als Quote: rund 2 % sind der Normalfall, weil der grösste Teil kommunaler Investitionen nie als Ausschreibung sichtbar wird. Über 100 % heisst, dass in dieser Region Bundes- und Konzernkäufer dominieren, deren Aufträge nicht aus dem Kommunalhaushalt stammen.", { p: nf(r.intensitaet, 1) })}
        </p>
      ) : null}
    </>
  );
}

export function Regionen() {
  const { t } = useSprache();
  const [d, setD] = useState<Daten | null>(null);
  const [fehler, setFehler] = useState(false);
  const [suche, setSuche] = useState("");
  const [land, setLand] = useState("");
  const [offen, setOffen] = useState<Region | null>(null);
  const [sortKey, setSortKey] = useState<string>("offen");
  const [sortDir, setSortDir] = useState(-1);

  useEffect(() => {
    fetch("/api/regionen")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("nicht verfügbar"))))
      .then(setD).catch(() => setFehler(true));
  }, []);

  const laender = useMemo(
    () => [...new Set((d?.regionen ?? []).map((r) => r.land))].sort((a, b) => a.localeCompare(b, "de")),
    [d]);

  const liste = useMemo(() => {
    if (!d) return [];
    const s = suche.trim().toLowerCase();
    const sp = SPALTEN.find((c) => c.key === sortKey) ?? SPALTEN[1];
    return d.regionen
      .filter((r) => (!land || r.land === land)
                  && (!s || r.name.toLowerCase().includes(s) || r.id.toLowerCase().includes(s)))
      .sort((a, b) => (sp.wert(a) - sp.wert(b)) * sortDir);
  }, [d, suche, land, sortKey, sortDir]);

  function sortiere(k: string) {
    if (k === sortKey) setSortDir((x) => -x);
    else { setSortKey(k); setSortDir(-1); }
  }

  if (fehler) return (
    <div className="st-head"><div><h4>{t("Region")}</h4>
      <p className="st-frage">{t("Die Regionsdaten sind gerade nicht verfügbar.")}</p></div></div>);
  if (!d) return (
    <div className="st-head"><div><h4>{t("Region")}</h4>
      <p className="st-frage">{t("Lade Aggregate …")}</p></div></div>);
  if (offen) return <Detail r={offen} d={d} onBack={() => setOffen(null)} />;

  return (
    <>
      <div className="st-head">
        <div>
          <h4>{t("Region")}</h4>
          <p className="st-frage">{t("Wo steht der Markt geografisch, und wie steht die Region da?")}</p>
        </div>
      </div>

      {/* Ohne diesen Satz liest jemand „312 offene" als „312 für uns". Die Zahlen zählen
          alle Vergaben am Leistungsort, ohne Schnitt auf das eigene Fachgebiet. */}
      <p className="st-hinweis">
        {t("Gezählt wird am Leistungsort und über alle Fachgebiete, nicht nur über eures. {n} Regionen, davon {k} mit amtlichem Regionalkontext (Stand {jahr}).", { n: nf(d.regionen.length), k: nf(d.regionen.filter((r) => r.einwohner != null).length), jahr: d.kontextJahr })}
      </p>

      <div className="reg-filter">
        <input className="reg-suche" type="search" value={suche} placeholder={t("Kreis oder Stadt suchen")}
          onChange={(e) => setSuche(e.target.value)} aria-label={t("Kreis oder Stadt suchen")} />
        <select className="reg-land" value={land} onChange={(e) => setLand(e.target.value)}
          aria-label={t("Bundesland")}>
          <option value="">{t("alle Bundesländer")}</option>
          {laender.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
        <span className="reg-zahl">{t("{n} Regionen", { n: nf(liste.length) })}</span>
      </div>

      <div className="st-table st-regionen">
        <div className="st-row st-row-h">
          {SPALTEN.map((c) => (
            <span key={String(c.key)} className="st-sortbar" onClick={() => sortiere(String(c.key))}
              data-sorted={sortKey === c.key ? "" : undefined}>
              {t(c.label)}
              <i className="st-arrow">{sortKey === c.key ? (sortDir < 0 ? "▼" : "▲") : "↕"}</i>
            </span>
          ))}
        </div>
        {liste.map((r) => (
          <div key={r.id} className="st-row st-clickable" onClick={() => setOffen(r)}>
            <span className="st-t">{r.name}<span className="st-sub">{r.land}</span></span>
            <span className="st-w"><span className="v-num">{nf(r.offen)}</span></span>
            <span className="st-w"><span className="v-num">{nf(r.vergeben)}</span></span>
            <span className="st-w"><span className="v-num">{nf(r.stellen)}</span></span>
            <span className="st-w">{r.singleBieter == null
              ? <span style={{ color: "var(--ink-300)" }}>—</span>
              : <span className="v-num">{nf(r.singleBieter)} %</span>}</span>
            <span className="st-w">{r.je1000 == null
              ? <span style={{ color: "var(--ink-300)" }}>—</span>
              : <span className="v-num">{nf(r.je1000, 2)}</span>}</span>
            <span className="st-w">{r.genehmigungen == null
              ? <span style={{ color: "var(--ink-300)" }} title={t("kein amtlicher Kontext zugeordnet")}>—</span>
              : <span className="v-num">{nf(r.genehmigungen)}</span>}</span>
          </div>
        ))}
      </div>
    </>
  );
}
