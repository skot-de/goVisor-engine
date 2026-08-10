"use client";

import { useRef } from "react";
import { COLS, cellHTML, chanceCap } from "@/lib/explorerCore";

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
  fuss,
  sortKey,
  sortDir,
  activeId,
  activeFacets,
  onSort,
  onSelect,
  onStar,
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
  /** Abschluss-Zeile unter der letzten Ausschreibung (Vorauswahl aufheben). */
  fuss?: React.ReactNode;
  sortKey: string;
  sortDir: number;
  activeId: string | null;
  /** Aktive Token-Anzahl je Facette (für den „on"-Zustand des Trichters). */
  activeFacets: Record<string, number>;
  onSort: (key: string) => void;
  onSelect: (id: string) => void;
  onStar: (id: string) => void;
  onNetz: (id: string) => void;
  onOwn: (id: string, ans: string) => void;
  onHeadFilter: (facet: string, rect: DOMRect) => void;
  onReorder: (fromKey: string, toKey: string, after: boolean) => void;
  colWidths: Record<string, number>;
  onResize: (key: string, width: number) => void;
}) {
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

  function handleRowClick(e: React.MouseEvent<HTMLTableSectionElement>) {
    const t = e.target as HTMLElement;
    const star = t.closest<HTMLElement>("[data-star]");
    if (star) { e.stopPropagation(); onStar(star.dataset.star!); return; }
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
    <table className="leads">
      <thead>
        <tr>
          {cols.map((c) => {
            const thCls = [c.th === "right" ? "right" : "", c.th === "center" ? "center" : ""]
              .filter(Boolean)
              .join(" ");
            const sortable = SORTABLE.has(c.key);
            const label = c.key === "wechsel" ? chanceCap() : c.label;
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
                    title="Filtern"
                    aria-label="Spalte filtern"
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
        {rows.length ? (
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
              <div className="empty-t">
                <b>Keine Leads mit diesen Filtern.</b> Passe die Filter an oder wechsle den
                Grundraum.
              </div>
            </td>
          </tr>
        )}
        {rows.length && fuss ? (
          <tr className="fussrow"><td colSpan={colspan}>{fuss}</td></tr>
        ) : null}
      </tbody>
    </table>
  );
}
