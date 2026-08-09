/* #27 §11 — Export der Eignungsübersicht. JSON (Datenmitnahme) + PDF (Druckansicht, keine Lib).
 * Umfasst Angaben, Referenzen, Zertifikate, Ausschlüsse. NICHT Textbausteine (#23) und
 * NICHT hochgeladene Nachweisdokumente (§11.1). */
"use client";
import { computeKmu, certValid, type Profil, type ProfilContext } from "@/lib/supabase/unternehmen";
import { catalogItem } from "./catalog";

function download(name: string, mime: string, content: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; document.body.appendChild(a); a.click();
  a.remove(); URL.revokeObjectURL(url);
}

export function exportProfilJson(profil: Profil, ctx: ProfilContext) {
  const kmu = computeKmu(profil.stammdaten);
  const payload = {
    firma: ctx.companyName, identity_id: ctx.identityId, entity_confidence: ctx.entityConfidence,
    exportiert_am: new Date().toISOString(),
    stammdaten: profil.stammdaten, kmu: { status: kmu.ist_kmu, kategorie: kmu.kategorie, begruendung: kmu.begruendung },
    zielrichtung: profil.zielrichtung, branchen: profil.branchen.cpv,
    anforderungen: profil.attributes, referenzen: profil.references,
    zertifikate: profil.certificates, ausschluesse: profil.exclusions, rolle: profil.role,
  };
  const slug = (ctx.companyName || "unternehmen").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  download(`eignungsprofil-${slug}.json`, "application/json", JSON.stringify(payload, null, 2));
}

const esc = (s: unknown) => String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c] as string));
const eur = (v?: number | null) => (v == null ? "—" : v.toLocaleString("de-DE", { maximumFractionDigits: 0 }) + " €");

export function exportProfilPdf(profil: Profil, ctx: ProfilContext) {
  const kmu = computeKmu(profil.stammdaten);
  const sd = profil.stammdaten;
  const anf = Object.entries(profil.attributes).map(([k, a]) => {
    const it = catalogItem(k); const label = it?.label || k;
    const val = a.value === true ? "ja" : a.value === false ? "nein" : a.value == null ? "—" : String(a.value);
    return `<tr><td>${esc(label)}</td><td>${esc(val)}</td><td>${esc(a.zustand)}</td></tr>`;
  }).join("");
  const refs = profil.references.map((r) =>
    `<tr><td>${esc(r.projekt)}</td><td>${esc(r.auftraggeber)}</td><td>${eur(r.wert)}</td><td>${esc(r.von)}–${esc(r.bis)}</td><td>${esc(r.cpv)}</td></tr>`).join("");
  const certs = profil.certificates.map((c) =>
    `<tr><td>${esc(c.typ)}</td><td>${esc(c.nummer)}</td><td>${esc(c.gueltig_bis)}</td><td>${certValid(c) ? "gültig" : "abgelaufen"}</td></tr>`).join("");

  const html = `<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Eignungsübersicht — ${esc(ctx.companyName)}</title>
<style>
  body{font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;color:#111;max-width:800px;margin:24px auto;padding:0 16px}
  h1{font-size:22px;margin:0 0 2px} h2{font-size:15px;border-bottom:1px solid #ccc;padding-bottom:3px;margin:22px 0 8px}
  .sub{color:#555;margin:0 0 14px} table{width:100%;border-collapse:collapse;margin:6px 0}
  th,td{text-align:left;padding:4px 8px;border-bottom:1px solid #eee;vertical-align:top} th{color:#666;font-weight:600;font-size:11px;text-transform:uppercase}
  .kv{display:grid;grid-template-columns:180px 1fr;gap:2px 12px} .kv div{padding:2px 0}
  .badge{display:inline-block;padding:1px 8px;border-radius:10px;background:#eef;font-size:11px}
  @media print{body{margin:0}}
</style></head><body>
  <h1>Eignungsübersicht</h1>
  <p class="sub">${esc(ctx.companyName || "—")} · Stand ${new Date().toLocaleDateString("de-DE")} · <span class="badge">${kmu.label}</span></p>

  <h2>Stammdaten</h2>
  <div class="kv">
    <div><b>Rechtsform</b></div><div>${esc(sd.rechtsform || "—")}</div>
    <div><b>Gründungsjahr</b></div><div>${esc(sd.gruendungsjahr || "—")}</div>
    <div><b>Mitarbeiter</b></div><div>${esc(sd.mitarbeiter ?? "—")}</div>
    <div><b>Umsatz (letzte 3 GJ)</b></div><div>${eur(sd.umsatz_j1)} · ${eur(sd.umsatz_j2)} · ${eur(sd.umsatz_j3)}</div>
    <div><b>KMU-Status</b></div><div>${esc(kmu.begruendung)}</div>
    <div><b>Zielrichtung</b></div><div>${esc(profil.zielrichtung)}</div>
    <div><b>CPV-Schwerpunkte</b></div><div>${esc(profil.branchen.cpv.join(", ") || "—")}</div>
  </div>

  <h2>Anforderungen</h2>
  ${anf ? `<table><thead><tr><th>Anforderung</th><th>Angabe</th><th>Zustand</th></tr></thead><tbody>${anf}</tbody></table>` : "<p class='sub'>keine erfasst</p>"}

  <h2>Referenzen</h2>
  ${refs ? `<table><thead><tr><th>Projekt</th><th>Auftraggeber</th><th>Wert</th><th>Zeitraum</th><th>CPV</th></tr></thead><tbody>${refs}</tbody></table>` : "<p class='sub'>keine erfasst</p>"}

  <h2>Zertifikate</h2>
  ${certs ? `<table><thead><tr><th>Typ</th><th>Nummer</th><th>gültig bis</th><th>Status</th></tr></thead><tbody>${certs}</tbody></table>` : "<p class='sub'>keine erfasst</p>"}

  <script>window.onload=function(){setTimeout(function(){window.print();},250);};</script>
</body></html>`;

  const win = window.open("", "_blank");
  if (!win) { alert("Bitte Pop-ups für den PDF-Export erlauben."); return; }
  win.document.open(); win.document.write(html); win.document.close();
}
