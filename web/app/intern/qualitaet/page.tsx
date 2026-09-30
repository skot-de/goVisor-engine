"use client";
/**
 * Datenqualität (Admin-Portal, Bereich 2). Review-Queue, Quality-Flags, Entity-Merges,
 * Dubletten — aus den Gold-QA-Parquets via /api/intern/qualitaet (Python-Helfer).
 * Middleware sperrt /intern auf istAdmin; ohne Session 404 → Hinweis.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import "../../intern.css";

type FlagN = { flag: string; n: number };
type Daten = {
  country: string; fehler?: string;
  review_queue?: { total: number; flags: FlagN[] };
  quality?: { total: number; mit_flag: number; flags: FlagN[] };
  merge_kandidaten?: number;
  merge_urteile?: { urteil: string; n: number }[];
  notice_dubletten?: { total: number; beleg: { beleg: string; n: number }[] };
  dok_dubletten?: number;
};
const LAENDER = ["DE", "AT", "CH", "LU"];
const nf = (n: number | undefined) => (n ?? 0).toLocaleString("de-DE");

function Balken({ items, max }: { items: FlagN[]; max: number }) {
  return <ul className="qa-bars">{items.map((f) => (
    <li key={f.flag}>
      <span className="qa-lbl">{f.flag}</span>
      <span className="qa-bar"><i style={{ width: `${Math.max(3, (f.n / max) * 100)}%` }} /></span>
      <span className="qa-n">{nf(f.n)}</span>
    </li>
  ))}</ul>;
}

export default function QualitaetPage() {
  const [land, setLand] = useState("DE");
  const [d, setD] = useState<Daten | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [ladet, setLadet] = useState(false);

  useEffect(() => {
    let ab = false;
    setLadet(true);
    (async () => {
      try {
        const r = await fetch(`/api/intern/qualitaet?country=${land}`, { cache: "no-store" });
        if (ab) return;
        if (r.status === 404) { setFehler("Kein Zugriff — als Admin anmelden (istAdmin)."); return; }
        setD(await r.json()); setFehler(null);
      } catch { if (!ab) setFehler("Laden fehlgeschlagen."); }
      finally { if (!ab) setLadet(false); }
    })();
    return () => { ab = true; };
  }, [land]);

  const rq = d?.review_queue; const q = d?.quality;
  const nd = d?.notice_dubletten;

  return (
    <main className="cp-wrap">
      <header className="cp-top">
        <h1>Datenqualität</h1>
        <nav className="cp-nav">
          <Link href="/intern/betrieb">Betrieb</Link>
          <Link href="/intern/konten">Konten</Link>
          <Link href="/intern">Firmen-Radar</Link>
          <select value={land} onChange={(e) => setLand(e.target.value)}>
            {LAENDER.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </nav>
      </header>
      {fehler && <p className="cp-hinweis">{fehler}</p>}
      {ladet && <p className="cp-klein">Lade …</p>}
      {d?.fehler && <p className="cp-hinweis">{d.fehler}</p>}

      <div className="cp-grid">
        <Karte titel="Review-Queue" gross={`${nf(rq?.total)} harte Fehler`}>
          {rq ? <Balken items={rq.flags} max={Math.max(...rq.flags.map((f) => f.n), 1)} />
              : <p className="cp-klein">—</p>}
        </Karte>

        <Karte titel="Quality-Flags (Bestand)"
               gross={q ? `${nf(q.mit_flag)} von ${nf(q.total)} mit Flag` : "—"}>
          {q ? <Balken items={q.flags} max={Math.max(...q.flags.map((f) => f.n), 1)} />
             : <p className="cp-klein">—</p>}
        </Karte>

        <Karte titel="Entity-Zusammenführungen"
               gross={`${nf(d?.merge_kandidaten)} Kandidaten`}>
          {d?.merge_urteile?.length
            ? <ul className="cp-liste">{d.merge_urteile.map((u) =>
                <li key={u.urteil}>{u.urteil}: {nf(u.n)}</li>)}</ul>
            : <p className="cp-klein">keine Urteile</p>}
          <p className="cp-klein">Urteile aus dem Merge-Lauf; „verschieden" = bewusst getrennt.</p>
        </Karte>

        <Karte titel="Dubletten" gross={`${nf(nd?.total)} Notice-Paare`}>
          {nd ? <ul className="cp-liste">{nd.beleg.map((b) =>
              <li key={b.beleg}>{b.beleg}: {nf(b.n)}</li>)}</ul> : <p className="cp-klein">—</p>}
          <p className="cp-klein">Dokument-Paare: {nf(d?.dok_dubletten)}</p>
        </Karte>
      </div>
      <p className="cp-klein" style={{ marginTop: 12 }}>
        Nur Ansicht. Merge bestätigen/ablehnen schreibt nach `curated/` und kommt mit Bereich 5
        (Kuratierung); wirkt dann beim nächsten Gold-Lauf.
      </p>
    </main>
  );
}

function Karte({ titel, gross, children }: { titel: string; gross: string; children: React.ReactNode }) {
  return <section className="cp-karte"><h3>{titel}</h3><p className="cp-gross">{gross}</p>{children}</section>;
}
