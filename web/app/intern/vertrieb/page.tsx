"use client";
/**
 * Vertrieb & Outreach (Admin-Portal, Bereich 4). Zielliste (Schmerz-Priorisierung) +
 * Outreach-Trefferquote/Sperre + Aktionen je Ziel: Landing (/t/<token>) erzeugen, Ansprache
 * loggen (setzt die 12-Monats-Sperre). Quellen: /api/intern/{zielliste,outreach,landing}.
 * Middleware sperrt /intern auf istAdmin. Firmensuche liegt im Firmen-Radar (/intern).
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import "../../intern.css";

type Ziel = Record<string, string | number>;
type Treffer = Record<string, { n: number; quote: number; [k: string]: number }>;
type Aktion = { token?: string; url?: string; fehler?: string; geloggt?: boolean; gesperrt_bis?: string };

const OUTCOMES = ["angesprochen", "interessiert", "gewonnen", "kein_interesse", "kein_kontakt"];
const SIGNALE = ["", "S1_verlust", "S2_auslauf", "S3_ausbeute", "S4_wachstum", "S5_feldbreite"];
const eur = (n: unknown) => (n == null || n === "" ? "—" : Number(n).toLocaleString("de-DE", { maximumFractionDigits: 0 }) + " €");

export default function VertriebPage() {
  const [zeilen, setZeilen] = useState<Ziel[]>([]);
  const [meta, setMeta] = useState<{ gesamt: number; gefiltert: number; fehlt?: boolean; hinweis?: string }>({ gesamt: 0, gefiltert: 0 });
  const [cooldown, setCooldown] = useState<Record<string, string>>({});
  const [treffer, setTreffer] = useState<Treffer>({});
  const [region, setRegion] = useState("");
  const [signal, setSignal] = useState("");
  const [q, setQ] = useState("");
  const [fehler, setFehler] = useState<string | null>(null);
  const [aktion, setAktion] = useState<Record<string, Aktion>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const ladeZiele = useCallback(async () => {
    const p = new URLSearchParams();
    if (region) p.set("region", region);
    if (signal) p.set("signal", signal);
    if (q) p.set("q", q);
    try {
      const r = await fetch(`/api/intern/zielliste?${p}`, { cache: "no-store" });
      if (r.status === 404) { setFehler("Kein Zugriff, als Admin anmelden (istAdmin)."); return; }
      const j = await r.json();
      if (j.error) { setFehler(j.error); return; }
      setZeilen(j.zeilen || []); setMeta({ gesamt: j.gesamt || 0, gefiltert: j.gefiltert || 0, fehlt: j.fehlt, hinweis: j.hinweis });
      setFehler(null);
    } catch { setFehler("Laden fehlgeschlagen."); }
  }, [region, signal, q]);

  const ladeOutreach = useCallback(async () => {
    try {
      const r = await fetch("/api/intern/outreach", { cache: "no-store" });
      if (!r.ok) return;
      const j = await r.json();
      setCooldown(j.cooldown || {}); setTreffer(j.trefferquote || {});
    } catch { /* Outreach ist optional */ }
  }, []);

  useEffect(() => { ladeOutreach(); }, [ladeOutreach]);
  useEffect(() => { const t = setTimeout(ladeZiele, q ? 300 : 0); return () => clearTimeout(t); }, [ladeZiele, q]);

  const landing = async (id: string) => {
    setBusy(id + ":l"); setFehler(null);
    try {
      const r = await fetch(`/api/intern/landing?id=${encodeURIComponent(id)}`, { method: "POST" });
      const j = await r.json();
      setAktion((a) => ({ ...a, [id]: { ...a[id], token: j.token, url: j.url, fehler: r.ok ? undefined : j.error } }));
    } finally { setBusy(null); }
  };

  const loggen = async (id: string, outcome: string) => {
    setBusy(id + ":o"); setFehler(null);
    try {
      const r = await fetch("/api/intern/outreach", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ id, outcome }),
      });
      const j = await r.json();
      if (!r.ok) { setAktion((a) => ({ ...a, [id]: { ...a[id], fehler: j.error } })); return; }
      setAktion((a) => ({ ...a, [id]: { ...a[id], geloggt: true, gesperrt_bis: j.gesperrt_bis } }));
      await ladeOutreach();
    } finally { setBusy(null); }
  };

  const gesamtTreffer = Object.values(treffer).reduce((s, t) => s + (t.n || 0), 0);

  return (
    <main className="cp-wrap">
      <header className="cp-top">
        <h1>Vertrieb & Outreach</h1>
        <nav className="cp-nav">
          <Link href="/intern">Firmen-Radar</Link>
          <Link href="/intern/betrieb">Betrieb</Link>
          <Link href="/intern/konten">Konten</Link>
          <Link href="/intern/qualitaet">Datenqualität</Link>
          <Link href="/intern/kosten">LLM & Kosten</Link>
          <Link href="/intern/kuratierung">Kuratierung</Link>
        </nav>
      </header>
      {fehler && <p className="cp-hinweis">{fehler}</p>}

      <div className="cp-grid">
        <section className="cp-karte">
          <h3>Zielliste</h3>
          <p className="cp-gross">{meta.gefiltert.toLocaleString("de-DE")}</p>
          <p className="cp-klein">von {meta.gesamt.toLocaleString("de-DE")} belegten Zielen (Schmerz-Score)</p>
          {meta.fehlt && <p className="cp-klein">⚠ {meta.hinweis}</p>}
        </section>
        <section className="cp-karte">
          <h3>Outreach</h3>
          <p className="cp-gross">{gesamtTreffer}</p>
          <p className="cp-klein">Ansprachen protokolliert · {Object.keys(cooldown).length} in 12-Monats-Sperre</p>
          {Object.entries(treffer).map(([seg, t]) =>
            <p key={seg} className="cp-klein">Segment {seg}: {t.n} Ansprachen · {t.quote}% positiv</p>)}
        </section>
      </div>

      <div className="ziel-filter">
        <input placeholder="Firma suchen…" value={q} onChange={(e) => setQ(e.target.value)} />
        <input placeholder="Region (NUTS, z.B. DEA)" value={region} onChange={(e) => setRegion(e.target.value)} onBlur={ladeZiele} />
        <select value={signal} onChange={(e) => setSignal(e.target.value)}>
          {SIGNALE.map((s) => <option key={s} value={s}>{s || "Alle Signale"}</option>)}
        </select>
      </div>

      <div className="kur-tabelle">
        <table>
          <thead><tr>
            <th>Firma</th><th>Region</th><th>Score</th><th>Signal</th><th>Zuschl. 36M</th>
            <th>Volumen 36M</th><th>Verlust 12M</th><th>Auslauf 6-18M</th><th>Aktion</th>
          </tr></thead>
          <tbody>
            {zeilen.map((z) => {
              const id = String(z.identity_id);
              const sperre = cooldown[id];
              const a = aktion[id] || {};
              return (
                <tr key={id}>
                  <td title={id}>{String(z.firmenname)}</td>
                  <td>{String(z.haupt_nuts1 || "—")}</td>
                  <td>{String(z.score)}</td>
                  <td>{String(z.dominant_signal || "—")}</td>
                  <td>{String(z.wins36 ?? "—")}</td>
                  <td>{eur(z.volumen_36m)}</td>
                  <td>{z.verlorene_12m ? `${z.verlorene_12m} · ${eur(z.verlust_volumen)}` : "—"}</td>
                  <td>{z.auslauf_n ? `${z.auslauf_n} · ${eur(z.auslauf_volumen_6_18m)}` : "—"}</td>
                  <td className="ziel-aktion">
                    {sperre && !a.geloggt && <span className="ziel-sperre" title={`zuletzt ${sperre}`}>gesperrt</span>}
                    <button disabled={busy === id + ":l"} onClick={() => landing(id)}>Landing</button>
                    <select defaultValue="" disabled={busy === id + ":o"}
                      onChange={(e) => { if (e.target.value) loggen(id, e.target.value); e.currentTarget.value = ""; }}>
                      <option value="">Ansprache…</option>
                      {OUTCOMES.map((o) => <option key={o} value={o}>{o}</option>)}
                    </select>
                    {a.url && <a href={a.url} target="_blank" rel="noopener" className="ziel-link">{a.token}</a>}
                    {a.geloggt && <span className="ziel-ok">geloggt</span>}
                    {a.fehler && <span className="ziel-fehler">{a.fehler}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </main>
  );
}
