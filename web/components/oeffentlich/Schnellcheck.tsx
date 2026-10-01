"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Schnellcheck §7 „Kann ich das gewinnen?" — Firmenname tippen, Firma bestätigen, ein
 * Passungs-Band ohne Konto sehen, dann der Übergang ins Portal (4 Wochen kostenlos).
 *
 * ⚠ Nur EIGENE Signale: Band + Anzahl eigener vergleichbarer Zuschläge. Keine Aussage über
 *   benannte Dritte, kein Verdrängbarkeits-Wert (das rechnet die Route bewusst nicht aus).
 */

type Treffer = { id: string; name: string; wins: number; strong: boolean };
type Ergebnis = { band: "hoch" | "mittel" | "niedrig"; vergleichbare: number; regionPasst: boolean; firma: string };

const BAND_TEXT: Record<Ergebnis["band"], string> = {
  hoch: "Gute Passung",
  mittel: "Teilweise Passung",
  niedrig: "Schwache Passung nach Ihren bisherigen Zuschlägen",
};

export function Schnellcheck({ slug, noticeId }: { slug: string; noticeId: string }) {
  const [q, setQ] = useState("");
  const [treffer, setTreffer] = useState<Treffer[]>([]);
  const [ergebnis, setErgebnis] = useState<Ergebnis | null>(null);
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (ergebnis) return; // nach einem Treffer nicht weitersuchen
    const s = q.trim();
    if (s.length < 2) { setTreffer([]); return; }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const r = await fetch(`/api/entity-search?q=${encodeURIComponent(s)}`);
        const d = await r.json();
        setTreffer(Array.isArray(d.matches) ? d.matches : []);
      } catch { setTreffer([]); }
    }, 220);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [q, ergebnis]);

  async function waehle(t: Treffer) {
    setLaedt(true); setFehler(null); setTreffer([]); setQ(t.name);
    try {
      const r = await fetch(`/api/ausschreibung/schnellcheck?slug=${encodeURIComponent(slug)}&id=${encodeURIComponent(t.id)}`);
      if (!r.ok) throw new Error(String(r.status));
      setErgebnis(await r.json());
    } catch {
      setFehler("Das hat gerade nicht geklappt. Bitte erneut versuchen.");
    } finally {
      setLaedt(false);
    }
  }

  function zuruecksetzen() { setErgebnis(null); setQ(""); setFehler(null); }

  return (
    <section className="aus-block aus-check">
      <h2>Kann ich das gewinnen?</h2>

      {!ergebnis ? (
        <>
          <label className="aus-check-label" htmlFor="aus-firma">Firmenname eingeben:</label>
          <input
            id="aus-firma"
            className="aus-check-input"
            type="text"
            autoComplete="off"
            value={q}
            placeholder="Ihre Firma"
            onChange={(e) => setQ(e.target.value)}
          />
          {treffer.length > 0 ? (
            <ul className="aus-check-liste">
              {treffer.map((t) => (
                <li key={t.id}>
                  <button type="button" className="aus-check-wahl" onClick={() => waehle(t)}>
                    <span className="aus-check-name">{t.name}</span>
                    <span className="aus-check-meta">{t.wins} Zuschläge</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {laedt ? <p className="aus-muted">Prüfe …</p> : null}
          {fehler ? <p className="aus-fehler">{fehler}</p> : null}
        </>
      ) : (
        <div className="aus-check-ergebnis">
          <p className="aus-check-firma">{ergebnis.firma}</p>
          <p className={`aus-check-band aus-band-${ergebnis.band}`}>{BAND_TEXT[ergebnis.band]}</p>
          <p className="aus-check-zahl">
            {ergebnis.vergleichbare > 0
              ? `${ergebnis.vergleichbare} vergleichbare eigene Zuschläge im selben Feld.`
              : "Keine vergleichbaren eigenen Zuschläge in diesem Feld gefunden."}
          </p>
          <a className="aus-cta" href={`/login?von=ausschreibung&n=${encodeURIComponent(noticeId)}`}>
            Vollständige Analyse freischalten. 4 Wochen alles kostenlos.
          </a>
          <button type="button" className="aus-check-reset" onClick={zuruecksetzen}>Andere Firma prüfen</button>
        </div>
      )}
    </section>
  );
}
