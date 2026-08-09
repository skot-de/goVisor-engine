"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { BRANCHEN, COLS, FACETS, ORTE, RADII, TOKICON } from "@/lib/explorerCore";

type Token = { type: string; value: string; label: string; radius?: number | null };
const has = (tokens: Token[], type: string, value: string) =>
  tokens.some((t) => t.type === type && t.value === value);

/* ── Spalten-Menü ────────────────────────────────────────────────────────── */
export function ColumnMenu({ open, onToggleCol }: { open: boolean; onToggleCol: (k: string) => void }) {
  const cols = COLS as { key: string; label: string; on: boolean; lock?: boolean }[];
  return (
    <div className="colmenu" data-open={open ? "" : undefined}>
      {cols.map((c) => (
        <div
          key={c.key}
          className="ci"
          data-col={c.key}
          data-on={c.on ? "" : undefined}
          data-locked={c.lock ? "" : undefined}
          onClick={() => !c.lock && onToggleCol(c.key)}
        >
          <span className="box" />
          {c.label || (c.key === "star" ? "Merken" : c.key)}
        </div>
      ))}
    </div>
  );
}

/* ── Filter-Chips (aktive Tokens) ────────────────────────────────────────── */
export function FilterBar({
  tokens, openRadius, onRemove, onClear, onToggleRadius, onSetRadius,
}: {
  tokens: Token[]; openRadius: number | null;
  onRemove: (i: number) => void; onClear: () => void;
  onToggleRadius: (i: number) => void; onSetRadius: (i: number, km: number) => void;
}) {
  if (!tokens.length) return <div className="filterbar empty" />;
  return (
    <div className="filterbar">
      {tokens.map((t, i) => (
        <span key={i} className={`ftoken ftoken-${t.type}`}>
          <span className="tok-lbl">{t.label}</span>
          {t.type === "ort" ? (
            <span style={{ position: "relative" }}>
              <button className="tok-rad" onClick={() => onToggleRadius(i)}>
                {t.radius ? `${t.radius} km` : "Umkreis"} ▾
              </button>
              {openRadius === i ? (
                <div className="radmenu">
                  {(RADII as number[]).map((km) => (
                    <button
                      key={km}
                      className={`radopt ${(t.radius || 0) === km ? "on" : ""}`}
                      onClick={() => onSetRadius(i, km)}
                    >
                      {km ? `${km} km` : "ohne"}
                    </button>
                  ))}
                </div>
              ) : null}
            </span>
          ) : null}
          <button className="tok-x" onClick={() => onRemove(i)} aria-label="Filter entfernen">
            ×
          </button>
        </span>
      ))}
      <button className="fb-clear" onClick={onClear}>
        zurücksetzen
      </button>
    </div>
  );
}

/* ── Such-Vorschläge ─────────────────────────────────────────────────────── */
export function Suggestions({
  query, list, suggIdx, onPick,
}: {
  query: string; list: Token[] & { cat?: string }[]; suggIdx: number;
  onPick: (v: number | "raw") => void;
}) {
  const icons = TOKICON as Record<string, string>;
  if (!query.trim() || !list.length) return <div className="suggest" />;
  return (
    <div className="suggest open">
      {list.map((o, i) => (
        <button key={i} className={`sugg ${i === suggIdx ? "hl" : ""}`} onClick={() => onPick(i)}>
          <span className="sugg-ic" dangerouslySetInnerHTML={{ __html: icons[o.type] }} />
          <span className="sugg-lbl">{o.label}</span>
          <span className="sugg-cat">{(o as { cat?: string }).cat}</span>
        </button>
      ))}
      <button className={`sugg sugg-raw ${suggIdx === list.length ? "hl" : ""}`} onClick={() => onPick("raw")}>
        <span className="sugg-ic" dangerouslySetInnerHTML={{ __html: icons.text }} />
        <span className="sugg-lbl">„{query.trim()}" als Freitext suchen</span>
      </button>
    </div>
  );
}

/* ── Kopf-Filter-Menü — portaliert ans Dokument-Ende (Übergabenotiz §9) ───── */
export function HeaderFilterPopover({
  facet, rect, tokens, onToggleFacet, onTogglePlace,
}: {
  facet: string; rect: DOMRect; tokens: Token[];
  onToggleFacet: (name: string, v: string, label: string) => void;
  onTogglePlace: (region: string, label: string) => void;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  const style: React.CSSProperties = {
    position: "fixed",
    left: Math.min(rect.left, window.innerWidth - 210),
    top: rect.bottom + 6,
    zIndex: 80,
  };

  let body: React.ReactNode;
  if (facet === "region") {
    const list = Object.values(ORTE as Record<string, { region: string; label: string }>).filter(
      (v, i, a) => a.findIndex((x) => x.region === v.region) === i
    );
    body = (
      <div className="reglist">
        {list.map((o) => (
          <button
            key={o.region}
            className={`regopt ${has(tokens, "ort", o.region) ? "on" : ""}`}
            onClick={() => onTogglePlace(o.region, o.label)}
          >
            <span className="fbox" />
            {o.label}
          </button>
        ))}
      </div>
    );
  } else {
    const f = (FACETS as Record<string, { opts: { v: string; l: string }[] }>)[facet];
    body = f.opts.map((o) => (
      <button
        key={o.v}
        className={`facetopt ${has(tokens, facet, o.v) ? "on" : ""}`}
        onClick={() => onToggleFacet(facet, o.v, o.l)}
      >
        <span className="fbox" />
        {o.l}
      </button>
    ));
  }

  return createPortal(
    <div className="headpop open" style={style} data-headpop={facet}>
      {body}
    </div>,
    document.body
  );
}
