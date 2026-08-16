"use client";
import { useState, useEffect, useCallback } from "react";
import { useSprache } from "@/lib/i18n";

/* INTERNES Vertriebstool — Firmen nach Sitz/Name suchen → Schmerz-Signale + Ansprache-Details.
 * Enthält Kontaktdaten; die API blockiert Production. Reine Sales-Sicht (kein Kundenprodukt). */

type Sig = { n: number; vol: number | null; letzter?: string | null; naechstes?: string | null };
type Badge = { label: string; cls: string; spark?: string };
type Control = { k: string; label: string; def: number; step?: number; type?: string };
type Firma = {
  id: string; name: string; plz: string | null; ort: string | null; wins36: number;
  medWert: number | null; vol36: number | null; s1: Sig; s2: Sig; dominant: string;
  email: string | null; phone: string | null;
  badge?: Badge; line?: string; metric?: number; // Vertriebsziel-Segment (deutschlandweit)
  weitere?: { key: string; label: string }[]; rahmenQuote?: number;
};

// Vertriebsziel-Segmente A–G (govisor-vertriebsziele-spec.md), Reihenfolge = Ansprache-Priorität §8
// `tab`/`title` bleiben hier deutsche Literale — sie sind die Übersetzungsschlüssel und gehen
// erst an der Render-Stelle durch `t()`. Ein `t()` in der Modul-Konstante fröre die Sprache
// beim Import ein.
const SEGS: { key: string; tab: string; title: string }[] = [
  { key: "F", tab: "Frische Verlierer", title: "Verlust ≤6 Monate. Akut, kürzestes Zeitfenster" },
  { key: "E", tab: "Verteidiger", title: "Bestand läuft in 6 bis 18 Monaten aus (≥250k)" },
  { key: "C", tab: "Absteiger", title: "Zuschlagszahl fällt über 3 Jahre" },
  { key: "A", tab: "High Roller", title: "≥24 Zuschläge in 12 Monaten. Verdrängungsverkauf" },
  { key: "D", tab: "Aussteiger", title: "früher aktiv, ≥18 Monate kein Zuschlag mehr" },
  { key: "G", tab: "Aufsteiger", title: "Zuschlagszahl steigt ≥40 % über 3 Jahre" },
  { key: "B", tab: "Gelegenheitsbieter", title: "1 bis 5 Zuschläge in 24 Monaten, größte Gruppe" },
];
type Exp = { titel: string; buyer: string; vol: number | null; ende: string | null; mte: number | null; vsrc?: string; art?: string | null; artcat?: string | null; url?: string | null; seit?: number | null };
type Loss = { titel: string; vol: number | null; datum: string | null; gewinner: string | null };
type Recent = { titel: string; buyer: string | null; vol: number | null; jahr: number | null; url?: string | null };
type Wett = { name: string; id: string; expiring: Exp[]; basis?: string | null };
type Buyer = { name: string; wins: number; letztes: number | null };
type Lead = { titel: string; buyer: string | null; ort: string | null; vol: number | null; frist: string | null; tage: number | null; url: string | null; art?: string | null; artcat?: string | null; seg?: string | null; dist?: number | null; ted?: string | null; doku?: string | null };
type Detail = { id: string; name: string; expiring: Exp[]; losses: Loss[]; recent?: Recent[]; wettbewerber?: Wett | null;
  website?: string | null; kmu?: boolean; segment?: string | null; topBuyers?: Buyer[]; leads?: Lead[]; leadsScope?: string; error?: string };

// Vertragstitel als Link zur TED-Bekanntmachung (extern → neuer Tab) + Vertragsart-Label.
// artcat (rahmen/einmal/neutral) steuert die Farbe — Bedeutung erklärt die Legende unten.
function Titel({ text, url, art, artcat }: { text: string | null; url?: string | null; art?: string | null; artcat?: string | null }) {
  const { t } = useSprache();
  // NICHT `t` nennen — das würde die Übersetzungsfunktion beschatten.
  const txt = text || t("(ohne Titel)");
  return (
    <>
      {url ? <a className="in-tlink" href={url} target="_blank" rel="noreferrer">{txt} ↗</a> : txt}
      {art && <span className={`in-art ${artcat || "neutral"}`}>{art}</span>}
    </>
  );
}

const nf = new Intl.NumberFormat("de-DE");
const eur = (v: number | null | undefined) =>
  v == null ? "—" : v >= 1e6 ? (v / 1e6).toFixed(1).replace(".", ",") + " Mio €"
  : nf.format(Math.round(v)) + " €";

