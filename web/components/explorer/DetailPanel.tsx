"use client";

import { useMemo, useState } from "react";
import {
  LEADS, WF, STAR, applyState,
  renderUebersicht, renderTeilnahme, renderAnalyse, renderMarkt, renderBuyer,
  renderTeam, renderGate, renderDocs,
} from "@/lib/explorerCore";
import { downloadDoc, downloadMarkdown, copyMarkdown } from "@/lib/dossier";
import { track, EV } from "@/lib/analytics";
import { markWonFromLead, loadContracts } from "@/lib/supabase/contracts";
import { setUserContracts } from "@/lib/explorerCore";

type Lead = {
  id: string; src: string; phaseLabel: string; cpvLabel: string; titel: string;
  status?: string; userStatus?: string; merk?: unknown; comments?: unknown[];
  aktualitaet?: { art: string; text: string; am: string } | null;
  [k: string]: unknown;
};

const TABS: { key: string; label: string; pro?: boolean }[] = [
  { key: "uebersicht", label: "Übersicht" },
  { key: "teilnahme", label: "Teilnahme" },
  { key: "docs", label: "Unterlagen" },
  { key: "analyse", label: "Bewertung" },
  { key: "buyer", label: "Vergabestelle", pro: true },
  { key: "markt", label: "Markt", pro: true },
  { key: "team", label: "Team" },
];

const ExpandIcon = (full: boolean) =>
  full
    ? "M9 3H5a2 2 0 0 0-2 2v4M15 3h4a2 2 0 0 1 2 2v4M9 21H5a2 2 0 0 1-2-2v-4M15 21h4a2 2 0 0 0 2-2v-4"
    : "M3 9V5a2 2 0 0 1 2-2h4M21 9V5a2 2 0 0 0-2-2h-4M3 15v4a2 2 0 0 0 2 2h4M21 15v4a2 2 0 0 1-2 2h-4";

