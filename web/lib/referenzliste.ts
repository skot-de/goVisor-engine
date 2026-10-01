"use client";

/**
 * Referenzliste der eigenen Firma als kopier-/herunterladbares Dokument (Markdown + Word).
 * Quelle: /api/firma/referenzen (gewonnene TED-Zuschlaege der eigenen Identitaet). Muster wie
 * lib/dossier.ts (Briefing je Lead), nur fuers eigene Unternehmen.
 */
export type Referenz = {
  titel: string; auftraggeber: string | null; jahr: number | null; wert: number | null;
  cpv?: string | null; land?: string | null; notice_id?: string | null;
};

const eur = (w: number | null | undefined) =>
  w == null ? "—" : Math.round(w).toLocaleString("de-DE") + " €";
const z = (s: string | null | undefined) => (s ?? "—").replace(/\|/g, "/").replace(/\s+/g, " ").trim();
// notice_id "660351_2026" → TED-Publikationsnummer "660351-2026".
const tedUrl = (nid?: string | null) =>
  nid ? `https://ted.europa.eu/de/notice/-/detail/${nid.replace(/_/g, "-")}` : "";

function kopf(firma: string, refs: Referenz[]): string {
  return `Referenzliste ${firma}\n`
    + `${refs.length} belegte Zuschläge aus öffentlichen Vergabebekanntmachungen (TED). `
    + `Werte in EUR, wo veröffentlicht.`;
}

export function referenzenMarkdown(firma: string, refs: Referenz[]): string {
  const out = [`# ${z(firma)}: Referenzliste`, "", kopf(firma, refs).split("\n")[1], "",
    "| Jahr | Auftraggeber | Gegenstand | Auftragswert |", "|---|---|---|---|"];
  for (const r of refs) out.push(`| ${r.jahr ?? "—"} | ${z(r.auftraggeber)} | ${z(r.titel)} | ${eur(r.wert)} |`);
  out.push("", "*Jede Zeile ist eine öffentlich bekanntgemachte Vergabe (TED), keine Selbstauskunft. Erstellt mit goVisor.*");
  return out.join("\n");
}

export function referenzenDocHtml(firma: string, refs: Referenz[]): string {
  const esc = (s: string) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const zrs = refs.map((r) => {
    const t = tedUrl(r.notice_id);
    const geg = t ? `<a href="${t}">${esc(z(r.titel))}</a>` : esc(z(r.titel));
    return `<tr><td style="border:1px solid #ccc;padding:6px 8px">${r.jahr ?? "—"}</td>`
      + `<td style="border:1px solid #ccc;padding:6px 8px">${esc(z(r.auftraggeber))}</td>`
      + `<td style="border:1px solid #ccc;padding:6px 8px">${geg}</td>`
      + `<td style="border:1px solid #ccc;padding:6px 8px;white-space:nowrap">${esc(eur(r.wert))}</td></tr>`;
  }).join("");
  return `<!DOCTYPE html><html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word"><head><meta charset="utf-8"><title>Referenzliste</title></head>
<body style="font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#12211d">
<h1 style="font-size:18pt;margin-bottom:2px">${esc(z(firma))}: ${esc("Referenzliste")}</h1>
<p style="color:#64766f;margin-top:0">${esc(kopf(firma, refs).split("\n")[1])}</p>
<table style="border-collapse:collapse;width:100%;margin:8px 0;font-size:10pt">
<tr><th style="border:1px solid #ccc;padding:6px 8px;background:#f5f7f6;text-align:left">Jahr</th>
<th style="border:1px solid #ccc;padding:6px 8px;background:#f5f7f6;text-align:left">Auftraggeber</th>
<th style="border:1px solid #ccc;padding:6px 8px;background:#f5f7f6;text-align:left">Gegenstand</th>
<th style="border:1px solid #ccc;padding:6px 8px;background:#f5f7f6;text-align:left">Auftragswert</th></tr>
${zrs}</table>
<p style="font-size:9pt;color:#8c9b95">Jede Zeile ist eine öffentlich bekanntgemachte Vergabe (TED), keine Selbstauskunft. Erstellt mit goVisor.</p>
</body></html>`;
}

function dl(content: string, mime: string, name: string) {
  const blob = new Blob(["﻿" + content], { type: mime });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
const fname = (firma: string, ext: string) =>
  `Referenzliste_${(firma || "Firma").replace(/[^\wäöüÄÖÜß -]/g, "").trim().slice(0, 40)}_${new Date().toISOString().slice(0, 10)}.${ext}`;

export function downloadReferenzenMd(firma: string, refs: Referenz[]) {
  dl(referenzenMarkdown(firma, refs), "text/markdown;charset=utf-8", fname(firma, "md"));
}
export function downloadReferenzenDoc(firma: string, refs: Referenz[]) {
  dl(referenzenDocHtml(firma, refs), "application/msword;charset=utf-8", fname(firma, "doc"));
}
export async function copyReferenzen(firma: string, refs: Referenz[]): Promise<boolean> {
  try { await navigator.clipboard.writeText(referenzenMarkdown(firma, refs)); return true; } catch { return false; }
}
