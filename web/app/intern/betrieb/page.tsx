"use client";
/**
 * Betriebs-Cockpit (Admin-Portal, Bereich 1). Insights + Troubleshooting an EINER Stelle:
 * Nachtlauf, Sonden-Ampel, LLM-Guthaben, Bestand, Dokument-Trichter, Datenqualitaet.
 *
 * Quellen: /api/intern/lauf (Lauf/Ertrag/Dokumente/Qualitaet) + /api/intern/betrieb
 * (Sonden + Guthaben). Beide sind ueber die Middleware auf Admins gesperrt (istAdmin);
 * ohne Session liefern sie 404 — dann zeigt die Seite einen Hinweis statt leerer Kacheln.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import "../../intern.css";

type Lauf = {
  ertrag?: { bestand?: Record<string, number> } | null;
  lauf?: { datum: string | null; ergebnis: string; dauerSek: number | null;
           alterStunden: number | null; letzterSchritt: string | null; fehlerZeilen: string[] };
  fortschritt?: { anteil: number; verbleibendSek: number | null };
  dokumente?: {
    aufPlatte: number; indiziert: number | null; rueckstand: number | null;
    trichter?: { volltext: number | null; analyse: number | null; ohneAnalyse: number | null };
    arbeiter?: { laeuft: boolean; letzte: string[] };
    qualitaet?: { stand: string; werte: { name: string; wert: number; delta: number | null }[] } | null;
  };
};
type Betrieb = {
  sonden: { zeit: string; gesamt: number; befunde: number; ok: number; betroffen: string[] } | null;
  guthaben: { erschoepft: boolean; halt: string | null; haltGrund: string | null;
              wartend: number | null; anbieter: { name: string; modell: string; frei: number }[] } | null;
};

const min = (s: number | null | undefined) => (s == null ? "—" : Math.round(s / 60) + " min");
const ERG: Record<string, [string, string]> = {
  durch: ["✓ durchgelaufen", "gut"], mit_fehlern: ["durchgelaufen, mit Warnungen", "warn"],
  abgebrochen: ["✖ abgebrochen", "schlecht"], laeuft: ["läuft gerade", "info"], keiner: ["kein Lauf", "warn"],
};

function Karte({ titel, ton, children }: { titel: string; ton?: string; children: React.ReactNode }) {
  return <section className={`cp-karte ${ton ? "cp-" + ton : ""}`}><h3>{titel}</h3>{children}</section>;
}

export default function BetriebCockpit() {
  const [l, setL] = useState<Lauf | null>(null);
  const [b, setB] = useState<Betrieb | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [ts, setTs] = useState(0);

  useEffect(() => {
    let ab = false;
    (async () => {
      try {
        const [rl, rb] = await Promise.all([
          fetch("/api/intern/lauf", { cache: "no-store" }),
          fetch("/api/intern/betrieb", { cache: "no-store" }),
        ]);
        if (ab) return;
        if (rl.status === 404 || rb.status === 404) { setFehler("Kein Zugriff — als Admin anmelden (istAdmin)."); return; }
        setL(await rl.json()); setB(await rb.json()); setFehler(null);
      } catch { if (!ab) setFehler("Laden fehlgeschlagen."); }
    })();
    return () => { ab = true; };
  }, [ts]);

  const lauf = l?.lauf; const erg = lauf ? (ERG[lauf.ergebnis] ?? [lauf.ergebnis, ""]) : null;
  const bestand = l?.ertrag?.bestand ?? {};
  const dok = l?.dokumente; const tri = dok?.trichter; const q = dok?.qualitaet;
  const s = b?.sonden; const g = b?.guthaben;

  return (
    <main className="cp-wrap">
      <header className="cp-top">
        <h1>Betrieb</h1>
        <nav className="cp-nav">
          <Link href="/intern/konten">Konten</Link>
          <Link href="/intern/qualitaet">Datenqualität</Link>
          <Link href="/intern/kosten">LLM & Kosten</Link>
          <Link href="/intern/kuratierung">Kuratierung</Link>
          <Link href="/intern/vertrieb">Vertrieb</Link>
          <Link href="/intern">Firmen-Radar</Link>
          <button onClick={() => setTs(Date.now())}>Aktualisieren</button>
        </nav>
      </header>

      {fehler && <p className="cp-hinweis">{fehler}</p>}

      <div className="cp-grid">
        <Karte titel="Nachtlauf" ton={erg?.[1]}>
          {lauf ? <>
            <p className="cp-gross">{erg?.[0]}</p>
            <p>Datum {lauf.datum ?? "—"} · Dauer {min(lauf.dauerSek)} · vor {lauf.alterStunden ?? "—"} h</p>
            {lauf.ergebnis === "laeuft" && l?.fortschritt &&
              <p>Fortschritt {Math.round((l.fortschritt.anteil ?? 0) * 100)} % · Rest {min(l.fortschritt.verbleibendSek)}</p>}
            {lauf.letzterSchritt && <p className="cp-klein">zuletzt: {lauf.letzterSchritt}</p>}
            {lauf.fehlerZeilen?.length > 0 &&
              <ul className="cp-liste">{lauf.fehlerZeilen.slice(-6).map((z, i) => <li key={i}>{z}</li>)}</ul>}
          </> : <p className="cp-klein">—</p>}
        </Karte>

        <Karte titel="Wächter-Sonden" ton={s ? (s.befunde > 0 ? "warn" : "gut") : undefined}>
          {s ? <>
            <p className="cp-gross">{s.ok}/{s.gesamt} grün{s.befunde > 0 ? ` · ${s.befunde} Befunde` : ""}</p>
            <p className="cp-klein">Stand {s.zeit}</p>
            {s.betroffen.length > 0 &&
              <ul className="cp-liste">{s.betroffen.map((n) => <li key={n}>⚠ {n}</li>)}</ul>}
          </> : <p className="cp-klein">kein Wächter-Log gefunden</p>}
        </Karte>

        <Karte titel="LLM-Auswertung & Guthaben" ton={g ? (g.erschoepft ? "schlecht" : "gut") : undefined}>
          {g ? <>
            <p className="cp-gross">{g.erschoepft ? "gestoppt" : "läuft"}{g.wartend != null ? ` · ${g.wartend} warten` : ""}</p>
            {g.haltGrund && <p className="cp-klein">{g.haltGrund}</p>}
            {g.anbieter?.map((a) => <p key={a.name} className="cp-klein">{a.name} · {a.modell} · {a.frei} frei</p>)}
          </> : <p className="cp-klein">kein LLM-Stand</p>}
        </Karte>

        <Karte titel="Bestand">
          <p className="cp-gross">{(bestand.leads_gesamt ?? 0).toLocaleString("de-DE")} Leads</p>
          <p>{(bestand.leads_offen ?? 0).toLocaleString("de-DE")} offen · {(bestand.vergabestellen ?? 0).toLocaleString("de-DE")} Vergabestellen</p>
        </Karte>

        <Karte titel="Dokumente" ton={dok?.arbeiter?.laeuft ? "info" : undefined}>
          {dok ? <>
            <p>{dok.aufPlatte.toLocaleString("de-DE")} Archive · {dok.indiziert?.toLocaleString("de-DE") ?? "—"} indiziert · {dok.rueckstand ?? "—"} Rückstand</p>
            {tri && <p className="cp-klein">Volltext {tri.volltext ?? "—"} → Analyse {tri.analyse ?? "—"} · ohne Analyse {tri.ohneAnalyse ?? "—"}</p>}
            <p className="cp-klein">Dauer-Arbeiter: {dok.arbeiter?.laeuft ? "läuft" : "steht"}</p>
          </> : <p className="cp-klein">—</p>}
        </Karte>

        <Karte titel="Datenqualität">
          {q ? <>
            <p className="cp-klein">Stand {q.stand}</p>
            <ul className="cp-liste">{q.werte.map((w) => (
              <li key={w.name}>{w.name}: {w.wert}%{w.delta != null ? ` (${w.delta > 0 ? "+" : ""}${w.delta})` : ""}</li>
            ))}</ul>
          </> : <p className="cp-klein">—</p>}
        </Karte>
      </div>
    </main>
  );
}