export function DetailPanel({
  activeId, activeTab, mode, tick, buyerDemo, aktiveRegion, accountLimit,
  onTab, onClose, onExpand, onWf, onStar, onBodyAction,
}: {
  activeId: string | null;
  activeTab: string;
  mode: "browse" | "read" | "full";
  tick: number;
  buyerDemo: string;
  aktiveRegion: string;
  accountLimit: boolean;
  onTab: (k: string) => void;
  onClose: () => void;
  onExpand: () => void;
  onWf: (k: string) => void;
  onStar: (id: string) => void;
  onBodyAction: (action: string, value: string, el: HTMLElement) => void;
}) {
  const wf = WF as Record<string, { label: string; cls: string }>;

  const bodyHtml = useMemo(() => {
    if (!activeId) return "";
    applyState({ activeId, activeTab, accountLimit, buyerDemo, aktiveRegion });
    const l = (LEADS as Lead[]).find((x) => x.id === activeId);
    if (!l) return "";
    switch (activeTab) {
      case "teilnahme": return renderTeilnahme(l);
      case "docs": return renderDocs(l);
      case "analyse": return accountLimit ? renderGate() : renderAnalyse(l);
      case "buyer": return renderBuyer(l);
      case "markt": return renderMarkt(l);
      case "team": return renderTeam(l);
      default: return renderUebersicht(l);
    }
    // tick erzwingt Neuberechnung nach In-Place-Mutationen (Status, Kommentar, …)
  }, [activeId, activeTab, tick, buyerDemo, aktiveRegion, accountLimit]);

  const [briefOpen, setBriefOpen] = useState(false);   // Hooks vor jedem Early-Return
  const [copied, setCopied] = useState(false);
  const [wonState, setWonState] = useState<"idle" | "saving" | "done" | "guest">("idle");

  // Leerzustand: der „Brief" oben zeigt das neue Volumen — kommt später aus echten Daten.
  if (!activeId) {
    return (
      <div className="brief">
        <div className="btxt">
          <p className="bh">Kein Lead ausgewählt</p>
          <p className="bl">Wähle links einen Lead, um Übersicht, Teilnahme und Bewertung zu sehen.</p>
        </div>
      </div>
    );
  }

  const l = (LEADS as Lead[]).find((x) => x.id === activeId)!;
  const analysed = l.status === "analysiert";
  const isFree = accountLimit;

  // Delegierte Interaktion im Tab-Körper (Anker, Kommentar, Region, Käufer-Demo, …)
  function handleBody(e: React.MouseEvent<HTMLDivElement>) {
    const t = e.target as HTMLElement;
    // In-Body-Tabwechsel (z. B. „Käufer-Dossier ansehen" → Vergabestelle-Tab) direkt an onTab.
    const tabEl = t.closest<HTMLElement>("[data-tab]");
    if (tabEl) { onTab(tabEl.dataset.tab || ""); return; }
    const map = ["anav", "openlead", "cmtsend", "grp", "mark", "region", "buyerdemo",
      "tonetz", "netz", "buyerleads", "partner", "netzfrei", "ptab", "pstufe", "uploaddocs"];
    for (const a of map) {
      const el = t.closest<HTMLElement>(`[data-${a}]`);
      if (el) { onBodyAction(a, el.dataset[a] || "", el); return; }
    }
  }

  return (
    <>
      <div className="dhead">
        <div className="dtop">
          <div className="eyebrow">
            <span className={`srcpill big src-${l.src}`}>{l.phaseLabel}</span>
            <span className="eb-sep">·</span>
            <span>{l.cpvLabel}</span>
            {analysed ? <span className="seen-mark">analysiert</span> : null}
          </div>
          <div className="dactions">
            {isFree ? (
              <>
                <span className="danalysemeter">
                  <span className="dam-lbl">Bewertungen</span>
                  <span className="dam-val">1/3</span>
                </span>
                <span className="dactsep" />
              </>
            ) : null}
            <button className={`dbtn dbtn-won ${wonState === "done" ? "on" : ""}`}
              title={wonState === "done" ? "Als Vertrag hinterlegt — im Strategie-Tab pflegbar" : "Als gewonnen markieren (legt einen Vertrag an)"}
              onClick={async () => {
                if (wonState === "done") return;
                setWonState("saving");
                const r = await markWonFromLead(l);
                setWonState(r.ok ? "done" : "guest");
                if (r.ok) { track("lead_marked_won", { lead_id: l.id }); loadContracts().then(setUserContracts).catch(() => {}); }
                if (!r.ok) setTimeout(() => setWonState("idle"), 2500);
              }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6M18 9h1.5a2.5 2.5 0 0 0 0-5H18M6 4h12v5a6 6 0 0 1-12 0zM8 21h8M12 15v6" />
              </svg>
              {wonState === "done" ? <span className="dbtn-wontxt">Vertrag angelegt</span>
                : wonState === "guest" ? <span className="dbtn-wontxt">Bitte anmelden</span> : null}
            </button>
            <div className="dbrief-wrap">
              <button className="dbtn" title="Briefing erstellen" onClick={() => setBriefOpen((o) => !o)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M8 13h8M8 17h5" />
                </svg>
              </button>
              {briefOpen ? (
                <div className="dbrief-menu">
                  <div className="dbrief-h">Briefing zu diesem Lead</div>
                  <button className="dbrief-opt" onClick={() => { track(EV.BRIEFING, { format: "doc", lead_id: l.id }); downloadDoc(l); setBriefOpen(false); }}>
                    <b>Word</b><span>.doc · öffnet in Word, bearbeitbar</span></button>
                  <button className="dbrief-opt" onClick={() => { track(EV.BRIEFING, { format: "md", lead_id: l.id }); downloadMarkdown(l); setBriefOpen(false); }}>
                    <b>Markdown</b><span>.md · Datei</span></button>
                  <button className="dbrief-opt" onClick={async () => { setCopied(await copyMarkdown(l)); setTimeout(() => setCopied(false), 1500); }}>
                    <b>{copied ? "Kopiert ✓" : "Markdown kopieren"}</b><span>in die Zwischenablage</span></button>
                </div>
              ) : null}
            </div>
            <button
              className="dbtn dbtn-star"
              title="Merken"
              aria-label="Merken"
              data-merk={l.merk ? String(l.merk) : undefined}
              onClick={() => onStar(l.id)}
              dangerouslySetInnerHTML={{ __html: STAR }}
            />
            <button className="dbtn" title={mode === "full" ? "Verkleinern" : "Vollbild"} onClick={onExpand}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d={ExpandIcon(mode === "full")} />
              </svg>
            </button>
            <button className="dbtn" title="Schließen" onClick={onClose}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </div>
        </div>

        {l.aktualitaet ? (
          <div className={`aktbar akt-${l.aktualitaet.art}`}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
            </svg>
            <span>
              <b>{l.aktualitaet.art === "aufgehoben" ? "Verfahren aufgehoben" : "Nach Veröffentlichung geändert"}</b>{" "}
              {l.aktualitaet.text} · Stand {l.aktualitaet.am}
            </span>
          </div>
        ) : null}

        <div className="dtitle">
          <h2>{l.titel}</h2>
          <div className="wfpick">
            {Object.entries(wf).map(([k, v]) => (
              <button key={k} className={`wf ${v.cls} ${l.userStatus === k ? "on" : ""}`} onClick={() => onWf(k)}>
                {v.label}
              </button>
            ))}
          </div>
        </div>

        <div className="tabs" role="tablist">
          {TABS.map((tb) => (
            <button
              key={tb.key}
              className="tab"
              role="tab"
              aria-selected={activeTab === tb.key}
              onClick={() => onTab(tb.key)}
            >
              {tb.label}
              {tb.key === "analyse" && isFree ? <span className="quota">1/3</span> : null}
              {tb.key === "team" && l.comments?.length ? <span className="quota">{l.comments.length}</span> : null}
              {tb.pro && isFree ? <span className="probadge probadge-lock" title="Im Pro-Zugang">Pro</span> : null}
            </button>
          ))}
        </div>
      </div>

      <div onClick={handleBody} dangerouslySetInnerHTML={{ __html: bodyHtml }} />
    </>
  );
}
