"use client";

import { useEffect, useMemo, useState } from "react";
import { Hinweise } from "./Hinweise";
import { Dokumente } from "./Dokumente";
import {
  LEADS, WF, STAR, BRANCHEN, applyState,
  renderUebersicht, renderTeilnahme, renderAnalyse, renderMarkt, renderBuyer,
  renderTeam, renderGate, renderDocs,
  cpvLabel,
} from "@/lib/explorerCore";
import { downloadDoc, downloadMarkdown, copyMarkdown } from "@/lib/dossier";
import { track, EV } from "@/lib/analytics";
import { markWonFromLead, loadContracts } from "@/lib/supabase/contracts";
import { setUserContracts } from "@/lib/explorerCore";
import { angabenStand } from "@/lib/profileEngine";
import { sprachName, useSprache } from "@/lib/i18n";

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

/* Verweis auf die Vorgangsakte — Ausschreibung, Korrekturen, Unterlagen und Zuschlag unter
 * einer Nummer (scripts/export_vorgaenge.py, /api/vorgang).
 *
 * ⚠ NUR ANZEIGEN, WENN ES SIE WIRKLICH GIBT. Aufbereitet sind rund 36.000 Vorgaenge, nicht
 * alle 1,47 Mio. Ein Verweis, der auf „keine Akte hinterlegt" fuehrt, ist schlechter als
 * gar keiner. Deshalb antwortet die Route mit 200 und `vorhanden: false`, statt mit 404:
 * ein Lead ohne Akte ist hier der Normalfall und keine Stoerung.
 *
 * Ein Abruf je Lead, ~200 Byte. Das Nachschlagewerk dahinter (3,6 MB) bleibt auf dem
 * Server; es in den Browser zu laden, um EINE Zeile zu entscheiden, waere teurer als
 * jeder einzelne dieser Abrufe. */
function VorgangHinweis({ leadId }: { leadId: string }) {
  const { t } = useSprache();
  const [vorgang, setVorgang] = useState<string | null>(null);
  useEffect(() => {
    let abgemeldet = false;
    setVorgang(null);
    fetch(`/api/vorgang?lead=${encodeURIComponent(leadId)}`)
      .then((r) => r.json())
      .then((d) => { if (!abgemeldet && d?.vorhanden && d.akte?.id) setVorgang(d.akte.id); })
      .catch(() => {});
    return () => { abgemeldet = true; };
  }, [leadId]);
  if (!vorgang) return null;
  return (
    <>
      <span className="eb-sep">·</span>
      <a className="eb-vorgang" href={`/vorgang?lead=${encodeURIComponent(leadId)}`}>
        {t("Vorgang ansehen")}
      </a>
    </>
  );
}

