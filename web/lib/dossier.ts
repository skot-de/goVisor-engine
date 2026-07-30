import { aufwandStufe } from "@/lib/explorerCore";

/* Auto-Dossier (Ticket #4): 1–2-seitiges Briefing eines Leads als Markdown oder Word.
 * Template-basiert (kein LLM), Herkunft ehrlich mitgeführt. Word = HTML-`.doc` (öffnet
 * editierbar in Word, keine Extra-Abhängigkeit). Kein PDF (nie — nicht bearbeitbar). */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Lead = any;

const SRC = { echt: "veröffentlicht", schaetz: "geschätzt", unbekannt: "unbekannt" } as Record<string, string>;
const band = (b?: string) => (!b || b === "na" ? "—" : b);
const tedUrl = (id: string) => `https://ted.europa.eu/de/notice/-/detail/${String(id).replace(/_/g, "-")}`;
// Briefing-Quelle = goVisor-Deep-Link (führt den Empfänger zurück in die App), TED bleibt als
// Herkunftsbeleg dahinter. Origin kommt vom aktuellen Deployment (Dossier wird im Browser erzeugt).
const govisorUrl = (id: string) => {
  const base = (typeof window !== "undefined" && window.location) ? window.location.origin : "";
  return `${base}/leads?lead=${encodeURIComponent(String(id))}`;
};
const heute = () => { const d = new Date(); return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`; };

function eckdaten(l: Lead): [string, string][] {
  const vol = l.volumen?.wert ? `${l.volumen.wert} (${SRC[l.volumen.src] || l.volumen.src})` : "unbekannt";
  const rows: [string, string][] = [
    ["Auftraggeber", l.buyer || "—"],
    ["Leistung", `${l.cpvLabel} (CPV ${l.cpv})`],
    ["Region", l.region || "—"],
    ["Volumen", vol],
    ["Frist / Auslauf", l.endet || "—"],
    ["Vertragsart", l.art || "—"],
    ["Rechtsrahmen", l.rahmen ? String(l.rahmen).toUpperCase() : "—"],
  ];
  if (l.incumbent?.name) rows.push(["Amtsinhaber", `${l.incumbent.name}${l.incumbent.seit ? ` (seit ${l.incumbent.seit})` : ""}`]);
  return rows;
}

function bewertung(l: Lead): [string, string][] {
  return [
    ["Relevanz", band(l.relevanz)],
    [l.incumbent ? "Verdrängungs-Risiko" : "Wechsel-Chance", band(l.wechsel)],
    ["Angebotsaufwand", band(aufwandStufe(l)?.stufe)],
  ];
}

function zusammenfassung(l: Lead): string {
  const vol = l.volumen?.wert ? `Das Volumen liegt bei ${l.volumen.wert} (${SRC[l.volumen.src] || l.volumen.src}).` : "Ein Auftragswert ist nicht veröffentlicht.";
  const rel = l.relevanz && l.relevanz !== "na"
    ? `Die Passung zu eurem Profil ist ${l.relevanz}.`
    : "Die Passung lässt sich erst mit hinterlegtem Profil bewerten.";
  return `${l.buyer || "Eine Vergabestelle"} vergibt „${l.cpvLabel}" (${l.phaseLabel}). ${vol} ${l.endet ? `Zeithorizont: ${l.endet}. ` : ""}${rel}`;
}

function anforderungen(l: Lead): [string, string][] | null {
  const m = l.match;
  if (!m || !m.teile?.length) return null;
  const mark = { ok: "erfüllt", teil: "teilweise", no: "fehlt", unbekannt: "nicht prüfbar" } as Record<string, string>;
  return m.teile.map((t: { label: string; status: string; text: string }) => [t.label, `${mark[t.status] || t.status} — ${t.text}`]);
}

