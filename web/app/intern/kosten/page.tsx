"use client";
/**
 * LLM & Kosten (Admin-Portal, Bereich 6). Live-Guthaben, Reserve/Halt, Analyse-Rückstau,
 * Ausgaben je Modell/Zweck. Quelle: /api/intern/kosten. Middleware sperrt /intern auf istAdmin.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import "../../intern.css";

type Live = { guthaben_usd?: number; total_credits?: number; total_usage?: number; fehler?: string } | null;
type Stand = { erschoepft: boolean; halt: string | null; haltGrund: string | null;
               wartend: number | null; fertig: number | null;
               anbieter: { name: string; modell: string; frei: number }[] } | null;
type Ausgaben = {
  gesamt_usd: number; aufrufe: number; seit: string | null; abgebrochen: number; leer: number;
  je_modell: { name: string; usd: number }[]; je_zweck: { name: string; usd: number }[];
  letzte_tage: { tag: string; usd: number }[];
} | null;

const usd = (n: number | undefined | null) => (n == null ? "—" : n.toLocaleString("de-DE", { style: "currency", currency: "USD" }));

export default function KostenPage() {
  const [live, setLive] = useState<Live>(null);
  const [stand, setStand] = useState<Stand>(null);
  const [aus, setAus] = useState<Ausgaben>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [ts, setTs] = useState(0);

  useEffect(() => {
    let ab = false;
    (async () => {
      try {
        const r = await fetch("/api/intern/kosten", { cache: "no-store" });
        if (ab) return;
        if (r.status === 404) { setFehler("Kein Zugriff — als Admin anmelden (istAdmin)."); return; }
        const j = await r.json();
        setLive(j.live); setStand(j.stand); setAus(j.ausgaben); setFehler(null);
      } catch { if (!ab) setFehler("Laden fehlgeschlagen."); }
    })();
    return () => { ab = true; };
  }, [ts]);

  const bal = live?.guthaben_usd;
  const knapp = bal != null && bal < 5;
  const maxMod = Math.max(...(aus?.je_modell ?? []).map((m) => m.usd), 1);

  return (
    <main className="cp-wrap">
      <header className="cp-top">
        <h1>LLM & Kosten</h1>
        <nav className="cp-nav">
          <Link href="/intern/betrieb">Betrieb</Link>
          <Link href="/intern/konten">Konten</Link>
          <Link href="/intern/qualitaet">Datenqualität</Link>
          <Link href="/intern/kuratierung">Kuratierung</Link>
          <Link href="/intern/vertrieb">Vertrieb</Link>
          <button onClick={() => setTs(Date.now())}>Aktualisieren</button>
        </nav>
      </header>
      {fehler && <p className="cp-hinweis">{fehler}</p>}

      <div className="cp-grid">
        <section className={`cp-karte ${knapp ? "cp-schlecht" : bal != null ? "cp-gut" : ""}`}>
          <h3>OpenRouter-Guthaben (live)</h3>
          {live?.fehler ? <p className="cp-klein">nicht abrufbar: {live.fehler}</p> :
            <>
              <p className="cp-gross">{usd(bal)}</p>
              <p className="cp-klein">{usd(live?.total_usage)} von {usd(live?.total_credits)} verbraucht</p>
              {stand?.haltGrund && <p className="cp-klein">{stand.haltGrund}</p>}
              {stand?.halt && <p className="cp-klein">Halt: {stand.halt}</p>}
            </>}
          <p className="cp-klein"><a href="https://openrouter.ai/credits" target="_blank" rel="noopener">Aufladen ↗</a></p>
        </section>

        <section className={`cp-karte ${stand?.erschoepft ? "cp-schlecht" : ""}`}>
          <h3>Analyse-Rückstau</h3>
          <p className="cp-gross">{stand?.wartend != null ? stand.wartend.toLocaleString("de-DE") : "—"} warten</p>
          <p className="cp-klein">Auswertung {stand?.erschoepft ? "gestoppt" : "läuft"}
            {stand?.fertig != null ? ` · zuletzt ${stand.fertig} fertig` : ""}</p>
          {stand?.anbieter?.map((a) => <p key={a.name} className="cp-klein">Modell: {a.modell} · {a.frei} frei</p>)}
        </section>

        <section className="cp-karte">
          <h3>Ausgaben je Modell</h3>
          <p className="cp-gross">{usd(aus?.gesamt_usd)} gesamt</p>
          <p className="cp-klein">{aus?.aufrufe?.toLocaleString("de-DE") ?? "—"} Aufrufe seit {aus?.seit ?? "—"}
            {aus ? ` · ${aus.abgebrochen} abgebrochen, ${aus.leer} leer` : ""}</p>
          <ul className="qa-bars">{(aus?.je_modell ?? []).map((m) => (
            <li key={m.name}>
              <span className="qa-lbl">{m.name}</span>
              <span className="qa-bar"><i style={{ width: `${Math.max(3, (m.usd / maxMod) * 100)}%` }} /></span>
              <span className="qa-n">{usd(m.usd)}</span>
            </li>
          ))}</ul>
        </section>

        <section className="cp-karte">
          <h3>Ausgaben je Zweck & letzte Tage</h3>
          <ul className="cp-liste">{(aus?.je_zweck ?? []).map((z) =>
            <li key={z.name}>{z.name}: {usd(z.usd)}</li>)}</ul>
          {aus?.letzte_tage?.length ? <>
            <p className="cp-klein" style={{ marginTop: 8 }}>Letzte Tage:</p>
            <ul className="cp-liste">{aus.letzte_tage.slice(-7).map((t) =>
              <li key={t.tag}>{t.tag}: {usd(t.usd)}</li>)}</ul>
          </> : null}
        </section>
      </div>
    </main>
  );
}