export function DetailPanel({
  activeId, activeTab, mode, tick, buyerDemo, aktiveRegion, accountLimit,
  rows = [], alle = [], profil = null, fremderLead = null, onPickLead, onGoto,
  onTab, onClose, onExpand, onWf, onStar, onBodyAction, onDropDocs,
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
  // Das echte Profil aus dem Onboarding. Wird nur gezaehlt, nicht gelesen: der Ueberblick
  // sagt, WIE VIELE Angaben stehen, und nie, welche.
  profil?: unknown;
  // Kennung, die geoeffnet werden SOLLTE, im geladenen Grundraum aber nicht liegt (Deep-Link
  // aus einer anderen Branche, Verlaufszeile einer Vergabestelle). Die Shell entscheidet das
  // vor dem Oeffnen und laedt den richtigen Grundraum nach; hier wird nur angezeigt, woran
  // es gerade ist. `unbekannt` ist der einzige Endzustand — die anderen beiden gehen vorbei.
  fremderLead?: { id: string; stand: "sucht" | "wechselt" | "unbekannt"; branche?: string } | null;
  onPickLead?: (id: string) => void;
  onGoto?: (ziel: "netzwerk" | "strategie" | "award" | "vorschau" | "jetzt" | "trefferguete") => void;
  onTab: (k: string) => void;
  onClose: () => void;
  onExpand: () => void;
  onWf: (k: string) => void;
  onStar: (id: string) => void;
  onBodyAction: (action: string, value: string, el: HTMLElement) => void;
  /** Dateien, die ins Drop-Feld gezogen wurden. */
  onDropDocs?: (id: string, files: FileList, el: HTMLElement) => void;
}) {
  const wf = WF as Record<string, { label: string; cls: string }>;
  const { t, lang } = useSprache();
  // Gewaehlte Dokumentsprache. `null` = Originalfassung, also das, was `titel` traegt.
  // Beim Leadwechsel zuruecksetzen: die Wahl gilt fuer DIESE Ausschreibung, nicht global.
  const [docLang, setDocLang] = useState<string | null>(null);
  useEffect(() => { setDocLang(null); }, [activeId]);

  const bodyHtml = useMemo(() => {
    if (!activeId) return "";
    applyState({ activeId, activeTab, accountLimit, buyerDemo, aktiveRegion });
    const echt = (LEADS as Lead[]).find((x) => x.id === activeId);
    if (!echt) return "";
    // Die gewaehlte Dokumentsprache muss auch den KOERPER erreichen, nicht nur die
    // Ueberschrift: die Leistungsbeschreibung ist der eigentliche Inhalt. Die Renderer
    // stammen aus dem Prototyp und lesen `l.beschreibung` direkt — statt sie alle
    // sprachbewusst zu machen, bekommen sie eine Kopie mit der gewaehlten Fassung.
    // Kopie, nicht Mutation: `LEADS` bleibt die Originalfassung, sonst waere die Wahl
    // nach dem ersten Umschalten nicht mehr ruecknehmbar.
    const f = docLang
      ? (echt as { sprachfassungen?: Record<string, { title?: string; description?: string }> })
          .sprachfassungen?.[docLang]
      : undefined;
    const l = f ? { ...echt, titel: f.title || echt.titel, beschreibung: f.description || echt.beschreibung } : echt;
    switch (activeTab) {
      case "teilnahme": return renderTeilnahme(l);
      case "docs": return renderDocs(l);
      case "analyse": return accountLimit ? renderGate() : renderAnalyse(l);
      case "buyer": return renderBuyer(l);
      case "markt": return renderMarkt(l);
      case "team": return renderTeam(l);
      default: return renderUebersicht(l);
    }
    // tick erzwingt Neuberechnung nach In-Place-Mutationen (Status, Kommentar, …).
    // `lang` MUSS mit in die Abhaengigkeiten: die Prototyp-Renderer holen die Sprache
    // ueber `tk()` aus dem Modul-Zustand, davon weiss React nichts. Ohne die Zeile
    // wechselt die Oberflaeche die Sprache und der Detail-Koerper bleibt deutsch stehen —
    // genau so gesehen, bevor es hier stand.
  }, [activeId, activeTab, tick, buyerDemo, aktiveRegion, accountLimit, docLang, lang]);

  const [briefOpen, setBriefOpen] = useState(false);   // Hooks vor jedem Early-Return
  const [copied, setCopied] = useState(false);
  const [wonState, setWonState] = useState<"idle" | "saving" | "done" | "guest">("idle");

  // Leerzustand = Tagesbriefing statt Platzhalter: was ist neu, was drängt, was lohnt sich.
  // Alle Zahlen aus der AKTUELL gefilterten Liste gerechnet — keine erfundenen Werte.
  if (!activeId) {
    return fremderLead
      ? <FremderGrundraum lead={fremderLead} onClose={onClose} />
      : <LeerBriefing rows={rows} alle={alle} profil={profil} onPick={onPickLead} onGoto={onGoto} />;
  }

  /* ⚠ Hier stand `…find(…)!`. Das Ausrufezeichen war eine Behauptung, keine Prüfung: es
     versprach dem Compiler, dass zu JEDER `activeId` ein Lead in `LEADS` liegt. Das gilt
     nicht — `LEADS` trägt nur den GELADENEN Grundraum, und geöffnet wurde auch aus dem
     Käufer-Verlauf und per `?lead=`-Deep-Link, beides branchenübergreifend. Der Absturz
     fiel erst zwei Zeilen später bei `.sprachen` auf; die Ursache ist diese Zeile und der
     Aufrufer, der eine unbekannte Kennung überhaupt gesetzt hat (siehe `openLead`).
     Der Zweig hier bleibt als Netz für den Fall, dass `LEADS` unter einem offenen Lead
     ausgetauscht wird (Grundraumwechsel), bevor React die neue `activeId` sieht. */
  const l = (LEADS as Lead[]).find((x) => x.id === activeId);
  if (!l) return <FremderGrundraum lead={{ id: activeId, stand: "unbekannt" }} onClose={onClose} />;
  // Sprachfassungen kommen aus dem Detail-JSON (per Object.assign an den Lead gehaengt).
  // Fehlen sie, bleibt alles beim einsprachigen Verhalten — kein Sonderfall im Markup.
  const sprachen: string[] = Array.isArray((l as { sprachen?: string[] }).sprachen)
    ? (l as { sprachen?: string[] }).sprachen! : [];
  const fassungen = (l as { sprachfassungen?: Record<string, { title?: string; description?: string }> })
    .sprachfassungen ?? {};
  const titelAnzeige = (docLang && fassungen[docLang]?.title) || l.titel;
  const analysed = l.status === "analysiert";
  const isFree = accountLimit;

  // Delegierte Interaktion im Tab-Körper (Anker, Kommentar, Region, Käufer-Demo, …)
  function handleBody(e: React.MouseEvent<HTMLDivElement>) {
    const t = e.target as HTMLElement;
    // In-Body-Tabwechsel (z. B. „Käufer-Dossier ansehen" → Vergabestelle-Tab) direkt an onTab.
    const tabEl = t.closest<HTMLElement>("[data-tab]");
    if (tabEl) { onTab(tabEl.dataset.tab || ""); return; }
    const map = ["anav", "openlead", "cmtsend", "grp", "mark", "region", "buyerdemo",
      "tonetz", "netz", "buyerleads", "partner", "netzint", "netzlos", "netzfrei", "ptab", "pstufe",
      "uploaddocs", "saveblock",
      "clchk", "clopen", "grundauf", "clkombi", "clnutzen", "clpick", "clcopy", "cljump", "clcollapse",
      "firma", "merk",
      "buyerwatch"];
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
            {/* amtliche CPV-Bezeichnung in der Oberflaechensprache — nicht `l.cpvLabel` direkt */}
            <span>{cpvLabel(l)}</span>
            {analysed ? <span className="seen-mark">{t("analysiert")}</span> : null}
            <VorgangHinweis leadId={l.id} />
          </div>
          <div className="dactions">
            {isFree ? (
              <>
                <span className="danalysemeter">
                  <span className="dam-lbl">{t("Bewertungen")}</span>
                  <span className="dam-val">1/3</span>
                </span>
                <span className="dactsep" />
              </>
            ) : null}
            <button className={`dbtn dbtn-won ${wonState === "done" ? "on" : ""}`}
              title={t(wonState === "done" ? "Als Vertrag hinterlegt, im Strategie-Tab pflegbar" : "Als gewonnen markieren (legt einen Vertrag an)")}
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
              {wonState === "done" ? <span className="dbtn-wontxt">{t("Vertrag angelegt")}</span>
                : wonState === "guest" ? <span className="dbtn-wontxt">{t("Bitte anmelden")}</span> : null}
            </button>
            <div className="dbrief-wrap">
              <button className="dbtn" title={t("Briefing erstellen")} onClick={() => setBriefOpen((o) => !o)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M8 13h8M8 17h5" />
                </svg>
              </button>
              {briefOpen ? (
                <div className="dbrief-menu">
                  <div className="dbrief-h">{t("Briefing zu diesem Lead")}</div>
                  <button className="dbrief-opt" onClick={() => { track(EV.BRIEFING, { format: "doc", lead_id: l.id }); downloadDoc(l); setBriefOpen(false); }}>
                    <b>Word</b><span>{t(".doc · öffnet in Word, bearbeitbar")}</span></button>
                  <button className="dbrief-opt" onClick={() => { track(EV.BRIEFING, { format: "md", lead_id: l.id }); downloadMarkdown(l); setBriefOpen(false); }}>
                    <b>Markdown</b><span>{t(".md · Datei")}</span></button>
                  <button className="dbrief-opt" onClick={async () => { setCopied(await copyMarkdown(l)); setTimeout(() => setCopied(false), 1500); }}>
                    <b>{t(copied ? "Kopiert ✓" : "Markdown kopieren")}</b><span>{t("in die Zwischenablage")}</span></button>
                </div>
              ) : null}
            </div>
            <button
              className="dbtn dbtn-star"
              title={t("Merken")}
              aria-label={t("Merken")}
              data-merk={l.merk ? String(l.merk) : undefined}
              onClick={() => onStar(l.id)}
              dangerouslySetInnerHTML={{ __html: STAR }}
            />
            <button className="dbtn" title={t(mode === "full" ? "Verkleinern" : "Vollbild")} onClick={onExpand}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d={ExpandIcon(mode === "full")} />
              </svg>
            </button>
            <button className="dbtn" title={t("Schließen")} onClick={onClose}>
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
              <b>{t(l.aktualitaet.art === "aufgehoben" ? "Verfahren aufgehoben" : "Nach Veröffentlichung geändert")}</b>{" "}
              {l.aktualitaet.text} · {t("Stand")} {l.aktualitaet.am}
            </span>
          </div>
        ) : null}

        {/* Dokumentsprache — nur wo es wirklich eine Wahl gibt. Getrennt von der
            Oberflaechensprache: hier geht es um den INHALT der Ausschreibung. Ein
            Schweizer Lead liegt auf de+fr vor, ein belgischer auf fr+nl. */}
        {sprachen.length > 1 ? (
          <div className="doclang" role="group" aria-label={t("sprache.dokument")}>
            <span>{t("sprache.dokument")}</span>
            {sprachen.map((code) => (
              <button key={code} type="button"
                onClick={() => setDocLang(code === docLang ? null : code)}
                aria-pressed={code === docLang}
                className={code === docLang ? "is-an" : ""}>{sprachName(code, t)}</button>
            ))}
          </div>
        ) : null}

        <div className="dtitle">
          <h2>{titelAnzeige}</h2>
          <div className="wfpick">
            {Object.entries(wf).map(([k, v]) => (
              <button key={k} className={`wf ${v.cls} ${l.userStatus === k ? "on" : ""}`} onClick={() => onWf(k)}>
                {t(v.label)}
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
              {t(tb.label)}
              {tb.key === "analyse" && isFree ? <span className="quota">1/3</span> : null}
              {tb.key === "team" && l.comments?.length ? <span className="quota">{l.comments.length}</span> : null}
              {tb.pro && isFree ? <span className="probadge probadge-lock" title={t("Im Pro-Zugang")}>{t("Pro")}</span> : null}
            </button>
          ))}
        </div>
      </div>

      {/* Zusätzliche Hinweise — bewusst als React-GESCHWISTER vor dem Reiter-Inhalt und nicht
          in den HTML-String gewebt. Der Reiter-Inhalt kommt verbatim aus dem Prototyp-Renderer;
          ihn anzufassen hiesse, jede kuenftige Aenderung dort nachzuziehen. Als Komponente
          bleibt die Logik testbar (Rangfolge, Deckel, Belege) und der Renderer unberuehrt.

          Nur in der Uebersicht: die Hinweise sollen das Erste sein, was man sieht, nicht ein
          Fund in einem Unterreiter. Wer die Frist-Warnung erst im vierten Tab findet, hat den
          Lead vorher schon zugeklappt.

          Fehlen die Felder (der Export liefert sie noch nicht), rendert die Komponente nichts —
          kein leerer Kasten, keine Fehlermeldung. */}
      {/* Die ECHTEN Dateien — als React-Geschwister vor dem Reiter-Inhalt, aus demselben
          Grund wie die Hinweise: der Reiter-Inhalt kommt verbatim aus dem Prototyp-Renderer,
          und ihn anzufassen hiesse, jede kuenftige Aenderung dort nachzuziehen.
          Sie stehen VOR der Analyse: wer den Reiter oeffnet, sucht meist das Dokument —
          die Auswertung liest man, wenn man weiss, worueber sie spricht. */}
      {activeTab === "docs" && l?.id ? <Dokumente leadId={String(l.id)} /> : null}

      {activeTab === "uebersicht" && (
        <Hinweise
          felder={{
            deadlineSource: l.deadlineSource as string | undefined,
            deadlineVeroeffentlicht: l.deadlineVeroeffentlicht as string | undefined,
            deadlineAktuell: l.deadlineAktuell as string | undefined,
            portale: l.portale as string[] | undefined,
            kategorieQuelle: l.kategorieQuelle as string | undefined,
            amtsinhaberSeitJahre: l.amtsinhaberSeitJahre as number | undefined,
            amtsinhaberZyklen: l.amtsinhaberZyklen as number | undefined,
            erfolgloseVersuche: l.erfolgloseVersuche as number | undefined,
            erfolgloseJahre: l.erfolgloseJahre as number | undefined,
          }}
        />
      )}

      {/* ⚠ DRAG-EREIGNISSE BLASEN, KLICKS AUCH — deshalb hier delegiert statt am Feld
          selbst. Der Koerper ist `dangerouslySetInnerHTML`; ein Handler AM Drop-Feld
          muesste nach jedem Neuzeichnen neu gebunden werden, und genau das vergisst man.

          ⚠ `preventDefault` auch bei `dragOver`. Ohne das ist die Flaeche kein gueltiges
          Ziel, der Browser oeffnet die Datei in einem neuen Tab und der Nutzer verliert
          seine Sicht — der haeufigste Fehler an Drop-Feldern. */}
      <div onClick={handleBody}
           onDragOver={(e) => {
             const z = (e.target as HTMLElement).closest<HTMLElement>("[data-dropzone]");
             if (!z || !onDropDocs) return;
             e.preventDefault();
             z.classList.add("dz-an");
           }}
           onDragLeave={(e) => {
             (e.target as HTMLElement).closest<HTMLElement>("[data-dropzone]")?.classList.remove("dz-an");
           }}
           onDrop={(e) => {
             const z = (e.target as HTMLElement).closest<HTMLElement>("[data-dropzone]");
             if (!z || !onDropDocs) return;
             e.preventDefault();
             z.classList.remove("dz-an");
             if (e.dataTransfer?.files?.length) onDropDocs(z.dataset.dropzone!, e.dataTransfer.files, z);
           }}
           dangerouslySetInnerHTML={{ __html: bodyHtml }} />
    </>
  );
}

