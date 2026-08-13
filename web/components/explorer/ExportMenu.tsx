"use client";

import { useEffect, useRef, useState } from "react";
import writeXlsxFile from "write-excel-file/browser";
import { aufwandStufe } from "@/lib/explorerCore";
import { track, EV } from "@/lib/analytics";
import { tk, useSprache } from "@/lib/i18n";

/* Export der aktuellen (gefilterten + sortierten) Lead-Liste — Excel/CSV (Ticket #5).
   Respektiert die Ansicht, max. 1000 Zeilen. CSV ist DE-Excel-tauglich (UTF-8+BOM, Semikolon).

   Sprache: die Spaltenköpfe stehen unten DEUTSCH in einer Modul-Konstante — sie wird beim
   Import ausgewertet und würde die Sprache einfrieren. Übersetzt wird erst beim Bauen der
   Datei (`tk(c.label)`), denn die Export-Funktionen sind keine Komponenten und können den
   Hook nicht rufen; im Menü selbst (Komponente) gilt das reguläre `t`. */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Lead = any;
const MAX = 1000;

const bandWort = (b?: string) => (!b || b === "na" ? "" : tk(b));
const tedUrl = (id: string) => `https://ted.europa.eu/de/notice/-/detail/${String(id).replace(/_/g, "-")}`;
// Code-Tabellen: Schlüssel bleiben Codes, die Werte sind Anzeigetext → erst beim Lesen übersetzen.
const VOL_SRC: Record<string, string> = { echt: "veröffentlicht", schaetz: "geschätzt", unbekannt: "unbekannt" };
const NATUR: Record<string, string> = { dienst: "Dienstleistung", liefer: "Lieferung", bau: "Bauleistung" };
const codeWort = (tab: Record<string, string>, code?: string) => (code && tab[code] ? tk(tab[code]) : "");

// Spalten: Label + Wert-Getter. Aus der UI-Lead-Form gemappt; leere/na-Werte bleiben leer (ehrlich).
const COLS: { label: string; get: (l: Lead) => string }[] = [
  { label: "Ausschreibung", get: (l) => l.titel || "" },
  { label: "Auftraggeber", get: (l) => l.buyer || "" },
  { label: "CPV", get: (l) => l.cpv || "" },
  { label: "CPV-Bezeichnung", get: (l) => l.cpvLabel || "" },
  { label: "Region", get: (l) => l.region || "" },
  { label: "Leistungsort (NUTS)", get: (l) => l.nuts || "" },
  { label: "Volumen", get: (l) => (l.volumen?.wert || "").replace(/\s*€/, "") },
  { label: "Volumen-Quelle", get: (l) => codeWort(VOL_SRC, l.volumen?.src) },
  { label: "Vertragsart", get: (l) => l.art || "" },
  { label: "Rechtsrahmen", get: (l) => (l.rahmen ? String(l.rahmen).toUpperCase() : "") },
  { label: "Leistungsart", get: (l) => codeWort(NATUR, l.naturKat) },
  { label: "Phase", get: (l) => l.phaseLabel || "" },
  { label: "Frist / Auslauf", get: (l) => l.endet || "" },
  { label: "Relevanz", get: (l) => bandWort(l.relevanz) },
  { label: "Wechsel-Chance", get: (l) => bandWort(l.wechsel) },
  { label: "Angebotsaufwand", get: (l) => bandWort(aufwandStufe(l)?.stufe) },
  { label: "Amtsinhaber", get: (l) => l.incumbent?.name || "" },
  { label: "TED-Link", get: (l) => tedUrl(l.id) },
];

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

function dateiname(view: string, ext: string) {
  const d = new Date();
  const stamp = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return `goVisor_Leads_${view}_${stamp}.${ext}`;
}

function exportCsv(rows: Lead[], view: string) {
  const esc = (s: string) => `"${String(s).replace(/"/g, '""')}"`;
  const head = COLS.map((c) => esc(tk(c.label))).join(";");
  const body = rows.map((l) => COLS.map((c) => esc(c.get(l))).join(";")).join("\r\n");
  // UTF-8 BOM → deutsches Excel erkennt Umlaute + Semikolon-Trennung.
  const blob = new Blob(["﻿" + head + "\r\n" + body], { type: "text/csv;charset=utf-8" });
  download(blob, dateiname(view, "csv"));
}

async function exportXlsx(rows: Lead[], view: string) {
  // v4-Spaltenformat: { header, cell:(obj)=>Cell, width }. API gibt { toBlob, toFile } zurück.
  const columns = COLS.map((c) => {
    const kopf = tk(c.label);
    return {
      header: { value: kopf, fontWeight: "bold" as const },
      width: Math.min(48, Math.max(12, kopf.length + 4)),
      cell: (l: Lead) => { const v = c.get(l); return v ? { value: v, type: String } : null; },
    };
  });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const blob: Blob = await (writeXlsxFile as any)(rows, { columns, sheet: "Leads" }).toBlob();
  download(blob, dateiname(view, "xlsx"));
}

export function ExportMenu({ rows, view }: { rows: Lead[]; view: string }) {
  const { t } = useSprache();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const capped = rows.slice(0, MAX);
  async function run(fmt: "csv" | "xlsx") {
    setOpen(false);
    track(EV.EXPORT, { format: fmt, rows: capped.length, view });
    if (fmt === "csv") exportCsv(capped, view);
    else await exportXlsx(capped, view);
  }

  return (
    <div className="colcfg" ref={ref} style={{ position: "relative" }}>
      <button className="colbtn" type="button" onClick={() => setOpen((o) => !o)} disabled={!rows.length} title={t("Aktuelle Liste exportieren")}>
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3v12M7 10l5 5 5-5M5 21h14" />
        </svg>
        {t("Export")}
      </button>
      {open && (
        <div className="exp-menu">
          <button className="exp-opt" onClick={() => run("xlsx")}>
            <b>Excel</b><span>{t(".xlsx · formatiert")}</span>
          </button>
          <button className="exp-opt" onClick={() => run("csv")}>
            <b>CSV</b><span>{t(".csv · UTF-8, Semikolon")}</span>
          </button>
          <div className="exp-note">{rows.length > MAX
            ? t("{max} von {n} (Obergrenze)", { max: MAX, n: rows.length })
            : t("{n} Leads · aktuelle Ansicht", { n: rows.length })}</div>
        </div>
      )}
    </div>
  );
}
