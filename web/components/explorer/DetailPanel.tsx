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

/* Minimal-Form für das Leer-Briefing — nur die Felder, die es wirklich liest. */
type BriefLead = { id: string; [k: string]: unknown };

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
  rows = [], alle = [], onPickLead, onGoto,
  onTab, onClose, onExpand, onWf, onStar, onBodyAction,
}: {
  activeId: string | null;
  activeTab: string;
  mode: "browse" | "read" | "full";
  tick: number;
  buyerDemo: string;
  aktiveRegion: string;
  accountLimit: boolean;
  // aktuell gefilterte Liste — Grundlage des Leer-Briefings. Bewusst strukturell typisiert
  // (nicht der lokale Lead-Typ), damit die Shell ihre eigene Lead-Form durchreichen kann.
  rows?: BriefLead[];
  alle?: BriefLead[];
  onPickLead?: (id: string) => void;
  onGoto?: (ziel: "netzwerk" | "strategie" | "award" | "vorschau") => void;
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

  // Leerzustand = Tagesbriefing statt Platzhalter: was ist neu, was drängt, was lohnt sich.
  // Alle Zahlen aus der AKTUELL gefilterten Liste gerechnet — keine erfundenen Werte.
  if (!activeId) return <LeerBriefing rows={rows} alle={alle} onPick={onPickLead} onGoto={onGoto} />;

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
      "tonetz", "netz", "buyerleads", "partner", "netzfrei", "ptab", "pstufe", "uploaddocs", "saveblock",
      "clchk", "clkombi", "clcopy", "cljump", "clcollapse", "firma", "merk"];
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
          {/* #24 Zuschlag: reduzierte Tab-Leiste — nur die Übersicht (Zuschlag+Gewinner+Passung),
              die bieter-/käuferorientierten Tabs passen zur Zuschlagsphase nicht. */}
          {(l?.src === "award" ? ([{ key: "uebersicht", label: "Übersicht" }] as typeof TABS) : TABS).map((tb) => (
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

/* Leerzustand als Tagesbriefing (statt „Kein Lead ausgewählt"): rechnet aus der AKTUELL
 * gefilterten Liste, was drängt und was sich lohnt — jede Zahl gemessen, keine erfundenen Werte.
 * Klick auf eine Zeile öffnet den Lead direkt. */
function LeerBriefing({ rows, alle = [], onPick, onGoto }: {
  rows: BriefLead[]; alle?: BriefLead[];
  onPick?: (id: string) => void; onGoto?: (ziel: "netzwerk" | "strategie" | "award" | "vorschau") => void;
}) {
  /* Drei Spalten nach Zeithorizont, nicht nach Datenherkunft:
   *   jetzt   — worauf man sich diese Woche bewerben kann
   *   bald    — was sich anbahnt (Ankündigungen, auslaufende Verträge)
   *   drumrum — Markt und Netzwerk, also die Bausteine daneben
   * `rows` ist die vorsortierte Akquise-Liste; „bald" braucht bewusst `alle`, weil die
   * Vorauswahl nur bewerbbare Ausschreibungen (f02) durchlässt und Ankündigungen sonst
   * unsichtbar blieben. */
  const b = useMemo(() => {
    const tageOf = (l: BriefLead) => {
      const f = l.frist as { tage?: number } | undefined;
      return typeof f?.tage === "number" ? f.tage : (typeof l.tage === "number" ? (l.tage as number) : null);
    };
    const offen = rows.filter((l) => l.src !== "award");
    const heiss = offen
      .filter((l) => { const t = tageOf(l); return t != null && t >= 0 && t <= 21; })
      .sort((a, z) => (tageOf(a) ?? 99) - (tageOf(z) ?? 99));

    // Vorschau: Ankündigungen + auslaufende Verträge, nach Möglichkeit profilnah.
    const basis = alle.length ? alle : rows;
    const mitProfil = rows.some((l) => l.relevanz === "hoch" || l.relevanz === "mittel");
    const passend = (l: BriefLead) =>
      !mitProfil || l.relevanz === "hoch" || l.relevanz === "mittel";
    const kuenftig = basis
      // Bereits ausgelaufene Verträge sind keine Vorschau — sie standen hier ganz oben,
      // weil nach endTage aufsteigend sortiert wird und negative Werte zuerst kommen.
      .filter((l) => (l.src === "f01" || l.src === "auslauf") && passend(l)
        && ((l.endTage as number | null) ?? 0) >= 0)
      .sort((a, z) => ((a.endTage as number | null) ?? 9999) - ((z.endTage as number | null) ?? 9999));

    const netz = basis.filter((l) => ((l.lose as unknown[] | undefined)?.length ?? 0) > 1 && passend(l));
    const zuschlaege = basis.filter((l) => l.src === "award");
    // Namen statt nackter Zähler: „190 Vergaben" sagt nichts, „bei Stadt Halle und DB Netz"
    // sagt, wo man morgen anruft.
    const netzKaeufer = [...new Set(netz.map((l) => String(l.buyer || "")).filter(Boolean))].slice(0, 2);
    const gewinner = [...new Set(zuschlaege
      .map((l) => (l.award as { winner?: string } | undefined)?.winner)
      .filter(Boolean) as string[])].slice(0, 2);
    /* Vierte Spalte: was Ausschreibungen aus eurem Gewerk gerade AUFHÄLT.
     * Bewusst NICHT aus gap_effects (das braucht eine Sitzung mit erfassten Nachweisen und
     * wäre für die meisten leer), sondern aus den Blockern, die matchLead ohnehin je Lead
     * rechnet — verfügbar, sobald ein Profil da ist. Gezählt wird nur, was im richtigen
     * Gewerk liegt: eine Region-Lücke bei einem fremden Fachgebiet ist keine Lücke. */
    const imFeld = basis.filter((l) => {
      const t = (l.match as { teile?: { dim: string; status: string }[] } | undefined)?.teile;
      return t?.some((x) => x.dim === "feld" && x.status !== "no");
    });
    const blockerArt = (l: BriefLead, art: string) =>
      ((l.match as { blocker?: { art: string }[] } | undefined)?.blocker ?? []).some((x) => x.art === art);
    const teilStatus = (l: BriefLead, dim: string) =>
      ((l.match as { teile?: { dim: string; status: string }[] } | undefined)?.teile ?? [])
        .find((x) => x.dim === dim)?.status;

    const luecken = [
      { key: "buerg", n: imFeld.filter((l) => blockerArt(l, "buergschaft_offen")).length,
        titel: "Bürgschaftsrahmen fehlt",
        text: "fordern eine Bürgschaft. Ohne euren Rahmen können wir nicht sagen, ob ihr sie stemmt." },
      { key: "allein", n: imFeld.filter((l) => blockerArt(l, "partner")).length,
        titel: "Über eurer Alleingrenze",
        text: "sind größer, als ihr allein stemmt — mit Partner wären sie erreichbar." },
      { key: "region", n: imFeld.filter((l) => teilStatus(l, "region") === "no").length,
        titel: "Außerhalb eurer Regionen",
        text: "passen fachlich, liegen aber außerhalb. Arbeitet ihr dort doch?" },
      { key: "vol", n: imFeld.filter((l) => teilStatus(l, "vol") === "no").length,
        titel: "Außerhalb eurer Wertspanne",
        text: "liegen über oder unter der Spanne, die ihr angegeben habt." },
    ].filter((x) => x.n > 0).sort((a, z) => z.n - a.n);

    return { offen, heiss, kuenftig, netz, zuschlaege, netzKaeufer, gewinner, luecken, imFeld, tageOf };
  }, [rows, alle]);

  const Zeile = ({ l, sub }: { l: BriefLead; sub: string }) => (
    <button className="lb-row" onClick={() => onPick?.(l.id)} title="Lead öffnen">
      <span className="lb-row-t">{String(l.titel || "").slice(0, 58)}</span>
      <span className="lb-row-s">{sub}</span>
    </button>
  );

  const monate = (l: BriefLead) => {
    const d = l.endTage as number | null;
    if (d == null) return "Zeitpunkt offen";
    if (d < 0) return "bereits ausgelaufen";
    if (d < 31) return "im nächsten Monat";
    return `in ~${Math.round(d / 30)} Monaten`;
  };

  return (
    <div className="lb">
      <div className="lb-head">
        <p className="lb-h">Euer Überblick</p>
        <p className="lb-l">Wählt links eine Ausschreibung — oder steigt hier ein.</p>
      </div>

      <div className="lb-drei">
        {/* ── jetzt ─────────────────────────────────────────────── */}
        <section className="lb-sp">
          <h4><span className="lb-dot heiss" />Jetzt bewerben</h4>
          <p className="lb-n2">{b.heiss.length}<em>mit Frist in den nächsten 3 Wochen</em></p>
          {b.heiss.length ? b.heiss.slice(0, 5).map((l) => {
            const t = b.tageOf(l);
            return <Zeile key={l.id} l={l}
              sub={t === 0 ? "läuft heute ab" : t === 1 ? "läuft morgen ab" : `noch ${t} Tage`} />;
          }) : <p className="lb-nix">Gerade nichts Dringendes — gut so.</p>}
        </section>

        {/* ── bald ──────────────────────────────────────────────── */}
        <section className="lb-sp">
          <h4><span className="lb-dot bald" />Bahnt sich an</h4>
          <p className="lb-n2">{b.kuenftig.length}<em>Ankündigungen und auslaufende Verträge</em></p>
          {b.kuenftig.length ? b.kuenftig.slice(0, 5).map((l) => (
            <Zeile key={l.id} l={l} sub={monate(l)} />
          )) : <p className="lb-nix">Noch keine Vorankündigungen in eurem Feld.</p>}
          {b.kuenftig.length > 5 ? (
            <button className="lb-mehr" onClick={() => onGoto?.("vorschau")}>Alle {b.kuenftig.length} ansehen</button>
          ) : null}
        </section>

        {/* ── was im Weg steht ──────────────────────────────────── */}
        <section className="lb-sp">
          <h4><span className="lb-dot luecke" />Was euch bremst</h4>
          {b.luecken.length ? (<>
            <p className="lb-n2">{b.luecken[0].n}<em>{b.luecken[0].titel.toLowerCase()}</em></p>
            {b.luecken.slice(0, 3).map((g) => (
              <a key={g.key} className="lb-kachel" href="/unternehmen">
                <b>{g.n}</b>
                <span><i>{g.titel}</i> — {g.text}</span>
              </a>
            ))}
          </>) : (
            <p className="lb-nix">{b.imFeld.length
              ? "Nichts blockiert euch gerade — euer Profil ist vollständig genug."
              : "Legt unter „Unternehmen“ euer Profil an, dann zeigen wir hier, was euch Aufträge kostet."}</p>
          )}
        </section>

        {/* ── drumrum ───────────────────────────────────────────── */}
        <section className="lb-sp">
          <h4><span className="lb-dot markt" />Markt &amp; Netzwerk</h4>
          <button className="lb-kachel" onClick={() => onGoto?.("netzwerk")}>
            <b>{b.netz.length}</b>
            <span>{b.netzKaeufer.length
              ? <>Mehrlos-Vergaben, u.a. bei <i>{b.netzKaeufer.join(" und ")}</i> — hier lohnt ein Partner</>
              : "Vergaben mit mehreren Losen — hier lohnt ein Partner"}</span>
          </button>
          <button className="lb-kachel" onClick={() => onGoto?.("award")}>
            <b>{b.zuschlaege.length}</b>
            <span>{b.gewinner.length
              ? <>frische Zuschläge, u.a. an <i>{b.gewinner.join(" und ")}</i> — wer gewonnen hat, kauft jetzt ein</>
              : "frische Zuschläge — wer gewonnen hat, kauft jetzt ein"}</span>
          </button>
          <button className="lb-kachel" onClick={() => onGoto?.("strategie")}>
            <b>→</b>
            <span>Strategie: wohin sich euer Markt bewegt</span>
          </button>
        </section>
      </div>

      <p className="lb-foot">Zahlen beziehen sich auf eure aktuell gefilterte Liste.</p>
    </div>
  );
}
