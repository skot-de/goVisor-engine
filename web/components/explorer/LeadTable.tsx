"use client";

import React, { useEffect, useRef, useState } from "react";
import { COLS, WF, cellHTML, chanceCap } from "@/lib/explorerCore";
import { useSprache } from "@/lib/i18n";

type Col = { key: string; label: string; on: boolean; th?: string; lock?: boolean };
type Lead = { id: string; status?: string; userStatus?: string; [k: string]: unknown };

const SORTABLE = new Set([
  "titel", "buyer", "frist", "relevanz", "wechsel", "aufwand", "vol", "src", "konk",
]);
// Spalten, die einen Facetten-Filter im Kopf tragen → Menüname
const HEADFILTER: Record<string, string> = {
  src: "phase", natur: "leistung", region: "region", rahmen: "rahmen",
};

const FunnelIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 5h18l-7 8v5l-4 2v-7L3 5Z" />
  </svg>
);

export function LeadTable({
  rows,
  limit,
  laedt,
  stoerung,
  gefiltert,
  fuss,
  abschnitte,
  sortKey,
  sortDir,
  activeId,
  activeFacets,
  onSort,
  onSelect,
  onStar,
  onWf,
  onDokLink,
  onHide,
  onNetz,
  onOwn,
  onHeadFilter,
  onReorder,
  colWidths,
  onResize,
}: {
  rows: Lead[];
  /** Nur die ersten `limit` Zeilen rendern (inkrementelles Nachwachsen beim Scrollen). */
  limit: number;
  /** Die Daten sind noch unterwegs.
   *
   *  ⚠ DRITTER ZUSTAND, NICHT ZWEITER. „Keine Leads" ist eine Aussage ueber die Daten;
   *  waehrend des Ladens ist sie falsch. Bis zum 2026-09-17 sah der Nutzer nach der
   *  Anmeldung rund zwoelf Sekunden lang „Keine Leads mit diesen Filtern. Passe die
   *  Filter an oder wechsle den Grundraum." — eine Aufforderung, an Filtern zu drehen,
   *  die nichts mit dem Problem zu tun hatten. */
  laedt?: boolean;
  /** Der Abruf ist GESCHEITERT — nicht „nichts gefunden".
   *
   *  ⚠ A16 im Fallenkatalog: „Ein leeres Ergebnis ist eine AUSSAGE. Kommt sie auch dann,
   *  wenn niemand nachgesehen hat, ist ein Ausfall zur Auskunft geworden." Dieselbe
   *  Unterscheidung steht seit dem 2026-09-04 in `lib/ladegrund.js` — sie war an dieser
   *  Stelle nur nie angeschlossen. Bis zum 2026-09-18 setzte der Fehlerzweig schlicht
   *  `loading = false`, und die Liste sagte „Keine Leads mit diesen Filtern": genau die
   *  Aufforderung, an Filtern zu drehen, die mit dem Problem nichts zu tun haben. */
  stoerung?: boolean;
  /** Sind ueberhaupt Filter oder Suchworte gesetzt?
   *
   *  ⚠ DRITTER ZUSTAND. „Keine Leads MIT DIESEN FILTERN" ist falsch, wenn keine gesetzt
   *  sind — dann liegt es am Grundraum, und der Rat geht ins Leere. */
  gefiltert?: boolean;
  /** Abschluss-Zeile unter der letzten Ausschreibung (Vorauswahl aufheben). */
  fuss?: React.ReactNode;
  /** Abschnitte statt einer flachen Liste — Zwischenzeile vor jeder Gruppe. */
  abschnitte?: { key: string; titel: string; hinweis: string; rows: Lead[] }[];
  sortKey: string;
  sortDir: number;
  activeId: string | null;
  /** Aktive Token-Anzahl je Facette (für den „on"-Zustand des Trichters). */
  activeFacets: Record<string, number>;
  onSort: (key: string) => void;
  onSelect: (id: string) => void;
  onStar: (id: string) => void;
  /** Status aus der Liste heraus setzen. `null` nimmt ihn zurueck. */
  onWf?: (id: string, k: string | null) => void;
  /** Unterlagen beim Portal oeffnen UND den Lead aufschlagen. */
  onDokLink?: (id: string) => void;
  onHide?: (id: string) => void;
  onNetz: (id: string) => void;
  onOwn: (id: string, ans: string) => void;
  onHeadFilter: (facet: string, rect: DOMRect) => void;
  onReorder: (fromKey: string, toKey: string, after: boolean) => void;
  colWidths: Record<string, number>;
  onResize: (key: string, width: number) => void;
}) {
  const { t } = useSprache();  // Zellen-HTML kommt aus explorerCore (tk) und rendert mit
  const cols: Col[] = (COLS as Col[]).filter((c) => c.on);
  const colspan = cols.length;
  const dragCol = useRef<string | null>(null);
  const resizing = useRef(false);

  function startResize(e: React.MouseEvent, key: string) {
    e.preventDefault();
    e.stopPropagation();
    resizing.current = true;
    const th = (e.currentTarget as HTMLElement).closest("th") as HTMLElement;
    const startW = th.offsetWidth;
    const startX = e.clientX;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    const move = (ev: MouseEvent) => onResize(key, startW + (ev.clientX - startX));
    const up = () => {
      // erst nach dem nächsten Tick freigeben, damit ein evtl. Klick nicht sortiert
      setTimeout(() => (resizing.current = false), 0);
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }

  function markDrop(th: HTMLElement, e: React.DragEvent) {
    const r = th.getBoundingClientRect();
    const after = e.clientX > r.left + r.width / 2;
    document.querySelectorAll("th.drop-l,th.drop-r").forEach((t) => t.classList.remove("drop-l", "drop-r"));
    th.classList.add(after ? "drop-r" : "drop-l");
    return after;
  }

  /* ── EIN Menue fuer alle Zeilen ────────────────────────────────────────────────
     ⚠ NICHT vier Knoepfe je Zeile. Das waeren bei 50 Zeilen 200 zusaetzliche Elemente,
     und die Meldung vom selben Tag lautete „es sind immer noch einfach ganz viele
     balken". Die Zelle bleibt, wie sie war; dieses Menue haengt sich beim Klick an sie.

     ⚠ Position in SEITENKOORDINATEN (`position:fixed`), nicht relativ zur Tabelle: die
     Tabelle scrollt in einem eigenen Behaelter, und ein absolut positioniertes Menue
     waere beim Scrollen mitgewandert, aber am falschen Ort stehengeblieben. */
  const [wfMenu, setWfMenu] = useState<{ id: string; x: number; y: number } | null>(null);
  useEffect(() => {
    if (!wfMenu) return;
    const zu = () => setWfMenu(null);
    const taste = (ev: KeyboardEvent) => { if (ev.key === "Escape") setWfMenu(null); };
    // ⚠ `capture`, sonst schliesst der Klick auf einen Menuepunkt das Menue, BEVOR
    //    dessen eigener Handler laeuft — der Punkt waere dann nie erreichbar.
    window.addEventListener("scroll", zu, true);
    window.addEventListener("resize", zu);
    window.addEventListener("keydown", taste);
    return () => {
      window.removeEventListener("scroll", zu, true);
      window.removeEventListener("resize", zu);
      window.removeEventListener("keydown", taste);
    };
  }, [wfMenu]);

  function handleRowClick(e: React.MouseEvent<HTMLTableSectionElement>) {
    const t = e.target as HTMLElement;
    const dl = t.closest<HTMLElement>("[data-doklink]");
    if (dl && onDokLink) { e.stopPropagation(); onDokLink(dl.dataset.doklink!); return; }
    const wf = t.closest<HTMLElement>("[data-wf]");
    if (wf && onWf) {
      e.stopPropagation();
      const r = wf.getBoundingClientRect();
      setWfMenu((m) => (m?.id === wf.dataset.wf ? null : { id: wf.dataset.wf!, x: r.left, y: r.bottom + 4 }));
      return;
    }
    const star = t.closest<HTMLElement>("[data-star]");
    if (star) { e.stopPropagation(); onStar(star.dataset.star!); return; }
    const hide = t.closest<HTMLElement>("[data-hide]");
    if (hide) { e.stopPropagation(); onHide?.(hide.dataset.hide!); return; }
    const ni = t.closest<HTMLElement>("[data-netzint]");
    if (ni) { e.stopPropagation(); onNetz(ni.dataset.netzint!); return; }
    const own = t.closest<HTMLElement>("[data-own]");
    if (own) {
      e.stopPropagation();
      const [id, ans] = own.dataset.own!.split(":");
      onOwn(id, ans);
      return;
    }
    const row = t.closest<HTMLElement>("tr[data-id]");
    if (row) onSelect(row.dataset.id!);
  }

  return (
    <>
    <table className="leads">
      <thead>
        <tr>
          {cols.map((c) => {
            const thCls = [c.th === "right" ? "right" : "", c.th === "center" ? "center" : ""]
              .filter(Boolean)
              .join(" ");
            const sortable = SORTABLE.has(c.key);
            // `COLS` ist eine Modul-Konstante und wird beim Import ausgewertet — dort
            // uebersetzt waere die Sprache beim ersten Laden eingefroren. Der deutsche
            // Label IST der Schluessel, also erst hier beim Rendern nachschlagen.
            const label = t(c.key === "wechsel" ? chanceCap() : c.label);
            const arrow = sortKey === c.key ? (sortDir > 0 ? "▲" : "▼") : "↕";
            const facet = HEADFILTER[c.key];
            const nActive = facet ? activeFacets[facet === "region" ? "ort" : facet] || 0 : 0;
            return (
              <th
                key={c.key}
                className={`${thCls} ${facet ? "has-filter" : ""}`.trim()}
                data-thcol={c.key}
                data-sort={sortable ? c.key : undefined}
                data-sorted={sortKey === c.key ? "" : undefined}
                style={colWidths[c.key] ? { width: colWidths[c.key], minWidth: colWidths[c.key], maxWidth: colWidths[c.key] } : undefined}
                draggable={c.key !== "star"}
                onDragStart={(e) => {
                  if (resizing.current) { e.preventDefault(); return; }
                  dragCol.current = c.key;
                  e.currentTarget.classList.add("dragging");
                  e.dataTransfer.effectAllowed = "move";
                }}
                onDragEnd={(e) => {
                  e.currentTarget.classList.remove("dragging");
                  document.querySelectorAll("th.drop-l,th.drop-r").forEach((t) => t.classList.remove("drop-l", "drop-r"));
                  dragCol.current = null;
                }}
                onDragOver={(e) => {
                  if (!dragCol.current || c.key === "star") return;
                  e.preventDefault();
                  markDrop(e.currentTarget, e);
                }}
                onDrop={(e) => {
                  if (!dragCol.current || c.key === "star") return;
                  e.preventDefault();
                  const after = markDrop(e.currentTarget, e);
                  onReorder(dragCol.current, c.key, after);
                }}
              >
                <span
                  className="th-lbl"
                  onClick={sortable ? () => onSort(c.key) : undefined}
                  style={sortable ? { cursor: "pointer" } : undefined}
                >
                  {label}
                </span>
                <span
                  className="ar"
                  onClick={sortable ? () => onSort(c.key) : undefined}
                  style={sortable ? { cursor: "pointer" } : undefined}
                >
                  {arrow}
                </span>
                {facet ? (
                  <button
                    className={`thfilter ${nActive ? "on" : ""}`}
                    title={t("Filtern")}
                    aria-label={t("Spalte filtern")}
                    onClick={(e) => {
                      e.stopPropagation();
                      onHeadFilter(facet, (e.currentTarget as HTMLElement).getBoundingClientRect());
                    }}
                  >
                    {FunnelIcon}
                    {nActive ? <span className="thfn">{nActive}</span> : null}
                  </button>
                ) : null}
                {c.key !== "star" ? (
                  <span
                    className="th-resize"
                    onMouseDown={(e) => startResize(e, c.key)}
                    onClick={(e) => e.stopPropagation()}
                    draggable={false}
                    title="Breite ziehen"
                    aria-hidden
                  />
                ) : null}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody onClick={handleRowClick}>
        {/* Abschnitte bilden den Trichter ab: worauf man sich JETZT bewerben kann, was
            sich anbahnt, was strategisch dran ist. Vorher war das eine flache Liste plus
            ein „Alle anzeigen"-Schalter — die Struktur sagt dasselbe, ohne Klick. */}
        {abschnitte?.length ? abschnitte.map((a) => (
          <React.Fragment key={a.key}>
            <tr className="sekrow" data-sek={a.key}>
              <td colSpan={colspan}>
                <span className="sek-t">{a.titel}</span>
                <span className="sek-n">{a.rows.length}</span>
                <span className="sek-h">{a.hinweis}</span>
              </td>
            </tr>
            {a.rows.length ? a.rows.slice(0, limit).map((l) => (
              <tr key={l.id} data-id={l.id}
                className={[l.status === "ungesichtet" ? "" : "gesichtet",
                  l.userStatus === "verworfen" ? "wf-verworfen" : ""].filter(Boolean).join(" ")}
                data-unread={l.status === "ungesichtet" ? "" : undefined}
                aria-selected={l.id === activeId}
                dangerouslySetInnerHTML={{ __html: cols.map((c) => cellHTML(l, c.key)).join("") }} />
            )) : (
              <tr className="sek-leer"><td colSpan={colspan}>Hier ist gerade nichts.</td></tr>
            )}
          </React.Fragment>
        )) : rows.length ? (
          rows.slice(0, limit).map((l) => {
            const cls = [
              l.status === "ungesichtet" ? "" : "gesichtet",
              l.userStatus === "verworfen" ? "wf-verworfen" : "",
            ]
              .filter(Boolean)
              .join(" ");
            const html = cols.map((c) => cellHTML(l, c.key)).join("");
            return (
              <tr
                key={l.id}
                data-id={l.id}
                className={cls}
                data-unread={l.status === "ungesichtet" ? "" : undefined}
                aria-selected={l.id === activeId}
                dangerouslySetInnerHTML={{ __html: html }}
              />
            );
          })
        ) : (
          <tr className="emptyrow">
            <td colSpan={colspan}>
              {/* ⚠ VIER ZUSTAENDE, NICHT ZWEI. Nur die letzten beiden duerfen eine
                  Aussage ueber die DATEN treffen; die ersten beiden sagen etwas ueber
                  UNS. Die Reihenfolge ist wichtig: eine Stoerung waehrend des Ladens ist
                  eine Stoerung, keine Ladeanzeige, die nie endet (Fallenkatalog A16). */}
              {stoerung ? (
                <div className="empty-t stoer-t" role="alert">
                  <b>{t("Die Ausschreibungen konnten nicht geladen werden.")}</b>{" "}
                  {t("Das liegt an uns, nicht an euren Filtern. Bitte neu laden.")}
                </div>
              ) : laedt ? (
                <div className="empty-t lade-t" aria-live="polite">
                  <span className="lade-punkte" aria-hidden="true"><i /><i /><i /></span>
                  <b>{t("Ausschreibungen werden geladen.")}</b>{" "}
                  {t("Das dauert beim ersten Aufruf einige Sekunden.")}
                </div>
              ) : gefiltert ? (
                <div className="empty-t">
                  <b>{t("Keine Leads mit diesen Filtern.")}</b>{" "}
                  {t("Passe die Filter an oder wechsle den Grundraum.")}
                </div>
              ) : (
                <div className="empty-t">
                  <b>{t("In diesem Grundraum ist gerade nichts offen.")}</b>{" "}
                  {t("Wechsle den Grundraum oder schau später noch einmal.")}
                </div>
              )}
            </td>
          </tr>
        )}
        {/* Auch bei leerer Phase anzeigen — sonst ist sie eine Sackgasse ohne Rückweg. */}
        {fuss ? (
          <tr className="fussrow"><td colSpan={colspan}>{fuss}</td></tr>
        ) : null}
      </tbody>
    </table>
    {wfMenu && onWf ? (
      <>
        {/* Auffangflaeche: ein Klick daneben schliesst, ohne dass die Zeile darunter
            mitgeoeffnet wird. */}
        <div className="wfm-scrim" onClick={() => setWfMenu(null)} />
        <div className="wfm" style={{ left: wfMenu.x, top: wfMenu.y }} role="menu"
             aria-label={t("Status setzen")}>
          {Object.entries(WF as Record<string, { label: string; cls: string }>).map(([k, v]) => (
            <button key={k} role="menuitem" className={`wfm-i ${v.cls}`}
                    onClick={() => { onWf(wfMenu.id, k); setWfMenu(null); }}>
              {t(v.label)}
            </button>
          ))}
          <button role="menuitem" className="wfm-i wfm-weg"
                  onClick={() => { onWf(wfMenu.id, null); setWfMenu(null); }}>
            {t("Kein Status")}
          </button>
        </div>
      </>
    ) : null}
    </>
  );
}
