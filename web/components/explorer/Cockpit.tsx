"use client";
import { useMemo, useState } from "react";
import { useSprache } from "@/lib/i18n";

/* Cockpit (Ticket #17) — Merkliste + Pipeline + Historie in einer Ansicht.
 * Drei zusammenklappbare Bereiche von Zukunft (beobachtet) über Gegenwart (aktiv)
 * zu Vergangenheit (Historie). Bereich 3 ist VORBEFÜLLT aus den öffentlichen Zuschlägen
 * der eigenen Firma (l.eigen) — der Kaltstart-Löser für die Ergebnisdaten (#11).
 * Kein CRM: verwaltet den Status der Ausschreibung, nicht die Vertriebsbeziehung. */

type Lead = {
  id: string; titel?: string; buyer?: string; buyerShort?: string; merk?: unknown;
  frist?: { date?: string | null; tage?: number | null } | null;
  pipe?: string | null; outcome?: string | null;
  eigen?: boolean; eigenBestaetigt?: boolean | null; incumbent?: { seit?: string } | null;
  cockpitProv?: "abgeleitet" | "bestaetigt" | "korrigiert";
  endTage?: number | null; endet?: string | null; src?: string;
};

const PIPE_LABEL: Record<string, string> = {
  beworben: "Beworben", abgegeben: "Abgegeben", wartet: "Wartet auf Entscheidung",
};
const PIPE_NEXT: Record<string, string> = { beworben: "abgegeben", abgegeben: "wartet" };

function Prov({ state }: { state?: string }) {
  const { t } = useSprache();
  if (!state) return null;
  const m: Record<string, [string, string]> = {
    abgeleitet: ["ck-prov-abl", "abgeleitet"],
    bestaetigt: ["ck-prov-best", "bestätigt"],
    korrigiert: ["ck-prov-korr", "ergänzt"],
  };
  const [cls, lbl] = m[state] || ["", state];
  return <span className={`ck-prov ${cls}`} title={
    state === "abgeleitet" ? t("Aus öffentlichen Daten abgeleitet, bitte prüfen")
    : state === "bestaetigt" ? t("Von Ihnen bestätigt") : t("Von Ihnen ergänzt/korrigiert")}>{t(lbl)}</span>;
}

/* Gruende, warum ein beobachteter Vorgang doch nicht beboten wurde. ⚠ Es sind die Werte aus
 * `DismissReason` (lib/supabase/outcomes.ts), nicht neu erfundene: die Spalte gibt es, die
 * Tabelle nimmt genau diese entgegen, und ein siebter Grund hier waere ein Wert, den niemand
 * auswerten kann. Das Uebergabepapier nennt vier; die Tabelle kann sechs, also fragen wir sechs. */
const GRUENDE: [string, string][] = [
  ["cpv_mismatch", "passte fachlich nicht"], ["region", "zu weit weg"],
  ["too_small", "zu klein"], ["too_big", "zu groß"],
  ["no_capacity", "keine Kapazität"], ["other", "anderer Grund"],
];

