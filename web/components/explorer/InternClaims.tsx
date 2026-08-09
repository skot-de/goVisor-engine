"use client";

import { useCallback, useEffect, useState } from "react";

/* INTERN — Prüfliste der Identitäts-Ansprüche.
 *
 * Zweck: entscheiden, ob jemand wirklich zu der Firma gehört, die er beansprucht. Damit das
 * in Sekunden geht statt in Minuten, steht neben dem Antrag alles, was dagegen oder dafür
 * spricht — die aus den Vergabedaten bekannte Domain, die Zahl hinterlegter Adressen und
 * die größten Auftraggeber. Ohne diesen Kontext wäre die Liste nur eine Warteschlange.
 */

type Firma = {
  name: string; wins: number; buyers: number | null; seit: number | null;
  bekannteDomain: string | null; domainBelege: number; adressenBekannt: number;
  topBuyers: { name: string; wins: number; seit: number; bis: number }[];
};
type Claim = {
  id: string; identity_id: string; company_name: string; email_domain: string | null;
  status: "belegt" | "unbestaetigt" | "geprueft" | "abgelehnt";
  grund: string | null; nachricht: string | null; created_at: string;
  bearbeitet_am: string | null; bearbeitet_von: string | null;
  firma: Firma | null; domainPasst: boolean;
};

const STATUS_TEXT: Record<Claim["status"], string> = {
  unbestaetigt: "offen", belegt: "automatisch belegt", geprueft: "freigegeben", abgelehnt: "abgelehnt",
};

export function InternClaims() {
  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [nurOffen, setNurOffen] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  const laden = useCallback(async () => {
    try {
      const r = await fetch("/api/intern/claims");
      if (!r.ok) throw new Error(r.status === 404 ? "In Production gesperrt (INTERN_ENABLED=1 setzen)." : `Fehler ${r.status}`);
      const d = await r.json();
      setClaims(d.claims ?? []); setFehler(null);
    } catch (e) { setFehler(e instanceof Error ? e.message : "Laden fehlgeschlagen"); }
  }, []);

  useEffect(() => { laden(); }, [laden]);

  async function entscheiden(id: string, status: "geprueft" | "abgelehnt") {
    setBusy(id);
    await fetch("/api/intern/claims", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ id, status }),
    }).catch(() => {});
    setBusy(null);
    laden();
  }

  if (fehler) return <div className="ic-wrap"><p className="ic-fehler">{fehler}</p></div>;
  if (!claims) return <div className="ic-wrap"><p className="ic-leer">Lädt …</p></div>;

  const liste = nurOffen ? claims.filter((c) => c.status === "unbestaetigt") : claims;
  const offen = claims.filter((c) => c.status === "unbestaetigt").length;

  return (
    <div className="ic-wrap">
      <header className="ic-top">
        <div>
          <h1>Identitäts-Anträge</h1>
          <p>{offen} offen · {claims.length} insgesamt</p>
        </div>
        <label className="ic-filter">
          <input type="checkbox" checked={nurOffen} onChange={() => setNurOffen((v) => !v)} />
          nur offene
        </label>
      </header>

      {!liste.length ? (
        <p className="ic-leer">{nurOffen ? "Nichts offen." : "Noch keine Anträge."}</p>
      ) : liste.map((c) => (
        <article key={c.id} className="ic-karte" data-status={c.status}>
          <div className="ic-kopf">
            <div>
              <b>{c.company_name}</b>
              <span className="ic-id">{c.identity_id}</span>
            </div>
            <span className={`ic-st ic-st-${c.status}`}>{STATUS_TEXT[c.status]}</span>
          </div>

          <div className="ic-gruende">
            <div><span>Antrags-Domain</span><b>{c.email_domain ?? "—"}</b></div>
            <div><span>bekannte Domain</span>
              <b>{c.firma?.bekannteDomain ?? "keine hinterlegt"}
                {c.firma?.domainBelege ? ` (${c.firma.domainBelege} Belege)` : ""}</b></div>
            <div><span>Adressen hinterlegt</span><b>{c.firma?.adressenBekannt ?? 0}</b></div>
            <div><span>Zuschläge</span>
              <b>{c.firma ? `${c.firma.wins} bei ${c.firma.buyers ?? "?"} Auftraggebern seit ${c.firma.seit ?? "?"}` : "Firma unbekannt"}</b></div>
          </div>

          {/* Der maschinelle Befund ist das Erste, was man wissen will. */}
          <p className={`ic-befund ${c.domainPasst ? "gut" : ""}`}>
            {c.domainPasst
              ? "Domain stimmt mit der bekannten überein — vermutlich nur wegen zu weniger Belege nicht automatisch freigegeben."
              : c.grund || "kein maschineller Befund"}
          </p>

          {c.firma?.topBuyers?.length ? (
            <p className="ic-kunden">
              Größte Auftraggeber: {c.firma.topBuyers.map((k) => `${k.name} (${k.wins})`).join(" · ")}
            </p>
          ) : null}

          {c.nachricht ? <blockquote className="ic-nachricht">{c.nachricht}</blockquote> : null}

          <footer className="ic-fuss">
            <span className="ic-zeit">
              {new Date(c.created_at).toLocaleString("de-DE")}
              {c.bearbeitet_am ? ` · bearbeitet ${new Date(c.bearbeitet_am).toLocaleDateString("de-DE")} von ${c.bearbeitet_von}` : ""}
            </span>
            {c.status === "unbestaetigt" ? (
              <span className="ic-btns">
                <button className="ic-ok" disabled={busy === c.id} onClick={() => entscheiden(c.id, "geprueft")}>Freigeben</button>
                <button className="ic-nein" disabled={busy === c.id} onClick={() => entscheiden(c.id, "abgelehnt")}>Ablehnen</button>
              </span>
            ) : null}
          </footer>
        </article>
      ))}
    </div>
  );
}
