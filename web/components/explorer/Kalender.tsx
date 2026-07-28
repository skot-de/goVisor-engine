"use client";
import { useMemo } from "react";

/* Verfahrenskalender (Ticket #16 §5) — chronologische Angebotsfristen der beobachteten Leads.
 * Kein Kalender-Vollprodukt: eine gruppierte Liste mit Dringlichkeit, jede Zeile führt zum Lead.
 * Liest dieselben Frist-Daten wie das Detail (l.frist), keine neue Erhebung. Fehlende Termine
 * werden weggelassen (kein „unbekannt"-Lärm); nur zukünftige Fristen — Abgelaufenes bleibt im Detail. */

type Lead = {
  id: string; titel?: string; buyer?: string; buyerShort?: string;
  frist?: { date?: string | null; tage?: number | null; src?: string; uhrzeit?: string | null } | null;
};

type Bucket = { key: string; label: string; items: Lead[] };

export function Kalender({
  rows, onSelect, feedUrl, onSubscribe, isPaid = true,
}: {
  rows: Lead[];
  onSelect: (id: string) => void;
  feedUrl?: string | null;
  onSubscribe?: () => void;
  isPaid?: boolean;
}) {
  const buckets = useMemo<Bucket[]>(() => {
    const withFrist = rows
      .filter((l) => l.frist && l.frist.tage != null && (l.frist.tage as number) >= 0)
      .sort((a, b) => (a.frist!.tage as number) - (b.frist!.tage as number));
    const b: Record<string, Lead[]> = { week: [], next: [], later: [] };
    for (const l of withFrist) {
      const t = l.frist!.tage as number;
      (t <= 7 ? b.week : t <= 14 ? b.next : b.later).push(l);
    }
    return [
      { key: "week", label: "Diese Woche", items: b.week },
      { key: "next", label: "Nächste Woche", items: b.next },
      { key: "later", label: "Später", items: b.later },
    ].filter((g) => g.items.length);
  }, [rows]);

  const total = buckets.reduce((n, g) => n + g.items.length, 0);

  return (
    <section className="kal">
      <header className="kal-head">
        <div>
          <h3 className="kal-t">Termine</h3>
          <p className="kal-sub">
            {total ? `${total} anstehende Angebotsfrist${total === 1 ? "" : "en"} aus deiner Merkliste`
                   : "Fristen deiner beobachteten Leads — chronologisch"}
          </p>
        </div>
        {onSubscribe && (
          feedUrl ? (
            <div className="kal-feed">
              <input readOnly value={feedUrl} onFocus={(e) => e.currentTarget.select()} aria-label="iCal-Feed-URL" />
              <span className="kal-feed-h">In Outlook/Google-Kalender abonnieren — aktualisiert sich automatisch</span>
            </div>
          ) : (
            <button className="kal-ics" onClick={onSubscribe} title={isPaid ? "iCal-Feed anlegen" : "Pro-Feature"}>
              📅 Fristen in meinen Kalender {isPaid ? "" : "· Pro"}
            </button>
          )
        )}
      </header>

      {total === 0 ? (
        <div className="kal-empty">
          <b>Noch keine Fristen.</b> Merke dir Leads (☆), dann erscheinen ihre Angebotsfristen hier —
          und, falls veröffentlicht, mit Datum und Restzeit.
        </div>
      ) : (
        buckets.map((g) => (
          <div className="kal-group" key={g.key}>
            <div className="kal-glabel">{g.label}</div>
            {g.items.map((l) => {
              const t = l.frist!.tage as number;
              const cls = t < 3 ? "risk" : t <= 7 ? "flag" : "";
              const est = l.frist!.src === "schaetz";
              return (
                <button className={`kal-row ${cls}`} key={l.id} onClick={() => onSelect(l.id)}>
                  <span className="kal-date">{l.frist!.date || "Frist offen"}{l.frist!.uhrzeit ? `, ${l.frist!.uhrzeit}` : ""}</span>
                  <span className="kal-kind">Angebotsfrist{est ? " · voraussichtlich" : ""}</span>
                  <span className="kal-lead">
                    <span className="kal-lead-t">{l.titel || "(ohne Titel)"}</span>
                    <span className="kal-lead-b">{l.buyerShort || l.buyer || ""}</span>
                  </span>
                  <span className={`kal-rest ${cls}`}>noch {t} {t === 1 ? "Tag" : "Tage"}</span>
                </button>
              );
            })}
          </div>
        ))
      )}
    </section>
  );
}