export function Cockpit({
  rows, onSelect, onApply, onStatus, onOutcome, onConfirm, onMitgeboten, verwaist = [],
}: {
  rows: Lead[];
  /* Gemerkte Vorgänge, die aus dem Export gefallen sind — die Frist ist durch. Sie tragen
     nur Titel und Käufer, mehr steht in der Merkliste nicht. Genau für sie ist die Frage
     nach dem Ergebnis da. */
  verwaist?: { lead_id: string; titel: string | null; buyer_name: string | null }[];
  onSelect: (id: string) => void;
  onApply: (id: string) => void;
  onStatus: (id: string, s: string) => void;
  onOutcome: (id: string, o: "gewonnen" | "verloren") => void;
  onConfirm: (id: string) => void;
  onMitgeboten?: (id: string, mitgeboten: boolean, grund?: string) => void;
}) {
  const { t } = useSprache();
  const [open, setOpen] = useState({ beob: true, aktiv: true, hist: false });
  // Welcher Vorgang wartet gerade auf den Grund? Genau einer, nie mehrere.
  const [grundFuer, setGrundFuer] = useState<string | null>(null);

  const { beob, aktiv, hist } = useMemo(() => {
    const beob: Lead[] = [], aktiv: Lead[] = [], hist: Lead[] = [];
    for (const l of rows) {
      if (l.outcome) hist.push(l);
      else if (l.pipe) aktiv.push(l);
      else if (l.merk) beob.push(l);
      else if (l.eigen && l.eigenBestaetigt !== false) hist.push(l); // vorbefüllt aus öffentl. Zuschlägen
    }
    beob.sort((a, b) => (a.frist?.tage ?? 9999) - (b.frist?.tage ?? 9999));
    return { beob, aktiv, hist };
  }, [rows]);

  const abgeleitet = hist.filter((l) => !l.outcome && l.cockpitProv !== "bestaetigt" && l.cockpitProv !== "korrigiert").length;

  const Area = ({ k, title, unter, n, children }: { k: "beob" | "aktiv" | "hist"; title: string; unter: string; n: number; children: React.ReactNode }) => (
    <section className="ck-area">
      <button className="ck-head" onClick={() => setOpen((o) => ({ ...o, [k]: !o[k] }))} aria-expanded={open[k]}>
        <span className={`ck-caret ${open[k] ? "open" : ""}`}>▸</span>
        <span className="ck-head-t">{title}</span>
        <span className="ck-head-u">{unter}</span>
        <span className="ck-head-n">{n}</span>
      </button>
      {open[k] && <div className="ck-body">{children}</div>}
    </section>
  );

  const Row = ({ l, children }: { l: Lead; children?: React.ReactNode }) => (
    <div className="ck-row">
      <button className="ck-row-main" onClick={() => onSelect(l.id)}>
        <span className="ck-row-t">{l.titel || t("(ohne Titel)")}</span>
        <span className="ck-row-b">{l.buyerShort || l.buyer || ""}</span>
      </button>
      <div className="ck-row-act">{children}</div>
    </div>
  );

  return (
    <div className="ck-wrap">
      <Area k="beob" title={t("Beobachtet")} unter={t("Zukunft, was ich angehen will")} n={beob.length}>
        {/* ⚠ ZUERST DIE ABGELAUFENEN. Sie sind das Einzige in dieser Liste, wo eine Antwort
            verlorengeht, wenn man sie übersieht: der Vorgang ist vorbei, die Frage nach dem
            Ergebnis stellt sich genau einmal. Alles andere kann warten. */}
        {verwaist.map((v) => (
          <div className="ck-row" key={v.lead_id}>
            <button className="ck-row-main" onClick={() => onSelect(v.lead_id)}>
              <span className="ck-row-t">{v.titel || t("(ohne Titel)")}</span>
              <span className="ck-row-b">{v.buyer_name || ""}</span>
            </button>
            <div className="ck-row-act">
              <span className="ck-frist risk">{t("abgelaufen")}</span>
              {grundFuer === v.lead_id ? (
                <span className="ck-gruende">
                  <em>{t("Woran lag es?")}</em>
                  {GRUENDE.map(([k, lbl]) => (
                    <button key={k} className="ck-btn ghost"
                            onClick={() => { onMitgeboten?.(v.lead_id, false, k); setGrundFuer(null); }}>
                      {t(lbl)}
                    </button>
                  ))}
                </span>
              ) : (
                <span className="ck-frage">
                  <em>{t("Habt ihr mitgeboten?")}</em>
                  <button className="ck-btn" onClick={() => onMitgeboten?.(v.lead_id, true)}>{t("Ja")}</button>
                  <button className="ck-btn ghost" onClick={() => setGrundFuer(v.lead_id)}>{t("Nein")}</button>
                </span>
              )}
            </div>
          </div>
        ))}
        {beob.length ? beob.map((l) => (
          <Row key={l.id} l={l}>
            {l.frist?.tage != null && (
              <span className={`ck-frist ${l.frist.tage < 3 ? "risk" : l.frist.tage <= 14 ? "flag" : ""}`}>
                {l.frist.tage < 0 ? t("abgelaufen") : t("noch {n} T", { n: l.frist.tage })}</span>
            )}
            {/* ⚠ IST DIE FRIST DURCH, IST „Ich bewerbe mich" FALSCH. Bis zum 2026-09-01 stand
                der Knopf auch an abgelaufenen Vorgaengen und fuehrte ins Leere. Genau dieser
                Moment ist die wertvollste Frage, die wir stellen koennen: die Bieterzahl steht
                in keiner Bekanntmachung, sie entsteht nur, wenn jemand sie uns sagt.
                Ein Klick, kein Formular. Der Grund kommt erst NACH einem „nein", und nur dann. */}
            {/* ⚠ HIER KEIN „abgelaufen"-Zweig. `frist.tage` wird im Frontend nie negativ
                (gemessen 2026-09-01: Minimum 0) — abgelaufene Vorgänge fallen aus dem Export
                und stehen oben unter `verwaist`. Eine Bedingung auf „< 0" wäre toter Code,
                der aussieht wie eine Funktion. */}
            <button className="ck-btn" onClick={() => onApply(l.id)}>{t("Ich bewerbe mich →")}</button>
          </Row>
        )) : <div className="ck-empty">{t("Noch nichts beobachtet. Merkt euch Ausschreibungen (☆) in der Akquise.")}</div>}
      </Area>

      <Area k="aktiv" title={t("Aktiv")} unter={t("Gegenwart, woran ich gerade dran bin")} n={aktiv.length}>
        {aktiv.length ? aktiv.map((l) => (
          <Row key={l.id} l={l}>
            <span className={`ck-status ${l.pipe === "wartet" ? "wait" : ""}`}>{t(PIPE_LABEL[l.pipe!] || l.pipe!)}</span>
            {PIPE_NEXT[l.pipe!] && <button className="ck-btn ghost" onClick={() => onStatus(l.id, PIPE_NEXT[l.pipe!])} title={t("Status weiterschalten")}>{t(PIPE_LABEL[PIPE_NEXT[l.pipe!]])} →</button>}
            <button className="ck-btn win" onClick={() => onOutcome(l.id, "gewonnen")}>{t("Gewonnen")}</button>
            <button className="ck-btn lose" onClick={() => onOutcome(l.id, "verloren")}>{t("Verloren")}</button>
          </Row>
        )) : <div className="ck-empty">{t("Keine laufenden Bewerbungen. Aus „Beobachtet\" wandert ein Lead hierher, sobald Sie sich bewerben.")}</div>}
      </Area>

      <Area k="hist" title={t("Historie")} unter={t("Vergangenheit. Was war, und was daraus folgt")} n={hist.length}>
        {(() => {
          // Ableitungen (#17 §5): Stammkunden + bald auslaufende Verträge (Verteidigungsbedarf).
          const kunden = new Set(hist.filter((l) => l.outcome !== "verloren").map((l) => l.buyerShort || l.buyer)).size;
          const baldAus = hist.filter((l) => l.endTage != null && l.endTage >= 0 && l.endTage <= 540).length;
          if (!kunden) return null;
          return (
            <div className="ck-abl">
              <span className="ck-abl-i"><b>{kunden}</b> {t("Stammkunden")}</span>
              {baldAus > 0 && <span className="ck-abl-i warn"><b>{baldAus}</b> {baldAus > 1 ? t("Verträge laufen") : t("Vertrag läuft")} {t("bald aus. Verteidigungsbedarf")}</span>}
            </div>
          );
        })()}
        {abgeleitet > 0 && (
          <div className="ck-note">
            <b>{t("{n} Verträge aus öffentlichen Daten vorbefüllt.", { n: abgeleitet })}</b>{" "}
            {t("Das sind eure öffentlich sichtbaren (oberschwelligen) Zuschläge. Unterschwelliges und Niederlagen fehlen. Bestätigen oder ergänzen Sie, um das Bild zu vervollständigen (und goVisor etwas beizubringen, das es nicht wusste).")}
          </div>
        )}
        {hist.length ? hist.map((l) => (
          <Row key={l.id} l={l}>
            {l.outcome ? <span className={`ck-out ${l.outcome === "gewonnen" ? "win" : "lose"}`}>{l.outcome === "gewonnen" ? t("gewonnen") : t("verloren")}</span>
              : <><Prov state={l.cockpitProv || "abgeleitet"} />
                  {(l.cockpitProv ?? "abgeleitet") === "abgeleitet" && <button className="ck-btn ghost" onClick={() => onConfirm(l.id)}>{t("Stimmt ✓")}</button>}</>}
            {l.incumbent?.seit && <span className="ck-since">{t("seit {jahr}", { jahr: l.incumbent.seit })}</span>}
            {l.endTage != null && l.endTage >= 0 && l.endTage <= 540 && l.endet &&
              <span className="ck-since warn" title={t("Euer Vertrag läuft bald aus. Hier droht Verdrängung, Verteidigung nötig")}>{t("läuft {datum} aus", { datum: l.endet })}</span>}
          </Row>
        )) : <div className="ck-empty">{t("Keine Historie. Eure öffentlichen Zuschläge erscheinen hier automatisch, sobald euer Firmenprofil bestätigt ist.")}</div>}
      </Area>

      <p className="ck-foot">{t("goVisor verwaltet den")} <b>{t("Status der Ausschreibung")}</b>{t(", nicht die Vertriebsbeziehung, kein CRM.")}</p>
    </div>
  );
}