export function InternFirmen() {
  const { t } = useSprache();
  const [plz, setPlz] = useState("");
  const [radius, setRadius] = useState(""); // Umkreis km (nur mit PLZ)
  const [ort, setOrt] = useState("");
  const [name, setName] = useState("");
  const [firmen, setFirmen] = useState<Firma[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [contacted, setContacted] = useState<Set<string>>(new Set());
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState<"" | "s1" | "s2" | "offen" | "aktiv">(""); // Schnellfilter
  const [segMode, setSegMode] = useState<string>(""); // aktives Vertriebsziel-Segment (A–G)
  // Outreach-Log (Server): 12-Monats-Sperre + Trefferquote je Segment
  const [cooldown, setCooldown] = useState<Record<string, string>>({});
  const [treffer, setTreffer] = useState<Record<string, { n: number; quote: number; interessiert: number; gewonnen: number }>>({});

  useEffect(() => {
    try { setContacted(new Set(JSON.parse(localStorage.getItem("govisor.outreach") || "[]"))); } catch { /* ignore */ }
    try { setNotes(JSON.parse(localStorage.getItem("govisor.notes") || "{}")); } catch { /* ignore */ }
    fetch("/api/intern/outreach").then((r) => r.json()).then((d) => {
      if (d.cooldown) setCooldown(d.cooldown);
      if (d.trefferquote) setTreffer(d.trefferquote);
    }).catch(() => { /* ignore */ });
  }, []);

  // Ansprache protokollieren (Server-Log + lokale Sofortanzeige) — segmentübergreifende 12-Monats-Sperre
  async function logOutreach(f: Firma, outcome: string) {
    setContacted((prev) => new Set(prev).add(f.id));
    setCooldown((prev) => ({ ...prev, [f.id]: new Date().toISOString().slice(0, 10) }));
    try { localStorage.setItem("govisor.outreach", JSON.stringify([...contacted, f.id])); } catch { /* ignore */ }
    try {
      await fetch("/api/intern/outreach", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ id: f.id, name: f.name, segment: segMode || "", outcome }),
      });
      const d = await (await fetch("/api/intern/outreach")).json();
      if (d.trefferquote) setTreffer(d.trefferquote);
    } catch { /* ignore */ }
  }

  function setNote(id: string, text: string) {
    setNotes((prev) => {
      const n = { ...prev, [id]: text };
      if (!text) delete n[id];
      try { localStorage.setItem("govisor.notes", JSON.stringify(n)); } catch { /* ignore */ }
      return n;
    });
  }

  // Outreach-Landing für eine Firma erzeugen und den Link in die Zwischenablage kopieren
  const [landing, setLanding] = useState<Record<string, { busy?: boolean; url?: string; copied?: boolean }>>({});
  async function makeLanding(id: string) {
    setLanding((p) => ({ ...p, [id]: { busy: true } }));
    try {
      const r = await fetch(`/api/intern/landing?id=${encodeURIComponent(id)}`, { method: "POST" });
      const d = await r.json();
      if (d.url) {
        const full = `${window.location.origin}${d.url}`;
        try { await navigator.clipboard.writeText(full); } catch { /* ignore */ }
        setLanding((p) => ({ ...p, [id]: { url: d.url, copied: true } }));
      } else setLanding((p) => ({ ...p, [id]: {} }));
    } catch { setLanding((p) => ({ ...p, [id]: {} })); }
  }

  // Fehlertexte bleiben deutsche Literale (= Schlüssel) und werden erst beim Rendern
  // übersetzt — sonst hinge die Meldung an der Sprache zum Zeitpunkt des Fehlers fest.
  const runSearch = useCallback(async (p: string, o: string, n: string, rad: string) => {
    if (!p && !o && !n) return;
    setLoading(true); setErr(null); setFirmen(null); setOpenId(null); setDetail(null);
    const q = new URLSearchParams();
    if (p) q.set("plz", p); if (o) q.set("ort", o); if (n) q.set("name", n);
    if (p && rad) q.set("radius", rad);
    // Suche in die URL spiegeln → Zurück-Navigation (z. B. vom Firmenprofil) stellt sie wieder her.
    window.history.replaceState(null, "", `/intern?${q}`);
    try {
      const r = await fetch(`/api/intern/firmen?${q}`);
      const d = await r.json();
      if (d.error) setErr(d.error); else setFirmen(d.firmen || []);
    } catch { setErr("Suche fehlgeschlagen"); }
    finally { setLoading(false); }
  }, []);

  function search(e?: React.FormEvent) {
    e?.preventDefault();
    setSegMode("");
    runSearch(plz.trim(), ort.trim(), name.trim(), radius);
  }

  // Vertriebsziel-Segment (deutschlandweite Kohorte, kein Suchbegriff) — mit einstellbaren Knöpfen
  const [segHint, setSegHint] = useState<string>("");
  const [segControls, setSegControls] = useState<Control[]>([]);
  const [segParams, setSegParams] = useState<Record<string, number>>({});
  const [sortBy, setSortBy] = useState<"metric" | "name" | "wert" | "sitz" | "rahmen">("metric");
  const [dedup, setDedup] = useState(true); // §8 Einmalzuordnung (nur höchstprior. Segment)

  const [segGeo, setSegGeo] = useState<string>(""); // aktiver Sitz-Geo-Filter (Label aus Backend)
  async function runSegment(seg: string, over?: Record<string, number>, dedupVal: boolean = dedup,
                            noGeo = false, geoArg?: { plz?: string; radius?: string; ort?: string }) {
    if (segMode === seg && !over && !noGeo) { setSegMode(""); setFirmen(null); return; } // Toggle aus
    setSegMode(seg); setFilter(""); setLoading(true); setErr(null); setFirmen(null); setOpenId(null); setDetail(null);
    const parts = over ? Object.entries(over).map(([k, v]) => `${k}:${v}`) : [];
    if (!dedupVal) parts.push("dedup:0"); // 1 ist Default → nur bei aus mitschicken
    const p = parts.join(",");
    // Sitz-Geo-Filter aus explizitem Argument (URL-Restore) oder den oberen Suchfeldern (PLZ+Radius / Ort)
    const gp2 = (geoArg ? geoArg.plz : plz)?.trim() || "";
    const go2 = (geoArg ? geoArg.ort : ort)?.trim() || "";
    const gr2 = (geoArg ? geoArg.radius : radius) || "";
    const g = new URLSearchParams();
    if (!noGeo && gp2) { g.set("plz", gp2); if (gr2) g.set("radius", gr2); }
    else if (!noGeo && go2) g.set("ort", go2);
    const gq = g.toString();
    window.history.replaceState(null, "", `/intern?segment=${seg}${p ? `&p=${p}` : ""}${gq ? `&${gq}` : ""}`);
    try {
      const r = await fetch(`/api/intern/firmen?segment=${seg}${p ? `&p=${encodeURIComponent(p)}` : ""}${gq ? `&${gq}` : ""}`);
      const d = await r.json();
      if (d.error) setErr(d.error);
      else {
        setFirmen(d.firmen || []); setSegHint(d.hint || ""); setSegGeo(d.geo || "");
        if (!over) { // frisches Segment → Knöpfe + Defaults übernehmen
          setSegControls(d.controls || []);
          const defs: Record<string, number> = {};
          (d.controls || []).forEach((c: Control) => { defs[c.k] = c.def; });
          setSegParams(defs); setSortBy("metric");
        }
      }
    } catch { setErr("Segment fehlgeschlagen"); }
    finally { setLoading(false); }
  }

  // Beim Laden (auch nach Zurück) Suche oder Rangliste aus der URL wiederherstellen
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const seg = sp.get("segment");
    if (seg && /^[A-G]$/.test(seg)) {
      const gp = sp.get("plz") || "", go = sp.get("ort") || "", gr = sp.get("radius") || "";
      if (gp) { setPlz(gp); setRadius(gr); } else if (go) setOrt(go);
      runSegment(seg, undefined, true, false, { plz: gp, ort: go, radius: gr });
      return;
    }
    const p = sp.get("plz") || "", o = sp.get("ort") || "", n = sp.get("name") || "", rad = sp.get("radius") || "";
    if (p || o || n) { setPlz(p); setOrt(o); setName(n); setRadius(rad); runSearch(p, o, n, rad); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runSearch]);

  async function toggle(id: string) {
    if (openId === id) { setOpenId(null); setDetail(null); return; }
    setOpenId(id); setDetail(null); setDetailLoading(true);
    try {
      const r = await fetch(`/api/intern/firmen?id=${encodeURIComponent(id)}`);
      setDetail(await r.json());
    } catch { setDetail({ id, name: "", expiring: [], losses: [], error: "Details nicht ladbar" }); }
    finally { setDetailLoading(false); }
  }

  // Aktiv = im Schnitt ≥4 Zuschläge/Jahr (wins36 ≥ 12) → lohnt die Ansprache auch ohne akutes Signal
  const AKTIV_MIN = 12;
  const perJahr = (w: number) => Math.round((w / 3) * 10) / 10;

  // Schnellfilter auf die Trefferliste (clientseitig)
  const visible = (firmen || []).filter((f) =>
    filter === "s1" ? f.s1.n > 0 : filter === "s2" ? f.s2.n > 0 : filter === "offen" ? !contacted.has(f.id)
    : filter === "aktiv" ? f.wins36 >= AKTIV_MIN : true
  );

  // Segment-Modus: clientseitig sortierbar (Backend liefert nach metric vorsortiert)
  const shown = segMode
    ? [...(firmen || [])].sort((a, b) =>
        sortBy === "name" ? a.name.localeCompare(b.name)
        : sortBy === "wert" ? (b.medWert || 0) - (a.medWert || 0)
        : sortBy === "sitz" ? (a.plz || "~").localeCompare(b.plz || "~")
        : sortBy === "rahmen" ? (b.rahmenQuote ?? -1) - (a.rahmenQuote ?? -1)
        : (b.metric || 0) - (a.metric || 0))
    : visible;

  // (2) Pitch-Zeile: kopierfertiger Einzeiler aus den Schmerz-Signalen der Firma.
  // BEWUSST deutsch: das ist kein Oberflächentext, sondern der Anschreibe-Entwurf an eine
  // deutsche Vergabefirma — er wird kopiert und versendet, nicht angezeigt.
  function pitchFor(f: Firma, d: Detail | null): string {
    const parts: string[] = [];
    if (f.s2.n > 0) parts.push(`in den nächsten Monaten laufen ${f.s2.n} Verträge (~${eur(f.s2.vol)})${f.s2.naechstes ? ` bis ${f.s2.naechstes}` : ""} aus`);
    if (f.s1.n > 0) parts.push(`${f.s1.n} Aufträge (${eur(f.s1.vol)}) gingen zuletzt an den Wettbewerb`);
    const buyer = d?.topBuyers?.[0]?.name;
    if (buyer) parts.push(`Hauptkunde ${buyer.split(",")[0].split(" ").slice(0, 5).join(" ")}`);
    const nLeads = d?.leads?.length ?? 0;
    const kern = parts.length ? parts.join("; ") : `${f.wins36} Zuschläge in 36 Monaten, Median ${eur(f.medWert)}`;
    const lead = nLeads > 0 ? ` Dazu ${nLeads} offene Ausschreibungen, die exakt zum Profil passen.` : "";
    return `Hallo, kurz zu ${f.name}: ${kern}.${lead} goVisor zeigt, wo Sie angreifbar sind und welche Aufträge jetzt passen — 15 Minuten dazu?`;
  }
  function copyPitch(id: string, text: string) {
    try { navigator.clipboard.writeText(text); } catch { /* ignore */ }
    setPitchCopied(id); setTimeout(() => setPitchCopied((c) => (c === id ? null : c)), 2000);
  }
  const [pitchCopied, setPitchCopied] = useState<string | null>(null);

  // (5) CSV-Export der aktuell sichtbaren Trefferliste (inkl. Notizen + Status).
  // Kopfzeile + Statuswerte bleiben deutsch: das ist ein Datenformat für die interne
  // Weiterverarbeitung, keine Oberfläche — eine mitwandernde Spaltenbenennung bräche jede
  // Auswertung, die auf den Namen aufsetzt.
  function exportCsv() {
    const segTab = segMode ? (SEGS.find((s) => s.key === segMode)?.tab || segMode) : "";
    const head = ["Firma", "PLZ", "Ort", "Segment", "Signal", "weitere_Segmente", "Rahmen_Quote_%",
      "Zuschläge36M", "MedianWert", "verloren_n", "verloren_vol", "auslauf_n", "auslauf_vol",
      "Telefon", "Email", "angesprochen", "Notiz"];
    const q = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const list = segMode ? shown : visible;
    const rows = list.map((f) => [
      f.name, f.plz, f.ort, segTab, f.badge?.label ?? "",
      (f.weitere || []).map((wg) => wg.label).join(" / "), f.rahmenQuote ?? "",
      f.wins36, f.medWert, f.s1.n, f.s1.vol, f.s2.n, f.s2.vol,
      f.phone, f.email, contacted.has(f.id) ? "ja" : "", notes[f.id] || "",
    ].map(q).join(";"));
    const csv = "﻿" + [head.map(q).join(";"), ...rows].join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url; a.download = `firmen-radar${segMode ? `-${segMode}` : ""}.csv`; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="in-wrap">
      <div className="in-head">
        <h1>{t("Firmen-Radar")} <span className="in-tag">{t("intern")}</span></h1>
        <p>{t("Zielfirmen nach Sitz oder Name, mit Schmerz-Signalen (verlorene & auslaufende Verträge) für die Erstansprache. Enthält Kontaktdaten aus öffentlichen Bekanntmachungen; nur intern.")}</p>
      </div>

      <form className="in-search" onSubmit={search}>
        <input placeholder={t("PLZ (z. B. 59071)")} value={plz} onChange={(e) => setPlz(e.target.value)} inputMode="numeric" />
        <select className="in-radius" value={radius} onChange={(e) => setRadius(e.target.value)} disabled={!plz} title={t("Umkreis um die PLZ")}>
          <option value="">{t("exakt")}</option>
          <option value="5">+5 km</option>
          <option value="10">+10 km</option>
          <option value="25">+25 km</option>
          <option value="50">+50 km</option>
        </select>
        <input placeholder={t("Ort (z. B. Hamm)")} value={ort} onChange={(e) => setOrt(e.target.value)} />
        <input placeholder={t("Firmenname (z. B. Klostermann)")} value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit" disabled={loading}>{loading ? t("Suche …") : t("Suchen")}</button>
      </form>

      <div className="in-nw">
        <span className="in-nw-label">{t("Vertriebsziele (deutschlandweit):")}</span>
        {SEGS.map((s) => (
          <button key={s.key} className={`in-nw-btn ${segMode === s.key ? "on" : ""}`} title={t(s.title)} onClick={() => runSegment(s.key)}>{t(s.tab)}</button>
        ))}
      </div>
      {segMode && segHint && (
        <div className="in-seghint">{t(SEGS.find((s) => s.key === segMode)?.tab || segMode)}: {segHint}
          {segGeo
            ? <span className="in-geochip">📍 {segGeo} <button className="in-geoclear" title={t("Geo-Filter entfernen")} onClick={() => { setPlz(""); setOrt(""); setRadius(""); runSegment(segMode, segParams, dedup, true); }}>×</button></span>
            : <span className="in-geohint"> · {t("Tipp: PLZ+Umkreis oder Ort oben eintragen → Segment filtert auf den Firmensitz")}</span>}
          {treffer[segMode]
            ? <span className="in-tq" title={t("Konversion = (interessiert + gewonnen) / Ansprachen")}> · {t("Trefferquote {quote}% aus {n} Ansprachen ({interessiert} interessiert, {gewonnen} gewonnen)", { quote: treffer[segMode].quote, n: treffer[segMode].n, interessiert: treffer[segMode].interessiert, gewonnen: treffer[segMode].gewonnen })}</span>
            : <span className="in-geohint"> · {t("Trefferquote: noch keine Ansprache protokolliert (Detail öffnen → „protokollieren\")")}</span>}
        </div>
      )}

      {segMode && segControls.length > 0 && (
        <div className="in-knobs">
          {segControls.map((c) => (
            <label key={c.k} className="in-knob">
              <span>{t(c.label)}</span>
              {c.type === "toggle"
                ? <input type="checkbox" checked={(segParams[c.k] ?? c.def) >= 1}
                    onChange={(e) => setSegParams((p) => ({ ...p, [c.k]: e.target.checked ? 1 : 0 }))} />
                : <input type="number" value={segParams[c.k] ?? c.def} step={c.step || 1}
                    onChange={(e) => setSegParams((p) => ({ ...p, [c.k]: Number(e.target.value) }))} />}
            </label>
          ))}
          <label className="in-knob in-knob-dedup" title={t("§8: jede Firma nur im höchstpriorisierten Segment; weitere Zugehörigkeiten als auch-Tags")}>
            <span>{t("§8 Einmalzuordnung")}</span>
            <input type="checkbox" checked={dedup} onChange={(e) => { setDedup(e.target.checked); runSegment(segMode, segParams, e.target.checked); }} />
          </label>
          <button className="in-knob-apply" disabled={loading} onClick={() => runSegment(segMode, segParams)}>{t("Anwenden")}</button>
          <button className="in-knob-reset" onClick={() => runSegment(segMode)}>{t("Zurücksetzen")}</button>
        </div>
      )}

      {err && <div className="in-err">{t(err)}</div>}
      {firmen && firmen.length === 0 && <div className="in-empty">{t("Keine Firmen gefunden.")}</div>}

      {firmen && firmen.length > 0 && (
        <div className="in-bar">
          <div className="in-chips">
            {!segMode && <>
              <button className={`in-chip ${filter === "" ? "on" : ""}`} onClick={() => setFilter("")}>{t("Alle {n}", { n: firmen.length })}</button>
              <button className={`in-chip ${filter === "s2" ? "on" : ""}`} onClick={() => setFilter((f) => f === "s2" ? "" : "s2")}>{t("◷ Auslauf {n}", { n: firmen.filter((f) => f.s2.n > 0).length })}</button>
              <button className={`in-chip ${filter === "s1" ? "on" : ""}`} onClick={() => setFilter((f) => f === "s1" ? "" : "s1")}>{t("▼ Verlust {n}", { n: firmen.filter((f) => f.s1.n > 0).length })}</button>
              <button className={`in-chip ${filter === "aktiv" ? "on" : ""}`} onClick={() => setFilter((f) => f === "aktiv" ? "" : "aktiv")} title={t("≥4 Zuschläge/Jahr")}>{t("⚡ aktiv {n}", { n: firmen.filter((f) => f.wins36 >= AKTIV_MIN).length })}</button>
              <button className={`in-chip ${filter === "offen" ? "on" : ""}`} onClick={() => setFilter((f) => f === "offen" ? "" : "offen")}>{t("nicht angesprochen {n}", { n: firmen.filter((f) => !contacted.has(f.id)).length })}</button>
            </>}
            {segMode && (
              <label className="in-sortlabel">{t("Sortieren:")}
                <select className="in-sort" value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)}>
                  <option value="metric">{t("Signalstärke")}</option>
                  <option value="rahmen">{t("Rahmen-Quote")}</option>
                  <option value="wert">{t("Median-Wert")}</option>
                  <option value="name">{t("Name (A bis Z)")}</option>
                  <option value="sitz">{t("PLZ / Sitz")}</option>
                </select>
              </label>
            )}
          </div>
          <button className="in-csv" onClick={exportCsv}>CSV ↓</button>
        </div>
      )}
      {firmen && firmen.length > 0 && (
        <div className="in-count">
          {segMode
           ? `${firmen.length} ${t("Treffer")} — ${t(SEGS.find((s) => s.key === segMode)?.tab || segMode)} (${segGeo ? `${t("Sitz")} ${segGeo}` : t("deutschlandweit")}${firmen.length >= 100 ? ", Top 100" : ""})`
           : t("{sichtbar} von {gesamt} Firmen, nach Schmerz-Volumen sortiert", { sichtbar: visible.length, gesamt: firmen.length })}
        </div>
      )}
      <div className="in-list">
        {shown.map((f) => (
          <div key={f.id} className={`in-card ${openId === f.id ? "open" : ""}`}>
            <button className="in-row" onClick={() => toggle(f.id)}>
              <div className="in-main">
                <span className="in-name">{f.name}{(contacted.has(f.id) || cooldown[f.id]) && <span className="in-done">{cooldown[f.id] ? `🔒 ${cooldown[f.id]}` : t("✓ angesprochen")}</span>}</span>
                {f.badge
                  ? <span className="in-sub">{[f.plz, f.ort].filter(Boolean).join(" ") || t("Sitz unbekannt")}{f.line ? ` · ${f.line}` : ""}</span>
                  : <span className="in-sub">{[f.plz, f.ort].filter(Boolean).join(" ") || t("Sitz unbekannt")} · {t("≈{n} Zuschläge/Jahr · Median {wert}", { n: perJahr(f.wins36), wert: eur(f.medWert) })}</span>}
                {(segMode && (f.rahmenQuote != null || (f.weitere?.length ?? 0) > 0)) && (
                  <span className="in-weitere">
                    {f.rahmenQuote != null && <span className="in-rqtag" title={t("Anteil wiederkehrender/Rahmenverträge am Auftragsvolumen (36 Monate)")}>🔁 {t("{pct}% Rahmen", { pct: f.rahmenQuote })}</span>}
                    {(f.weitere?.length ?? 0) > 0 && <>{t("auch:")} {f.weitere!.map((wg) => <span key={wg.key} className="in-wtag">{t(wg.label)}</span>)}</>}
                  </span>
                )}
              </div>
              <div className="in-signals">
                {f.badge
                  ? <span className={`in-sig ${f.badge.cls}`}>{t(f.badge.label)}{f.badge.spark ? <> <span className="in-spark">{f.badge.spark}</span></> : null}</span>
                  : <>
                    {f.s1.n > 0 && <span className="in-sig s1" title={t("verlorene Verträge (letzter {datum})", { datum: f.s1.letzter ?? "?" })}>{t("▼ {n} verloren · {wert}", { n: f.s1.n, wert: eur(f.s1.vol) })}</span>}
                    {f.s2.n > 0 && <span className="in-sig s2" title={t("nächstes Ende {datum}", { datum: f.s2.naechstes ?? "?" })}>{t("◷ {n} laufen aus · {wert}", { n: f.s2.n, wert: eur(f.s2.vol) })}</span>}
                    {f.s1.n === 0 && f.s2.n === 0 && (f.wins36 >= AKTIV_MIN
                      ? <span className="in-sig aktiv" title={t("aktiv, aber kein frischer Verlust und nichts läuft in 6 bis 18 Monaten aus")}>{t("⚡ aktiv · ≈{n}/Jahr", { n: perJahr(f.wins36) })}</span>
                      : <span className="in-sig none" title={t("kein frischer Verlust, kein Vertrag läuft in 6 bis 18 Monaten aus, die Firma kann trotzdem laufende Aufträge halten")}>{t("ruhig")}</span>)}
                  </>}
              </div>
            </button>

            {openId === f.id && (
              <div className="in-detail">
                {detailLoading && <div className="in-muted">{t("Lade Ansprache-Details …")}</div>}
                {detail && !detailLoading && (detail.error ? <div className="in-err">{t(detail.error)}</div> : (
                  <>
                    {(detail.segment || detail.kmu || detail.website) && (
                      <div className="in-ctx">
                        {detail.kmu && <span className="in-kmu">{t("KMU")}</span>}
                        {detail.segment && <span className="in-seg">{detail.segment.length > 60 ? detail.segment.slice(0, 59) + "…" : detail.segment}</span>}
                        {detail.website && <a className="in-link" href={detail.website.startsWith("http") ? detail.website : `https://${detail.website}`} target="_blank" rel="noreferrer">{t("Website ↗")}</a>}
                      </div>
                    )}
                    <div className="in-contact">
                      {f.phone && <span>☎ {f.phone}</span>}
                      {f.email && <span>✉ {f.email}</span>}
                      <a className="in-link" href={`/firma?id=${encodeURIComponent(f.id)}&from=intern`}>{t("Vollständiges Firmenprofil →")}</a>
                      {cooldown[f.id]
                        ? <span className="in-locked" title={t("12-Monats-Sperre, segmentübergreifend keine Doppelansprache")}>🔒 {t("angesprochen {datum}", { datum: cooldown[f.id] })}</span>
                        : <span className="in-logbtns">
                            <span className="in-logl">{t("protokollieren:")}</span>
                            {(["angesprochen", "interessiert", "gewonnen", "kein_interesse"] as const).map((oc) => (
                              <button key={oc} className="in-logbtn" onClick={() => logOutreach(f, oc)}>{t(oc === "kein_interesse" ? "kein Interesse" : oc)}</button>
                            ))}
                          </span>}
                      {landing[f.id]?.url
                        ? <a className="in-link" href={landing[f.id].url} target="_blank" rel="noreferrer">{landing[f.id].copied ? t("Landing-Link kopiert ✓, öffnen ↗") : t("Landing öffnen ↗")}</a>
                        : <button className="in-done-btn" disabled={landing[f.id]?.busy} onClick={() => makeLanding(f.id)}>
                            {landing[f.id]?.busy ? t("erzeuge …") : t("Landing erzeugen + Link kopieren")}
                          </button>}
                      <button className={`in-done-btn ${pitchCopied === f.id ? "on" : ""}`} onClick={() => copyPitch(f.id, pitchFor(f, detail))}>
                        {pitchCopied === f.id ? t("Pitch kopiert ✓") : t("Pitch kopieren")}
                      </button>
                      <span className="in-note">{t("Kontakt aus Bekanntmachung, vor Nutzung prüfen (oft Vergabeportal statt Firma).")}</span>
                    </div>

                    <textarea className="in-notiz" placeholder={t("Notiz zu dieser Firma (nur lokal gespeichert)…")}
                      value={notes[f.id] || ""} onChange={(e) => setNote(f.id, e.target.value)} rows={2} />

                    {(detail.topBuyers?.length ?? 0) > 0 && (
                      <div className="in-buyers">
                        <span className="in-bl">{t("Schlüsselkunden:")}</span>
                        {detail.topBuyers!.map((b, i) => (
                          <span key={i} className="in-btag">{b.name} <em>{b.wins}×{b.letztes ? ` · ${t("zuletzt {jahr}", { jahr: b.letztes })}` : ""}</em></span>
                        ))}
                      </div>
                    )}

                    {/* Gesprächsaufhänger: laufende Verträge, die demnächst enden (Amtsinhaber-Position) */}
                    {detail.expiring.length > 0 && <div className="in-block">
                      <h3>{t("◷ Läuft aus. Gesprächsaufhänger")} <span className="in-h3n">{detail.expiring.length}</span></h3>
                      {(() => {
                        const total = detail.expiring.reduce((s, e) => s + (e.vol || 0), 0);
                        const rahmen = detail.expiring.filter((e) => e.artcat === "rahmen").reduce((s, e) => s + (e.vol || 0), 0);
                        return total > 0 ? (
                          <div className="in-rq" title={t("Anteil Rahmen-/wiederkehrende Verträge am auslaufenden Volumen, wiederkehrend = wird neu ausgeschrieben")}>
                            {t("Auslaufendes Volumen {wert} · davon", { wert: eur(total) })} <strong>{t("{pct}% Rahmen/wiederkehrend", { pct: Math.round(rahmen / total * 100) })}</strong>
                          </div>
                        ) : null;
                      })()}
                      {detail.expiring.slice(0, 5).map((e, i) => (
                        <div key={i} className="in-item">
                          <span className="in-it"><Titel text={e.titel} url={e.url} art={e.art} artcat={e.artcat} />
                            <span className="in-buyer">{e.buyer}{e.seit ? ` · ${t("hält seit {jahr}", { jahr: e.seit })}` : ""}</span></span>
                          <span className="in-iv">{eur(e.vol)}{e.vsrc && e.vsrc !== "actual" ? " *" : ""} · {t("Ende")} {e.ende ?? "?"}</span>
                        </div>
                      ))}
                      {detail.expiring.length > 5 && <div className="in-more">{t("+{n} weitere", { n: detail.expiring.length - 5 })}</div>}
                    </div>}

                    {/* Chancen: offene Ausschreibungen in ihrem Kern-Fachgebiet */}
                    {(detail.leads?.length ?? 0) > 0 && <div className="in-block in-leads">
                      <h3>{t("▸ Passende offene Ausschreibungen")} <span className="in-h3n">{t("Top {n}", { n: detail.leads!.length })}</span>
                        {detail.leadsScope && <span className="in-scope"> · {detail.leadsScope}</span>}</h3>
                      {detail.leads!.map((l, i) => (
                        <div key={i} className="in-item">
                          <span className="in-it"><Titel text={l.titel} url={l.url} art={l.art} artcat={l.artcat} />
                            {l.ted && <span className="in-tedmark" title={t("Titel-Link führt zur TED-Bekanntmachung")}>TED</span>}
                            {l.doku && l.doku !== l.url && <a className="in-srclink" href={l.doku} target="_blank" rel="noreferrer" title={t("Vergabeunterlagen ansehen")}>{t("Doku ↗")}</a>}
                            <span className="in-buyer">{l.seg ? `${l.seg} · ` : ""}{l.buyer || ""}{l.ort ? ` · ${l.ort}` : ""}{l.dist != null ? ` · ${l.dist} km` : ""}</span></span>
                          <span className="in-iv">{eur(l.vol)} · {t("Frist")} {l.frist ?? "?"}{l.tage != null ? ` (${l.tage} T)` : ""}</span>
                        </div>
                      ))}
                    </div>}

                    {(detail.recent?.length ?? 0) > 0 && <div className="in-block">
                      <h3>{t("Zuletzt gewonnen")} <span className="in-h3n">{detail.recent!.length}</span></h3>
                      {detail.recent!.slice(0, 5).map((r, i) => (
                        <div key={i} className="in-item">
                          <span className="in-it"><Titel text={r.titel} url={r.url} /><span className="in-buyer">{r.buyer || ""}</span></span>
                          <span className="in-iv">{eur(r.vol)}{r.jahr ? ` · ${r.jahr}` : ""}</span>
                        </div>
                      ))}
                    </div>}

                    {detail.losses.length > 0 && <div className="in-block">
                      <h3>{t("▼ Jüngst verloren")} <span className="in-h3n">{detail.losses.length}</span></h3>
                      {detail.losses.slice(0, 5).map((l, i) => (
                        <div key={i} className="in-item">
                          <span className="in-it">{l.titel || t("(ohne Titel)")}</span>
                          <span className="in-iv">{eur(l.vol)} · {t("an {gewinner}", { gewinner: l.gewinner || "?" })} · {l.datum?.slice(0, 7)}</span>
                        </div>
                      ))}
                    </div>}

                    {detail.wettbewerber && detail.wettbewerber.expiring.length > 0 && <div className="in-block">
                      <h3>{detail.wettbewerber.basis === "head_to_head" ? t("Hauptwettbewerber") : t("Größter Anbieter im Feld")}: {detail.wettbewerber.name.split(" ").slice(0, 4).join(" ")}
                        <span className="in-scope"> · {detail.wettbewerber.basis === "head_to_head" ? t("hat die Firma verdrängt") : detail.wettbewerber.basis === "region" ? t("gleiche Region, Proxy") : t("bundesweit, Proxy")}</span> — {t("läuft aus")} <span className="in-h3n">{detail.wettbewerber.expiring.length}</span>
                        {" "}<a className="in-link" href={`/firma?id=${encodeURIComponent(detail.wettbewerber.id)}&from=intern`}>{t("Profil →")}</a></h3>
                      {detail.wettbewerber.expiring.slice(0, 5).map((e, i) => (
                        <div key={i} className="in-item">
                          <span className="in-it"><Titel text={e.titel} url={e.url} art={e.art} artcat={e.artcat} /><span className="in-buyer">{e.buyer}</span></span>
                          <span className="in-iv">{eur(e.vol)} · {t("Ende")} {e.ende ?? "?"}</span>
                        </div>
                      ))}
                    </div>}

                    {detail.losses.length === 0 && detail.expiring.length === 0 && (detail.recent?.length ?? 0) === 0 && (detail.leads?.length ?? 0) === 0 &&
                      <div className="in-muted">{t("Keine Vertragsdaten erfasst.")}</div>}

                    {/* Legende: erklärt die Vertragsart-Labels + den Schätz-Marker einmal zentral */}
                    <div className="in-legende">
                      <span><span className="in-art rahmen">{t("Rahmen")}</span> {t("wird neu ausgeschrieben, lohnt Dranbleiben")}</span>
                      <span><span className="in-art einmal">{t("Einmal")}</span> {t("einmalige Leistung, danach erledigt")}</span>
                      <span><span className="in-art neutral">{t("Einzel")}</span> {t("Vergabeart unbestimmt")}</span>
                      <span className="in-legende-star">{t("* Wert geschätzt (CPV-Median), nicht veröffentlicht")}</span>
                    </div>
                  </>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
