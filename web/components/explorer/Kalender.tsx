"use client";
import { useEffect, useMemo, useState } from "react";

/* Verfahrenskalender (Ticket #16 §5) — chronologische Termine der beobachteten Leads.
 * Kein Kalender-Vollprodukt: eine gruppierte Liste mit Dringlichkeit, jede Zeile führt zum Lead.
 *
 * WAS SICH AM 2026-08-25 GEÄNDERT HAT. Bis dahin stand hier genau ein Termin je Lead: die
 * Angebotsfrist aus der Bekanntmachung. Aus den Unterlagen kommen jetzt die dazu, die dort
 * NICHT stehen und trotzdem über Erfolg oder Ausschluss entscheiden:
 *
 *   · Letzter Tag für Bieterfragen — liegt VOR der Angebotsfrist. Wer ihn verpasst, bietet
 *     auf eine Leistungsbeschreibung, die er nicht mehr klären lassen kann.
 *   · Ende der Bindefrist — wie lange man an sein Angebot gebunden bleibt. Bindet Kapazität
 *     und gehört in die Kalkulation.
 *
 * Gemessen im Bestand: 2.684 Bindefristen, 545 Bieterfragen-Fristen (govisor/kalender.py).
 *
 * ⚠ NUR KLASSIFIZIERTE TERMINE. Die Extraktion typisiert jedes gefundene Datum als „Frist",
 * darunter auch Druckdaten von PDF-Seiten. Was sich keiner Terminart zuordnen liess, ist
 * schon beim Export verworfen — hier kommt nur Benanntes an.
 *
 * ⚠ FEHLT DIE DATEI, FEHLT SIE. Dann zeigt die Zeile weiter die Angebotsfrist aus dem Lead,
 * statt Wissen zu behaupten, das wir für diesen Vorgang nicht haben. */

type Lead = {
  id: string; titel?: string; buyer?: string; buyerShort?: string;
  frist?: { date?: string | null; tage?: number | null; src?: string; uhrzeit?: string | null } | null;
};

type Termin = {
  art: string; datum: string; label: string; quelle: "bekanntmachung" | "unterlagen";
  beleg?: string | null; datei?: string | null; vorbei?: boolean;
  konflikt?: boolean; abweichung_tage?: number;
};

type Eintrag = { titel?: string; termine: Termin[]; verworfen?: number };

/** Ein Termin, angereichert um den Lead, zu dem er gehört. */
type Zeile = Termin & { lead: Lead; tage: number };

const TAG = 86_400_000;

function tageBis(iso: string): number {
  const heute = new Date(); heute.setHours(0, 0, 0, 0);
  const d = new Date(`${iso}T00:00:00`);
  return Math.round((d.getTime() - heute.getTime()) / TAG);
}

