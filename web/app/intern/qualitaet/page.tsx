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
type MergeRow = {
  entity_a: string; entity_b: string; name_a: string; name_b: string;
  urteil: string; einig: boolean; regel_grund: string; kandidaten: number;
  entschieden: string | null;
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

  const [merges, setMerges] = useState<MergeRow[] | null>(null);
  const [mergeMeta, setMergeMeta] = useState<{ gesamt: number; entschieden_n: number }>({ gesamt: 0, entschieden_n: 0 });
  const [mergeBusy, setMergeBusy] = useState<string | null>(null);

  const ladeMerges = async () => {
    setMerges(null);
    try {
      const r = await fetch(`/api/intern/qualitaet?country=${land}&merges=150`, { cache: "no-store" });
      if (!r.ok) { setFehler("Merge-Liste nicht ladbar."); return; }
      const j = await r.json();
      if (j.fehler) { setFehler(j.fehler); return; }
      setMerges(j.merge_liste || []); setMergeMeta({ gesamt: j.gesamt || 0, entschieden_n: j.entschieden_n || 0 });
    } catch { setFehler("Merge-Liste nicht ladbar."); }
  };

  const entscheide = async (row: MergeRow, entscheidung: "gleich" | "verschieden") => {
    const key = row.entity_a + "|" + row.entity_b;
    setMergeBusy(key); setFehler(null);
    try {
      const r = await fetch("/api/intern/kuratierung", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          kind: "entity_merge_entscheidung", country: land, action: "append",
          row: { entity_a: row.entity_a, entity_b: row.entity_b, entscheidung,
                 name_a: row.name_a, name_b: (row.name_b || "").split("|")[0].trim(),
                 grund: `Admin-Entscheid (LLM: ${row.urteil}${row.einig ? ", einig" : ""})` },
        }),
      });
      const j = await r.json();
      if (!r.ok) { setFehler(j.error || "Speichern fehlgeschlagen."); return; }
      setMerges((cur) => cur?.map((m) =>
        m.entity_a === row.entity_a && m.entity_b === row.entity_b ? { ...m, entschieden: entscheidung } : m) ?? cur);
      setMergeMeta((mm) => ({ ...mm, entschieden_n: mm.entschieden_n + 1 }));
    } finally { setMergeBusy(null); }
  };

  return (
    <main className="cp-wrap">
      <header className="cp-top">
        <h1>Datenqualität</h1>
        <nav className="cp-nav">
          <Link href="/intern">Firmen-Radar</Link>
          <Link href="/intern/betrieb">Betrieb</Link>
          <Link href="/intern/konten">Konten</Link>
          <Link href="/intern/kosten">LLM & Kosten</Link>
          <Link href="/intern/kuratierung">Kuratierung</Link>
          <Link href="/intern/vertrieb">Vertrieb</Link>
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
          <button className="qa-mergebtn" onClick={ladeMerges}>Kandidaten prüfen & entscheiden</button>
        </Karte>

        <Karte titel="Dubletten" gross={`${nf(nd?.total)} Notice-Paare`}>
          {nd ? <ul className="cp-liste">{nd.beleg.map((b) =>
              <li key={b.beleg}>{b.beleg}: {nf(b.n)}</li>)}</ul> : <p className="cp-klein">—</p>}
          <p className="cp-klein">Dokument-Paare: {nf(d?.dok_dubletten)}</p>
        </Karte>
      </div>
      {merges && (
        <section style={{ marginTop: 16 }}>
          <h3>Merge-Kandidaten entscheiden</h3>
          <p className="cp-klein">
            {mergeMeta.entschieden_n} von {nf(mergeMeta.gesamt)} entschieden · unklare zuerst.
            „gleich" verschmilzt (schlägt die LLM-Richter), „verschieden" trennt bewusst.
            Wirkt beim nächsten <code>entity_merge_anwenden</code>-Lauf + Gold-Rebuild — Gold wird hier nicht angefasst.
          </p>
          <div className="kur-tabelle">
            <table>
              <thead><tr>
                <th>Name (nur Name)</th><th>Kandidat</th><th>LLM</th><th>Grund</th><th>Aktion</th>
              </tr></thead>
              <tbody>
                {merges.map((m) => {
                  const key = m.entity_a + "|" + m.entity_b;
                  return (
                    <tr key={key}>
                      <td title={m.entity_a}>{m.name_a}</td>
                      <td title={m.entity_b}>{(m.name_b || "").split("|")[0].trim()}</td>
                      <td>{m.urteil}{m.einig ? " ✓" : " ✗"}</td>
                      <td>{m.regel_grund}</td>
                      <td className="ziel-aktion">
                        {m.entschieden
                          ? <span className={m.entschieden === "gleich" ? "ziel-ok" : "ziel-sperre"}>{m.entschieden}</span>
                          : <>
                              <button disabled={mergeBusy === key} onClick={() => entscheide(m, "gleich")}>gleich</button>
                              <button className="kur-del" disabled={mergeBusy === key} onClick={() => entscheide(m, "verschieden")}>verschieden</button>
                            </>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <p className="cp-klein" style={{ marginTop: 12 }}>
        Ansicht plus Merge-Entscheid. Entscheidungen landen versioniert in
        `curated/&lt;L&gt;_entity_merge_entscheidung.csv` (auch in Bereich 5 sichtbar) und
        fließen beim nächsten Merge-Lauf ein.
      </p>
    </main>
  );
}

function Karte({ titel, gross, children }: { titel: string; gross: string; children: React.ReactNode }) {
  return <section className="cp-karte"><h3>{titel}</h3><p className="cp-gross">{gross}</p>{children}</section>;
}