// ── Markdown ────────────────────────────────────────────────────────────────
export function dossierMarkdown(l: Lead): string {
  const mdTable = (rows: [string, string][]) =>
    ["| | |", "|---|---|", ...rows.map(([k, v]) => `| **${k}** | ${v} |`)].join("\n");
  const out: string[] = [];
  out.push(`# Briefing: ${l.titel}`, `*${l.phaseLabel} · ${l.cpvLabel}*`, "");
  out.push("## Zusammenfassung", zusammenfassung(l), "");
  out.push("## Eckdaten", mdTable(eckdaten(l)), "");
  out.push("## Bewertung", mdTable(bewertung(l)), "");
  const anf = anforderungen(l);
  if (anf) out.push("## Anforderungs-Check", mdTable(anf), "");
  out.push("---", `Quelle: [In goVisor öffnen](${govisorUrl(l.id)}) · Bekanntmachung auf [TED](${tedUrl(l.id)}) · Datenstand ${heute()} · erstellt mit goVisor`,
    "*Volumen- und Timing-Angaben sind, wo gekennzeichnet, geschätzt — nicht veröffentlichte Werte werden nicht geraten.*");
  return out.join("\n");
}

// ── Word (HTML-.doc) ─────────────────────────────────────────────────────────
export function dossierDocHtml(l: Lead): string {
  const esc = (s: string) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const tbl = (rows: [string, string][]) =>
    `<table style="border-collapse:collapse;width:100%;margin:8px 0">${rows.map(([k, v]) =>
      `<tr><td style="border:1px solid #ccc;padding:6px 10px;background:#f5f7f6;font-weight:bold;width:32%">${esc(k)}</td><td style="border:1px solid #ccc;padding:6px 10px">${esc(v)}</td></tr>`).join("")}</table>`;
  const anf = anforderungen(l);
  return `<!DOCTYPE html><html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word"><head><meta charset="utf-8"><title>Briefing</title></head>
<body style="font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#12211d">
<h1 style="font-size:18pt;margin-bottom:2px">Briefing: ${esc(l.titel)}</h1>
<p style="color:#64766f;margin-top:0">${esc(l.phaseLabel)} · ${esc(l.cpvLabel)}</p>
<h2 style="font-size:13pt;color:#067a55">Zusammenfassung</h2><p>${esc(zusammenfassung(l))}</p>
<h2 style="font-size:13pt;color:#067a55">Eckdaten</h2>${tbl(eckdaten(l))}
<h2 style="font-size:13pt;color:#067a55">Bewertung</h2>${tbl(bewertung(l))}
${anf ? `<h2 style="font-size:13pt;color:#067a55">Anforderungs-Check</h2>${tbl(anf)}` : ""}
<hr><p style="font-size:9pt;color:#8c9b95">Quelle: <a href="${govisorUrl(l.id)}">In goVisor öffnen</a> · Bekanntmachung auf TED (${tedUrl(l.id)}) · Datenstand ${heute()} · erstellt mit goVisor.<br>
Volumen- und Timing-Angaben sind, wo gekennzeichnet, geschätzt — nicht veröffentlichte Werte werden nicht geraten.</p>
</body></html>`;
}

// ── Downloads ────────────────────────────────────────────────────────────────
function fname(l: Lead, ext: string) {
  const clean = (s: string) => String(s || "").replace(/[^\wäöüÄÖÜß -]/g, "").trim().slice(0, 40);
  const d = new Date();
  return `Briefing_${clean(l.buyerShort || l.buyer)}_${clean(l.titel)}_${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}.${ext}`;
}
function dl(content: string, mime: string, name: string) {
  const blob = new Blob(["﻿" + content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}
export function downloadMarkdown(l: Lead) { dl(dossierMarkdown(l), "text/markdown;charset=utf-8", fname(l, "md")); }
export function downloadDoc(l: Lead) { dl(dossierDocHtml(l), "application/msword;charset=utf-8", fname(l, "doc")); }
export async function copyMarkdown(l: Lead): Promise<boolean> {
  try { await navigator.clipboard.writeText(dossierMarkdown(l)); return true; } catch { return false; }
}