export function Kalender({
  rows, onSelect, feedUrl, onSubscribe, isPaid = true,
}: {
  rows: Lead[];
  onSelect: (id: string) => void;
  feedUrl?: string | null;
  onSubscribe?: () => void;
  isPaid?: boolean;
}) {
  const [extra, setExtra] = useState<Record<string, Eintrag>>({});

  // Termine der beobachteten Leads nachladen. Eine Datei je Vorgang, deshalb nur die
  // Merkliste — nicht der Bestand.
  //
  // ⚠ IN BLOECKEN, NICHT ABGESCHNITTEN. Die Route deckelt bei 60 IDs je Anfrage (sie soll
  // keine Abgriff-Flaeche fuer den Bestand sein). Hier stand dafuer ein `.slice(0, 60)` —
  // ein stiller Schnitt, und der ist hier besonders tueckisch: die Zeilen ab 61 fielen auf
  // die Angebotsfrist aus dem Lead zurueck und saehen damit aus wie Vorgaenge, zu denen es
  // eben keine weiteren Termine gibt. Eine fehlende Bindefrist ist aber nicht dasselbe wie
  // eine, die wir nicht geholt haben. Wer 200 Leads beobachtet, bekommt jetzt vier Abrufe.
  useEffect(() => {
    const ids = rows.map((l) => l.id).filter(Boolean);
    if (!ids.length) { setExtra({}); return; }
    const bloecke: string[][] = [];
    for (let i = 0; i < ids.length; i += 60) bloecke.push(ids.slice(i, i + 60));
    let abgebrochen = false;
    Promise.all(
      bloecke.map((b) =>
        fetch(`/api/kalender?ids=${encodeURIComponent(b.join(","))}`)
          .then((r) => (r.ok ? r.json() : {}))
          .catch(() => ({})),          // ein gescheiterter Block kippt die anderen nicht
      ),
    )
      .then((teile) => { if (!abgebrochen) setExtra(Object.assign({}, ...teile)); })
      .catch(() => { /* keine Termine ist kein Fehler, der die Ansicht kippt */ });
    return () => { abgebrochen = true; };
  }, [rows]);

  const { gruppen, gesamt, konflikte } = useMemo(() => {
    const zeilen: Zeile[] = [];
    for (const l of rows) {
      const e = extra[l.id];
      if (e?.termine?.length) {
        for (const t of e.termine) {
          const tage = tageBis(t.datum);
          if (tage < 0) continue;             // Abgelaufenes bleibt im Detail
          zeilen.push({ ...t, lead: l, tage });
        }
      } else if (l.frist?.tage != null && (l.frist.tage as number) >= 0) {
        // Rückfall: was wir schon immer hatten — die Angebotsfrist aus der Bekanntmachung.
        zeilen.push({
          art: "angebotsfrist", datum: l.frist.date || "", quelle: "bekanntmachung",
          label: `Angebotsfrist${l.frist.src === "schaetz" ? " · voraussichtlich" : ""}`,
          lead: l, tage: l.frist.tage as number,
        });
      }
    }
    zeilen.sort((a, b) => a.tage - b.tage || a.art.localeCompare(b.art));
    const b: Record<string, Zeile[]> = { week: [], next: [], later: [] };
    for (const z of zeilen) (z.tage <= 7 ? b.week : z.tage <= 14 ? b.next : b.later).push(z);
    return {
      gruppen: [
        { key: "week", label: "Diese Woche", items: b.week },
        { key: "next", label: "Nächste Woche", items: b.next },
        { key: "later", label: "Später", items: b.later },
      ].filter((g) => g.items.length),
      gesamt: zeilen.length,
      konflikte: zeilen.filter((z) => z.konflikt && z.quelle === "unterlagen").length,
    };
  }, [rows, extra]);

  return (
    <section className="kal">
      <header className="kal-head">
        <div>
          <h3 className="kal-t">Termine</h3>
          <p className="kal-sub">
            {gesamt ? `${gesamt} anstehende${gesamt === 1 ? "r" : ""} Termin${gesamt === 1 ? "" : "e"} aus eurer Merkliste — Fristen, Bindefristen und Ortstermine`
                    : "Fristen eurer beobachteten Leads — chronologisch"}
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

      {/* ⚠ Der Widerspruch gehört nach oben, nicht in eine Zeile weit unten. Wer sich auf
          die falsche Frist verlässt, bietet zu spät — und merkt es erst danach. */}
      {konflikte > 0 && (
        <div className="kal-konflikt">
          <b>Achtung:</b> Bei {konflikte === 1 ? "einem Termin" : `${konflikte} Terminen`} nennen die
          Unterlagen eine <b>andere Angebotsfrist</b> als die Bekanntmachung. Welche gilt, kann nur
          die Vergabestelle sagen — fragt nach, bevor ihr kalkuliert.
        </div>
      )}

      {gesamt === 0 ? (
        <div className="kal-empty">
          <b>Noch keine Termine.</b> Merkt euch Leads (☆), dann erscheinen ihre Fristen hier —
          und, wo die Unterlagen ausgelesen sind, auch Bindefrist und Bieterfragen-Frist.
        </div>
      ) : (
        gruppen.map((g) => (
          <div className="kal-group" key={g.key}>
            <div className="kal-glabel">{g.label}</div>
            {g.items.map((z, i) => {
              const cls = z.tage < 3 ? "risk" : z.tage <= 7 ? "flag" : "";
              const ausUnterlagen = z.quelle === "unterlagen";
              return (
                <button
                  className={`kal-row ${cls} ${z.konflikt ? "konflikt" : ""}`}
                  key={`${z.lead.id}-${z.art}-${z.datum}-${i}`}
                  onClick={() => onSelect(z.lead.id)}
                  title={z.beleg || undefined}
                >
                  <span className="kal-date">{z.datum || "Frist offen"}</span>
                  <span className="kal-kind">
                    {z.label}
                    {ausUnterlagen && <span className="kal-src" title="aus den Vergabeunterlagen">· Unterlagen</span>}
                    {z.konflikt && ausUnterlagen && typeof z.abweichung_tage === "number" && (
                      <span className="kal-warn">
                        ⚠ {z.abweichung_tage > 0 ? "+" : ""}{z.abweichung_tage} Tage gegenüber der Bekanntmachung
                      </span>
                    )}
                  </span>
                  <span className="kal-lead">
                    <span className="kal-lead-t">{z.lead.titel || "(ohne Titel)"}</span>
                    <span className="kal-lead-b">{z.lead.buyerShort || z.lead.buyer || ""}</span>
                  </span>
                  <span className={`kal-rest ${cls}`}>noch {z.tage} {z.tage === 1 ? "Tag" : "Tage"}</span>
                </button>
              );
            })}
          </div>
        ))
      )}
    </section>
  );
}
