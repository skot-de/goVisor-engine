"use client";
import { useMemo, useState } from "react";

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
  if (!state) return null;
  const m: Record<string, [string, string]> = {
    abgeleitet: ["ck-prov-abl", "abgeleitet"],
    bestaetigt: ["ck-prov-best", "bestätigt"],
    korrigiert: ["ck-prov-korr", "ergänzt"],
  };
  const [cls, lbl] = m[state] || ["", state];
  return <span className={`ck-prov ${cls}`} title={
    state === "abgeleitet" ? "Aus öffentlichen Daten abgeleitet — bitte prüfen"
    : state === "bestaetigt" ? "Von Ihnen bestätigt" : "Von Ihnen ergänzt/korrigiert"}>{lbl}</span>;
}

export function Cockpit({
  rows, onSelect, onApply, onStatus, onOutcome, onConfirm,
}: {
  rows: Lead[];
  onSelect: (id: string) => void;
  onApply: (id: string) => void;
  onStatus: (id: string, s: string) => void;
  onOutcome: (id: string, o: "gewonnen" | "verloren") => void;
  onConfirm: (id: string) => void;
}) {
  const [open, setOpen] = useState({ beob: true, aktiv: true, hist: false });

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
        <span className="ck-row-t">{l.titel || "(ohne Titel)"}</span>
        <span className="ck-row-b">{l.buyerShort || l.buyer || ""}</span>
      </button>
      <div className="ck-row-act">{children}</div>
    </div>
  );

  return (
    <div className="ck-wrap">
      <Area k="beob" title="Beobachtet" unter="Zukunft — was ich angehen will" n={beob.length}>
        {beob.length ? beob.map((l) => (
          <Row key={l.id} l={l}>
            {l.frist?.tage != null && (
              <span className={`ck-frist ${l.frist.tage < 3 ? "risk" : l.frist.tage <= 14 ? "flag" : ""}`}>
                {l.frist.tage < 0 ? "abgelaufen" : `noch ${l.frist.tage} T`}</span>
            )}
            <button className="ck-btn" onClick={() => onApply(l.id)}>Ich bewerbe mich →</button>
          </Row>
        )) : <div className="ck-empty">Noch nichts beobachtet. Merken Sie sich Ausschreibungen (☆) in der Akquise.</div>}
      </Area>

      <Area k="aktiv" title="Aktiv" unter="Gegenwart — woran ich gerade dran bin" n={aktiv.length}>
        {aktiv.length ? aktiv.map((l) => (
          <Row key={l.id} l={l}>
            <span className={`ck-status ${l.pipe === "wartet" ? "wait" : ""}`}>{PIPE_LABEL[l.pipe!] || l.pipe}</span>
            {PIPE_NEXT[l.pipe!] && <button className="ck-btn ghost" onClick={() => onStatus(l.id, PIPE_NEXT[l.pipe!])} title="Status weiterschalten">{PIPE_LABEL[PIPE_NEXT[l.pipe!]]} →</button>}
            <button className="ck-btn win" onClick={() => onOutcome(l.id, "gewonnen")}>Gewonnen</button>
            <button className="ck-btn lose" onClick={() => onOutcome(l.id, "verloren")}>Verloren</button>
          </Row>
        )) : <div className="ck-empty">Keine laufenden Bewerbungen. Aus „Beobachtet" wandert ein Lead hierher, sobald Sie sich bewerben.</div>}
      </Area>

      <Area k="hist" title="Historie" unter="Vergangenheit — was war, und was daraus folgt" n={hist.length}>
        {(() => {
          // Ableitungen (#17 §5): Stammkunden + bald auslaufende Verträge (Verteidigungsbedarf).
          const kunden = new Set(hist.filter((l) => l.outcome !== "verloren").map((l) => l.buyerShort || l.buyer)).size;
          const baldAus = hist.filter((l) => l.endTage != null && l.endTage >= 0 && l.endTage <= 540).length;
          if (!kunden) return null;
          return (
            <div className="ck-abl">
              <span className="ck-abl-i"><b>{kunden}</b> Stammkunden</span>
              {baldAus > 0 && <span className="ck-abl-i warn"><b>{baldAus}</b> {baldAus > 1 ? "Verträge laufen" : "Vertrag läuft"} bald aus — Verteidigungsbedarf</span>}
            </div>
          );
        })()}
        {abgeleitet > 0 && (
          <div className="ck-note">
            <b>{abgeleitet} Verträge aus öffentlichen Daten vorbefüllt.</b> Das sind Ihre öffentlich sichtbaren
            (oberschwelligen) Zuschläge — Unterschwelliges und Niederlagen fehlen. Bestätigen oder ergänzen Sie,
            um das Bild zu vervollständigen (und goVisor etwas beizubringen, das es nicht wusste).
          </div>
        )}
        {hist.length ? hist.map((l) => (
          <Row key={l.id} l={l}>
            {l.outcome ? <span className={`ck-out ${l.outcome === "gewonnen" ? "win" : "lose"}`}>{l.outcome === "gewonnen" ? "gewonnen" : "verloren"}</span>
              : <><Prov state={l.cockpitProv || "abgeleitet"} />
                  {(l.cockpitProv ?? "abgeleitet") === "abgeleitet" && <button className="ck-btn ghost" onClick={() => onConfirm(l.id)}>Stimmt ✓</button>}</>}
            {l.incumbent?.seit && <span className="ck-since">seit {l.incumbent.seit}</span>}
            {l.endTage != null && l.endTage >= 0 && l.endTage <= 540 && l.endet &&
              <span className="ck-since warn" title="Ihr Vertrag läuft bald aus — hier droht Verdrängung, Verteidigung nötig">läuft {l.endet} aus</span>}
          </Row>
        )) : <div className="ck-empty">Keine Historie. Ihre öffentlichen Zuschläge erscheinen hier automatisch, sobald Ihr Firmenprofil bestätigt ist.</div>}
      </Area>

      <p className="ck-foot">goVisor verwaltet den <b>Status der Ausschreibung</b>, nicht die Vertriebsbeziehung — kein CRM.</p>
    </div>
  );
}