/* Eine Kennung, die der geladene Grundraum nicht enthält — und was daraus wird.
 *
 * Der Fall ist kein Fehler des Nutzers und keine kaputte Datenlage: `LEADS` trägt immer nur
 * EINEN Grundraum (`/api/leads?branche=…`), während Kennungen auch von ausserhalb kommen —
 * aus dem Vergabe-Verlauf einer Vergabestelle (`buyer_recent_awards` läuft über alle
 * Branchen) und aus `?lead=`-Links. Bis zum 2026-09-02 endete genau das in einem stillen
 * `TypeError`: das Panel öffnete sich, fand nichts und stürzte beim ersten Feldzugriff ab.
 *
 * ⚠ DREI ZUSTÄNDE, NICHT EINER. Der Grundraumwechsel lädt eine Datei von bis zu 42 MB; das
 * dauert sichtbar. Wäre das Warten derselbe Zustand wie „gibt es nicht", stünde sekundenlang
 * eine Absage auf dem Schirm, die sich danach als falsch herausstellt — und wer nach zwei
 * Sekunden wegklickt, hat eine Fehlmeldung gelesen. Deshalb sagt das Warten, WOHIN es geht.
 */
function FremderGrundraum({ lead, onClose }: {
  lead: { id: string; stand: "sucht" | "wechselt" | "unbekannt"; branche?: string };
  onClose: () => void;
}) {
  const { t } = useSprache();
  const raum = (BRANCHEN as Record<string, string>)[lead.branche || ""] || lead.branche || "";

  if (lead.stand !== "unbekannt") {
    return (
      <div className="lb">
        <div className="lb-head">
          <p className="lb-h">
            {lead.stand === "sucht"
              ? t("Ausschreibung wird gesucht …")
              : t("Wechselt zu {raum} …", { raum: t(raum) })}
          </p>
          <p className="lb-l">
            {lead.stand === "sucht"
              ? t("Kennung {id} gehört zu einem anderen Grundraum. Wir suchen, zu welchem.", { id: lead.id })
              : t("Kennung {id} liegt dort. Der Grundraum wird geladen, dann öffnet sich die Ausschreibung.", { id: lead.id })}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="lb">
      <div className="lb-head">
        <p className="lb-h">{t("Diese Ausschreibung finden wir nicht")}</p>
        <p className="lb-l">
          {t("Kennung {id} liegt in keinem Grundraum, sie ist nicht mehr im Bestand oder war nie darin.", { id: lead.id })}
        </p>
        <button className="lb-h4btn" onClick={onClose}>{t("Zurück zum Überblick")}</button>
      </div>
    </div>
  );
}

/* Leerzustand als Tagesbriefing (statt „Kein Lead ausgewählt"): rechnet aus der AKTUELL
 * gefilterten Liste, was drängt und was sich lohnt — jede Zahl gemessen, keine erfundenen Werte.
 * Klick auf eine Zeile öffnet den Lead direkt. */
function LeerBriefing({ rows, alle = [], profil = null, onPick, onGoto }: {
  rows: BriefLead[]; alle?: BriefLead[];
  // Nur gezaehlt, nie gelesen: der Ueberblick sagt, WIE VIELE Angaben stehen.
  profil?: unknown;
  onPick?: (id: string) => void;
  onGoto?: (ziel: "netzwerk" | "strategie" | "award" | "vorschau" | "jetzt" | "trefferguete") => void;
}) {
  const { t } = useSprache();
  /* Zwei Spalten, nicht vier gleiche Viertel: links die Arbeit fuer heute, rechts vier
   * Kacheln als Kontext. Der Schnitt folgt dem Zeithorizont, nicht der Datenherkunft.
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
    /* ⚠ DIE LEITZAHL MUSS MAN ANFASSEN KOENNEN. „6.501 mit Frist in den naechsten
       3 Wochen" ist keine Aufgabe, sondern ein Druckmittel — niemand arbeitet 6.501 Leads
       ab. Gemessen ueber alle Grundraeume: 10.018 in drei Wochen, 3.515 in einer, 1.672 in
       zwei Tagen. Vorn steht deshalb die Woche; die groessere Zahl bleibt daneben, weil
       sie den Rahmen setzt, aber sie fuehrt nicht mehr. */
    const dieseWoche = heiss.filter((l) => (tageOf(l) ?? 99) <= 7);

    /* Vorschau: Ankündigungen + auslaufende Verträge, nach Möglichkeit profilnah.
     *
     * ⚠ HIER STAND EINE MONATSANGABE JE ZEILE („läuft in ~7 Monaten aus"), und sie ist
     * mit den Zeilen weggefallen. Falls sie jemand zurueckholt: bei einem GESCHAETZTEN
     * Enddatum ist eine Monatszahl erfunden. Gemessen an den belegten Nachfolge-Ketten
     * streut der Versatz je Gewerk um 267 bis 980 Tage (p25–p75). Nur wo `timing.src`
     * „echt" ist, darf konkret formuliert werden; sonst gehoert dorthin eine Grobstufe. */
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

    /* ⚠ JEDE LÜCKE BRAUCHT IHR EIGENES ZIEL. Bis zum 2026-09-01 führten alle vier auf
       `/unternehmen` — eine Seite, auf der man die Hälfte davon gar nicht ändern kann. Ein
       Hinweis, der ins falsche Zimmer zeigt, ist keine Einladung, sondern eine Sackgasse.

       Zwei der Lücken haben ein EINGABEFELD, und zwar in der Treffergüte (`BetragInput`,
       Betrag eintippen, Enter). Die anderen sind keine leeren Felder, sondern Einladungen,
       das Profil zu WEITEN („arbeitet ihr dort doch?"), und das geschieht im Eignungsprofil. */
    /* ⚠ `titel` und `text` sind hier am 2026-09-20 WEGGEFALLEN, nicht verlorengegangen:
       die Anleitung („tragt den Rahmen ein, den eure Bank stellt") steht in der
       Trefferguete, und das ist der einzige Ort, an dem der Wert auch eingetippt werden
       kann. Eine zweite Fassung im Ueberblick waere eine Anweisung ohne Eingabefeld.
       Geblieben ist `kurz` — die eine Zeile, die auf die Kachel passt. */
    const luecken = [
      { key: "buerg", ziel: "trefferguete", n: imFeld.filter((l) => blockerArt(l, "buergschaft_offen")).length,
        bitte: (n: string) => t("Tragt euren Bürgschaftsrahmen ein, {n} fordern ihn", { n }) },
      { key: "allein", ziel: "trefferguete", n: imFeld.filter((l) => blockerArt(l, "partner")).length,
        bitte: (n: string) => t("Sagt uns eure Alleingrenze, {n} liegen darüber", { n }) },
      { key: "region", ziel: "profil", n: imFeld.filter((l) => teilStatus(l, "region") === "no").length,
        bitte: (n: string) => t("Nehmt die Region auf, {n} liegen außerhalb", { n }) },
      { key: "vol", ziel: "profil", n: imFeld.filter((l) => teilStatus(l, "vol") === "no").length,
        bitte: (n: string) => t("Passt eure Wertspanne an, {n} liegen außerhalb", { n }) },
      /* ⚠ Der Ortstermin gehört HIERHIN und nicht nur ins Lead-Detail. Ein Pflichttermin
         ist eine Zulassungsbedingung: wer nicht erscheint, darf nicht bieten. Wer das erst
         beim Lesen der Unterlagen merkt, hat den Vorgang schon in der Merkliste. Gemessen
         2026-09-01: 3.723 Vorgänge mit erkanntem Termin, davon 108 verpflichtend — selten,
         und genau deshalb fällt er im Alltag durch. */
      { key: "ortstermin", ziel: "profil", n: imFeld.filter((l) => blockerArt(l, "ortstermin")).length,
        bitte: (n: string) => t("Nehmt die Region auf, {n} verlangen einen Ortstermin", { n }) },
    ].filter((x) => x.n > 0).sort((a, z) => z.n - a.n)
      /* ⚠ Die Zahl steht IN der Bitte, nicht davor. „1.204 liegen ausserhalb eurer
         Regionen" benennt nur, was fehlt — das ist eine Maengelmeldung. Eine Einladung
         sagt, was nach dem Klick passiert, und traegt die Zahl als Begruendung mit.
         Dieselbe Regel steht seit dem 2026-09-01 in `test_aktivierung.py`; beim Umbau auf
         Kacheln ist sie mir einmal durchgerutscht und der Waechter hat es gemeldet. */
      .map((x) => ({ ...x, text: x.bitte(x.n.toLocaleString("de-DE")) }));

    /* ⚠ Der Stand kommt aus `profileEngine`, nicht aus einer Zaehlung hier. Dieselbe
       Funktion liest auch `matchLead` aus; eine zweite Liste an dieser Stelle waere beim
       ersten neuen Profilfeld still falsch geworden. */
    const stand = angabenStand(profil);
    return { offen, heiss, dieseWoche, kuenftig, netz, zuschlaege, netzKaeufer, gewinner,
             luecken, imFeld, stand, tageOf };
  }, [rows, alle, profil]);

  /* Eine Kachel des Ueberblicks. `ziel` ist entweder ein Klick in einen Tab oder ein
     echter Verweis — beide muessen dieselbe Kachel sein, sonst faellt eine aus der Reihe.
     Ein `<a>` ist hier kein Schmuck: `/unternehmen` ist eine andere Seite, und die gehoert
     in den Verlauf und in die Mittelklick-Geste. */
  const Kachel = ({ n, label, sub, ziel }: {
    n: string; label: string; sub: string; ziel: (() => void) | string;
  }) => {
    const innen = (<>
      <span className="kx-n">{n}</span>
      <span className="kx-l">{label}</span>
      <span className="kx-s">{sub}</span>
    </>);
    return typeof ziel === "string"
      ? <a className="kx" href={ziel}>{innen}</a>
      : <button className="kx" onClick={ziel}>{innen}</button>;
  };

  const Zeile = ({ l, sub }: { l: BriefLead; sub: string }) => (
    <button className="lb-row" onClick={() => onPick?.(l.id)} title={t("Lead öffnen")}>
      <span className="lb-row-t">{String(l.titel || "").slice(0, 58)}</span>
      <span className="lb-row-s">{sub}</span>
    </button>
  );

  return (
    <div className="lb">
      <div className="lb-head">
        <p className="lb-h">{t("Euer Überblick")}</p>
        <p className="lb-l">{t("Wählt links eine Ausschreibung, oder steigt hier ein.")}</p>
      </div>

      {/* ⛔ NICHT MEHR VIER GLEICH BREITE SPALTEN. Gemessen bei den ueblichen
          Fensterbreiten (`grid-template-columns:repeat(4,…)` greift erst ab 1560 px):

              1728 px   4 Spalten   347 px hoch   alles in einer Reihe
              1512 px   3 Spalten   603 px hoch   „Markt & Netzwerk" rutscht nach unten
              1440 px   3 Spalten   603 px hoch   dito
              1100 px   2 Spalten   611 px hoch   zwei Abschnitte rutschen

          Ein MacBook 14" hat 1512, ein uebliches Fenster 1440 — die Seite war also fuer
          eine Breite entworfen, die fast niemand hat, und wurde sonst doppelt so hoch,
          mit dem vierten Abschnitt unter dem ersten, wo ihn niemand sucht.

          ⚠ DER EIGENTLICHE GRUND IST ABER NICHT DIE BREITE, SONDERN DIE RANGFOLGE. Die
          vier Abschnitte beantworten vier Fragen, und nur eine ist Arbeit fuer heute:
          „was ist dringend". Die anderen drei sind Kontext. Gleich breite Spalten
          behaupten Gleichrang, den es nicht gibt — und geben „Bahnt sich an" mit seinen
          14 Eintraegen dasselbe Viertel wie den 10.018 offenen Fristen. Daher kommen die
          weissen Loecher. */}
      <div className="lb-zwei">
        {/* ── jetzt ─────────────────────────────────────────────── */}
        <section className="lb-sp">
          <h4>
            <span className="lb-dot heiss" />
            {/* Rückweg in die Liste: aus dem Überblick gab es bisher keinen. */}
            <button className="lb-h4btn" onClick={() => onGoto?.("jetzt")}>{t("Jetzt bewerben")}</button>
          </h4>
          <p className="lb-n2">{b.dieseWoche.length.toLocaleString("de-DE")}<em>{t("mit Frist in dieser Woche")}</em></p>
          <p className="lb-rahmen">{t("{n} innerhalb von drei Wochen", { n: b.heiss.length.toLocaleString("de-DE") })}</p>
          {b.heiss.length ? b.heiss.slice(0, 5).map((l) => {
            const tage = b.tageOf(l);
            return <Zeile key={l.id} l={l}
              sub={tage === 0 ? t("läuft heute ab") : tage === 1 ? t("läuft morgen ab")
                   : t("noch {n} Tage", { n: tage ?? 0 })} />;
          }) : <p className="lb-nix">{t("Gerade nichts Dringendes, gut so.")}</p>}
        </section>

        {/* ── Kontext: vier Kacheln und ein Weg ───────────────────────────────
            Vorher standen hier drei Abschnitte mit eigener Ueberschrift, eigenem Punkt
            und drei verschiedenen Bauformen: fuenf Trefferzeilen, drei Luecken-Kacheln,
            drei Markt-Kacheln. Gemessen bei 1440 px: 18 klickbare Flaechen, 8 grosse
            Zahlen, 205 Woerter, 821 px hoch — bei rund 800 px sichtbarer Hoehe. Sven am
            2026-09-20: „sonst ist alles voll".

            Jetzt EIN Muster: vier gleich gebaute Kacheln, jede mit einem Ziel, darunter
            der eine Weg, der keine Zahl ist. Gemessen 11 Flaechen, 374 px.

            ⚠ Was dabei WEGFAELLT, faellt nicht weg, sondern rueckt eine Ebene tiefer: die
            fuenf Vorschau-Zeilen stehen im Phasen-Tab, die weiteren Profil-Luecken in der
            Trefferguete. Die Kachel zeigt die groesste; schliesst man sie, rueckt die
            naechste nach. */}
        <div className="lb-kontext">
          <div className="lb-kx">
            {/* ⚠ „4 von 6" und NICHT „67 %": ein Prozentsatz verspricht, dass 100
                erreichbar ist. Wer keine Buergschaft hat und keine will, kommt nie
                dorthin und wird dafuer jeden Tag angetippt. Die Zahl im Nenner steht in
                `angabenStand` und zaehlt nur, was `matchLead` liest und ein Mensch
                setzen kann. */}
            <Kachel
              n={t("{a} von {b}", { a: b.stand.voll, b: b.stand.gesamt })}
              label={t("Angaben im Profil")}
              sub={b.luecken.length
                ? b.luecken[0].text
                : b.imFeld.length
                  ? t("Nichts blockiert euch gerade.")
                  : t("Legt euer Profil an, dann zeigen wir hier, was euch Aufträge kostet.")}
              ziel={b.luecken.length && b.luecken[0].ziel === "trefferguete"
                ? () => onGoto?.("trefferguete") : "/unternehmen"} />
            <Kachel
              n={b.kuenftig.length.toLocaleString("de-DE")}
              label={t("bahnen sich an")}
              sub={b.kuenftig.length
                ? t("Ankündigungen und auslaufende Verträge")
                : t("Noch keine Vorankündigungen in eurem Feld.")}
              ziel={() => onGoto?.("vorschau")} />
            <Kachel
              n={b.netz.length.toLocaleString("de-DE")}
              label={t("Mehrlos-Vergaben")}
              sub={b.netzKaeufer.length
                ? t("u.a. bei {wer}, hier lohnt ein Partner", { wer: b.netzKaeufer.join(t(" und ")) })
                : t("hier lohnt ein Partner")}
              ziel={() => onGoto?.("netzwerk")} />
            <Kachel
              n={b.zuschlaege.length.toLocaleString("de-DE")}
              label={t("frische Zuschläge")}
              sub={b.gewinner.length
                ? t("u.a. an {wer}, wer gewonnen hat, kauft jetzt ein", { wer: b.gewinner.join(t(" und ")) })
                : t("wer gewonnen hat, kauft jetzt ein")}
              ziel={() => onGoto?.("award")} />
          </div>
          {/* Die Strategie ist keine Zahl, sondern ein Ort. Als fuenfte Kachel liesse sie
              im Zweierraster ein Loch; als flache Zeile schliesst sie den Block ab. */}
          <button className="lb-strat" onClick={() => onGoto?.("strategie")}>
            {t("Strategie: wohin sich euer Markt bewegt")}<span aria-hidden="true">→</span>
          </button>
        </div>
      </div>

      <p className="lb-foot">{t("Zahlen beziehen sich auf eure aktuell gefilterte Liste.")}</p>
    </div>
  );
}
