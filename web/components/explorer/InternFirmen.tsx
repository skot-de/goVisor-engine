"use client";
import { useState, useEffect, useCallback } from "react";

/* INTERNES Vertriebstool — Firmen nach Sitz/Name suchen → Schmerz-Signale + Ansprache-Details.
 * Enthält Kontaktdaten; die API blockiert Production. Reine Sales-Sicht (kein Kundenprodukt). */

type Sig = { n: number; vol: number | null; letzter?: string | null; naechstes?: string | null };
type Firma = {
  id: string; name: string; plz: string | null; ort: string | null; wins36: number;
  medWert: number | null; vol36: number | null; s1: Sig; s2: Sig; dominant: string;
  email: string | null; phone: string | null;
};
type Exp = { titel: string; buyer: string; vol: number | null; ende: string | null; mte: number | null; vsrc?: string; art?: string | null; url?: string | null; seit?: number | null };
type Loss = { titel: string; vol: number | null; datum: string | null; gewinner: string | null };
type Recent = { titel: string; buyer: string | null; vol: number | null; jahr: number | null; url?: string | null };
type Wett = { name: string; id: string; expiring: Exp[] };
type Buyer = { name: string; wins: number; letztes: number | null };
type Lead = { titel: string; buyer: string | null; ort: string | null; vol: number | null; frist: string | null; tage: number | null; url: string | null };
type Detail = { id: string; name: string; expiring: Exp[]; losses: Loss[]; recent?: Recent[]; wettbewerber?: Wett | null;
  website?: string | null; kmu?: boolean; segment?: string | null; topBuyers?: Buyer[]; leads?: Lead[]; error?: string };

// Vertragstitel als Link zur TED-Bekanntmachung (extern → neuer Tab) + Rahmen/Einmal-Marker.
function Titel({ text, url, art }: { text: string | null; url?: string | null; art?: string | null }) {
  const t = text || "(ohne Titel)";
  const artCls = art === "Rahmen" || art === "wiederkehrend" ? "in-art rahmen" : art === "Einmalauftrag" ? "in-art einmal" : "";
  return (
    <>
      {url ? <a className="in-tlink" href={url} target="_blank" rel="noreferrer">{t} ↗</a> : t}
      {art && <span className={artCls}>{art}</span>}
    </>
  );
}

const nf = new Intl.NumberFormat("de-DE");
const eur = (v: number | null | undefined) =>
  v == null ? "—" : v >= 1e6 ? (v / 1e6).toFixed(1).replace(".", ",") + " Mio €"
  : nf.format(Math.round(v)) + " €";

export function InternFirmen() {
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
  const [filter, setFilter] = useState<"" | "s1" | "s2" | "offen">(""); // Schnellfilter

  useEffect(() => {
    try { setContacted(new Set(JSON.parse(localStorage.getItem("govisor.outreach") || "[]"))); } catch { /* ignore */ }
    try { setNotes(JSON.parse(localStorage.getItem("govisor.notes") || "{}")); } catch { /* ignore */ }
  }, []);

  function setNote(id: string, text: string) {
    setNotes((prev) => {
      const n = { ...prev, [id]: text };
      if (!text) delete n[id];
      try { localStorage.setItem("govisor.notes", JSON.stringify(n)); } catch { /* ignore */ }
      return n;
    });
  }

  function toggleContacted(id: string) {
    setContacted((prev) => {
      const s = new Set(prev);
      if (s.has(id)) s.delete(id); else s.add(id);
      try { localStorage.setItem("govisor.outreach", JSON.stringify([...s])); } catch { /* ignore */ }
      return s;
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
    runSearch(plz.trim(), ort.trim(), name.trim(), radius);
  }

  // Beim Laden (auch nach Zurück) die Suche aus der URL wiederherstellen
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const p = sp.get("plz") || "", o = sp.get("ort") || "", n = sp.get("name") || "", rad = sp.get("radius") || "";
    if (p || o || n) { setPlz(p); setOrt(o); setName(n); setRadius(rad); runSearch(p, o, n, rad); }
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

  // Schnellfilter auf die Trefferliste (Signal-basiert, clientseitig)
  const visible = (firmen || []).filter((f) =>
    filter === "s1" ? f.s1.n > 0 : filter === "s2" ? f.s2.n > 0 : filter === "offen" ? !contacted.has(f.id) : true
  );

  // (2) Pitch-Zeile: kopierfertiger Einzeiler aus den Schmerz-Signalen der Firma
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

  // (5) CSV-Export der aktuell sichtbaren Trefferliste (inkl. Notizen + Status)
  function exportCsv() {
    const head = ["Firma", "PLZ", "Ort", "Zuschläge36M", "MedianWert", "verloren_n", "verloren_vol", "auslauf_n", "auslauf_vol", "Telefon", "Email", "angesprochen", "Notiz"];
    const q = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const rows = visible.map((f) => [f.name, f.plz, f.ort, f.wins36, f.medWert, f.s1.n, f.s1.vol, f.s2.n, f.s2.vol, f.phone, f.email, contacted.has(f.id) ? "ja" : "", notes[f.id] || ""].map(q).join(";"));
    const csv = "﻿" + [head.map(q).join(";"), ...rows].join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url; a.download = "firmen-radar.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="in-wrap">
      <div className="in-head">
        <h1>Firmen-Radar <span className="in-tag">intern</span></h1>
        <p>Zielfirmen nach Sitz oder Name — mit Schmerz-Signalen (verlorene &amp; auslaufende Verträge) für die Erstansprache.
          Enthält Kontaktdaten aus öffentlichen Bekanntmachungen; nur intern.</p>
      </div>

      <form className="in-search" onSubmit={search}>
        <input placeholder="PLZ (z. B. 59071)" value={plz} onChange={(e) => setPlz(e.target.value)} inputMode="numeric" />
        <select className="in-radius" value={radius} onChange={(e) => setRadius(e.target.value)} disabled={!plz} title="Umkreis um die PLZ">
          <option value="">exakt</option>
          <option value="5">+5 km</option>
          <option value="10">+10 km</option>
          <option value="25">+25 km</option>
          <option value="50">+50 km</option>
        </select>
        <input placeholder="Ort (z. B. Hamm)" value={ort} onChange={(e) => setOrt(e.target.value)} />
        <input placeholder="Firmenname (z. B. Klostermann)" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit" disabled={loading}>{loading ? "Suche …" : "Suchen"}</button>
      </form>

      {err && <div className="in-err">{err}</div>}
      {firmen && firmen.length === 0 && <div className="in-empty">Keine Firmen gefunden.</div>}

      {firmen && firmen.length > 0 && (
        <div className="in-bar">
          <div className="in-chips">
            <button className={`in-chip ${filter === "" ? "on" : ""}`} onClick={() => setFilter("")}>Alle {firmen.length}</button>
            <button className={`in-chip ${filter === "s2" ? "on" : ""}`} onClick={() => setFilter((f) => f === "s2" ? "" : "s2")}>◷ Auslauf {firmen.filter((f) => f.s2.n > 0).length}</button>
            <button className={`in-chip ${filter === "s1" ? "on" : ""}`} onClick={() => setFilter((f) => f === "s1" ? "" : "s1")}>▼ Verlust {firmen.filter((f) => f.s1.n > 0).length}</button>
            <button className={`in-chip ${filter === "offen" ? "on" : ""}`} onClick={() => setFilter((f) => f === "offen" ? "" : "offen")}>nicht angesprochen {firmen.filter((f) => !contacted.has(f.id)).length}</button>
          </div>
          <button className="in-csv" onClick={exportCsv}>CSV ↓</button>
        </div>
      )}
      {firmen && firmen.length > 0 && (
        <div className="in-count">{visible.length} von {firmen.length} Firmen — nach Schmerz-Volumen sortiert</div>
      )}
      <div className="in-list">
        {visible.map((f) => (
          <div key={f.id} className={`in-card ${openId === f.id ? "open" : ""}`}>
            <button className="in-row" onClick={() => toggle(f.id)}>
              <div className="in-main">
                <span className="in-name">{f.name}{contacted.has(f.id) && <span className="in-done">✓ angesprochen</span>}</span>
                <span className="in-sub">{[f.plz, f.ort].filter(Boolean).join(" ") || "Sitz unbekannt"} · {f.wins36} Zuschläge/36M · Median {eur(f.medWert)}</span>
              </div>
              <div className="in-signals">
                {f.s1.n > 0 && <span className="in-sig s1" title={`verlorene Verträge (letzter ${f.s1.letzter ?? "?"})`}>▼ {f.s1.n} verloren · {eur(f.s1.vol)}</span>}
                {f.s2.n > 0 && <span className="in-sig s2" title={`nächstes Ende ${f.s2.naechstes ?? "?"}`}>◷ {f.s2.n} laufen aus · {eur(f.s2.vol)}</span>}
                {f.s1.n === 0 && f.s2.n === 0 && <span className="in-sig none">kein akutes Signal</span>}
              </div>
            </button>

            {openId === f.id && (
              <div className="in-detail">
                {detailLoading && <div className="in-muted">Lade Ansprache-Details …</div>}
                {detail && !detailLoading && (detail.error ? <div className="in-err">{detail.error}</div> : (
                  <>
                    {(detail.segment || detail.kmu || detail.website) && (
                      <div className="in-ctx">
                        {detail.kmu && <span className="in-kmu">KMU</span>}
                        {detail.segment && <span className="in-seg">{detail.segment.length > 60 ? detail.segment.slice(0, 59) + "…" : detail.segment}</span>}
                        {detail.website && <a className="in-link" href={detail.website.startsWith("http") ? detail.website : `https://${detail.website}`} target="_blank" rel="noreferrer">Website ↗</a>}
                      </div>
                    )}
                    <div className="in-contact">
                      {f.phone && <span>☎ {f.phone}</span>}
                      {f.email && <span>✉ {f.email}</span>}
                      <a className="in-link" href={`/firma?id=${encodeURIComponent(f.id)}&from=intern`}>Vollständiges Firmenprofil →</a>
                      <button className={`in-done-btn ${contacted.has(f.id) ? "on" : ""}`} onClick={() => toggleContacted(f.id)}>
                        {contacted.has(f.id) ? "✓ angesprochen" : "Als angesprochen markieren"}
                      </button>
                      {landing[f.id]?.url
                        ? <a className="in-link" href={landing[f.id].url} target="_blank" rel="noreferrer">{landing[f.id].copied ? "Landing-Link kopiert ✓ — öffnen ↗" : "Landing öffnen ↗"}</a>
                        : <button className="in-done-btn" disabled={landing[f.id]?.busy} onClick={() => makeLanding(f.id)}>
                            {landing[f.id]?.busy ? "erzeuge …" : "Landing erzeugen + Link kopieren"}
                          </button>}
                      <button className={`in-done-btn ${pitchCopied === f.id ? "on" : ""}`} onClick={() => copyPitch(f.id, pitchFor(f, detail))}>
                        {pitchCopied === f.id ? "Pitch kopiert ✓" : "Pitch kopieren"}
                      </button>
                      <span className="in-note">Kontakt aus Bekanntmachung — vor Nutzung prüfen (oft Vergabeportal statt Firma).</span>
                    </div>

                    <textarea className="in-notiz" placeholder="Notiz zu dieser Firma (nur lokal gespeichert)…"
                      value={notes[f.id] || ""} onChange={(e) => setNote(f.id, e.target.value)} rows={2} />

                    {(detail.topBuyers?.length ?? 0) > 0 && (
                      <div className="in-buyers">
                        <span className="in-bl">Schlüsselkunden:</span>
                        {detail.topBuyers!.map((b, i) => (
                          <span key={i} className="in-btag">{b.name} <em>{b.wins}×{b.letztes ? ` · zuletzt ${b.letztes}` : ""}</em></span>
                        ))}
                      </div>
                    )}

                    {detail.losses.length > 0 && <div className="in-block">
                      <h3>Jüngst verloren ({detail.losses.length})</h3>
                      {detail.losses.slice(0, 8).map((l, i) => (
                        <div key={i} className="in-item">
                          <span className="in-it">{l.titel || "(ohne Titel)"}</span>
                          <span className="in-iv">{eur(l.vol)} · an {l.gewinner || "?"} · {l.datum?.slice(0, 7)}</span>
                        </div>
                      ))}
                    </div>}

                    {detail.expiring.length > 0 && <div className="in-block">
                      <h3>Läuft aus — Gesprächsaufhänger ({detail.expiring.length})</h3>
                      {detail.expiring.slice(0, 12).map((e, i) => (
                        <div key={i} className="in-item">
                          <span className="in-it"><Titel text={e.titel} url={e.url} art={e.art} />
                            <span className="in-buyer">{e.buyer}{e.seit ? ` · hält seit ${e.seit}` : ""}</span></span>
                          <span className="in-iv">{eur(e.vol)}{e.vsrc && e.vsrc !== "actual" ? " *" : ""} · Ende {e.ende ?? "?"}</span>
                        </div>
                      ))}
                      {detail.expiring.some((e) => e.vsrc && e.vsrc !== "actual") &&
                        <div className="in-legend">* Wert geschätzt/aus CPV-Median abgeleitet — nicht veröffentlicht.</div>}
                    </div>}

                    {detail.wettbewerber && detail.wettbewerber.expiring.length > 0 && <div className="in-block">
                      <h3>Hauptwettbewerber: {detail.wettbewerber.name.split(" ").slice(0, 4).join(" ")} — was bei ihm ausläuft ({detail.wettbewerber.expiring.length})
                        {" "}<a className="in-link" href={`/firma?id=${encodeURIComponent(detail.wettbewerber.id)}&from=intern`}>Profil →</a></h3>
                      {detail.wettbewerber.expiring.slice(0, 8).map((e, i) => (
                        <div key={i} className="in-item">
                          <span className="in-it"><Titel text={e.titel} url={e.url} art={e.art} /><span className="in-buyer">{e.buyer}</span></span>
                          <span className="in-iv">{eur(e.vol)} · Ende {e.ende ?? "?"}</span>
                        </div>
                      ))}
                    </div>}

                    {(detail.leads?.length ?? 0) > 0 && <div className="in-block in-leads">
                      <h3>▸ Passende offene Ausschreibungen — Top {detail.leads!.length}</h3>
                      {detail.leads!.map((l, i) => (
                        <div key={i} className="in-item">
                          <span className="in-it"><Titel text={l.titel} url={l.url} /><span className="in-buyer">{l.buyer || ""}{l.ort ? ` · ${l.ort}` : ""}</span></span>
                          <span className="in-iv">{eur(l.vol)} · Frist {l.frist ?? "?"}{l.tage != null ? ` (${l.tage} T)` : ""}</span>
                        </div>
                      ))}
                    </div>}

                    {(detail.recent?.length ?? 0) > 0 && <div className="in-block">
                      <h3>Zuletzt gewonnen ({detail.recent!.length})</h3>
                      {detail.recent!.slice(0, 8).map((r, i) => (
                        <div key={i} className="in-item">
                          <span className="in-it"><Titel text={r.titel} url={r.url} /><span className="in-buyer">{r.buyer || ""}</span></span>
                          <span className="in-iv">{eur(r.vol)}{r.jahr ? ` · ${r.jahr}` : ""}</span>
                        </div>
                      ))}
                    </div>}

                    {detail.losses.length === 0 && detail.expiring.length === 0 && (detail.recent?.length ?? 0) === 0 && (detail.leads?.length ?? 0) === 0 &&
                      <div className="in-muted">Keine Vertragsdaten erfasst.</div>}
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
