import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { ladeOeffentlich, type OeffentlicheSeite } from "@/lib/oeffentlich";
import { FristCountdown } from "@/components/oeffentlich/FristCountdown";
import { Schnellcheck } from "@/components/oeffentlich/Schnellcheck";
import "../../ausschreibung.css";

/**
 * Öffentlicher One-Pager je Ausschreibung (Ticket #17). Server-Komponente: lädt über
 * `ladeOeffentlich` (bestehende `web/data`-JSON, serverless-fähig, kein Python). Dormant und
 * flag-gated: ohne `OEFFENTLICHE_SEITEN=1` liefert `ladeOeffentlich` null → 404, die Seite
 * existiert dann schlicht nicht. In Produktion liegt zusätzlich die Coming-Soon-Sperre davor.
 *
 * ⚠ Das einzige gesperrte Element ist die Wechsel-Wahrscheinlichkeit. Ihr Wert steckt nicht
 *   in `seite` (die Datenschicht lässt ihn weg) — hier kann also gar kein Wert ins HTML
 *   geraten. `hatVerdraengung` steuert nur, OB der gesperrte Block erscheint.
 */

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const seite = await ladeOeffentlich(slug);
  if (!seite) return { title: "Ausschreibung", robots: { index: false, follow: false } };
  const titel = kurz(seite.titel, 70);
  const frist = seite.frist ? ` · Frist ${seite.frist.date}` : "";
  return {
    // §11: {Kurztitel} {Auftraggeber} | Frist — ohne Gedankenstrich, mit Trennzeichen.
    title: kurz(`${titel} | ${seite.buyer}${frist}`, 120),
    description: kurz(seite.leistung ?? `${seite.titel}. Auftraggeber: ${seite.buyer}.`, 300),
    // Indexierbar nur mit seitenspezifischer Exklusivschicht (§11). Sonst noindex.
    robots: seite.indexierbar ? { index: true, follow: true } : { index: false, follow: false },
    alternates: { canonical: `/ausschreibung/${seite.slug}` },
  };
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const seite = await ladeOeffentlich(slug);
  if (!seite) notFound();
  // Kanonischer Slug: abweichender Titel-Teil → 301 auf die stabile Form (§11 URL-Regel).
  if (slug !== seite.slug) redirect(`/ausschreibung/${seite.slug}`);

  return <Inhalt seite={seite} />;
}

function Inhalt({ seite }: { seite: OeffentlicheSeite }) {
  const stand = new Date().toLocaleDateString("de-DE");
  return (
    <main className="aus-wrap">
      <nav className="aus-brot" aria-label="Pfad">
        Ausschreibungen
        {seite.region ? <> {"›"} {seite.region}</> : null}
        {seite.cpvLabel ? <> {"›"} {seite.cpvLabel}</> : null}
      </nav>

      <h1 className="aus-h1">{seite.titel}</h1>

      <p className="aus-kennungen">
        <span className="aus-buyer">{seite.buyer}</span>
        {seite.kennungen.ted ? <> {"·"} TED {seite.kennungen.ted}</> : null}
        {seite.verfahren ? <> {"·"} {verfahrenWort(seite.verfahren)}</> : null}
      </p>

      {seite.frist ? (
        <p className="aus-frist">
          <span aria-hidden>⏱</span> Angebotsfrist {seite.frist.date}
          {seite.frist.uhrzeit ? `, ${seite.frist.uhrzeit}` : ""} {"·"}{" "}
          <FristCountdown date={seite.frist.date} uhrzeit={seite.frist.uhrzeit} />
        </p>
      ) : (
        <p className="aus-frist aus-muted">Frist siehe Bekanntmachung</p>
      )}
      <p className="aus-verbindlich">Verbindlich ist die Bekanntmachung.</p>

      <p className="aus-fakten">
        {seite.volumen ? <span>{seite.volumen}</span> : <span className="aus-muted">Wert unbekannt</span>}
        {" · "}<span className={`aus-zustand aus-zustand-${seite.zustand}`}>{zustandWort(seite.zustand)}</span>
        {seite.lose.length > 0 ? <> {"·"} {seite.lose.length} {seite.lose.length === 1 ? "Los" : "Lose"}</> : null}
      </p>

      {/* Schnellcheck §7 — „Kann ich das gewinnen?" */}
      <Schnellcheck slug={seite.slug} noticeId={seite.noticeId} />

      {/* Das EINE gesperrte Element (§6.2) — nur der Block, nie der Wert. */}
      {seite.hatVerdraengung ? (
        <section className="aus-block aus-gesperrt">
          <h2>Wechsel-Wahrscheinlichkeit</h2>
          <div className="aus-blur" aria-hidden>▒▒▒▒▒▒▒▒</div>
          <p className="aus-cta-hint">Im Portal sichtbar: wie wahrscheinlich der Auftrag den Anbieter wechselt.</p>
        </section>
      ) : null}

      {seite.zustand === "zuschlag" && seite.gewinner && seite.gewinner.length > 0 ? (
        <section className="aus-block">
          <h2>Zuschlag</h2>
          <ul className="aus-liste">
            {seite.gewinner.map((g, i) => <li key={i}>{g}</li>)}
          </ul>
        </section>
      ) : null}

      {/* Auftraggeber (§6.3): Aggregat mit Namen steht in EIGENEM Abschnitt, nie neben der
          Wechsel-Wahrscheinlichkeit. Ohne Namens-Riegel nur Zahlen. */}
      {seite.auftraggeberStatistik.vergabenGesamt != null ? (
        <section className="aus-block">
          <h2>Auftraggeber</h2>
          <p>
            {seite.auftraggeberStatistik.vergabenGesamt} Vergaben
            {seite.auftraggeberStatistik.zeitraum ? ` (${seite.auftraggeberStatistik.zeitraum})` : ""}.
          </p>
          {seite.auftraggeberAggregat ? (
            <p className="aus-aggregat">
              Häufigster Auftragnehmer im Feld: {seite.auftraggeberAggregat.name}
              {seite.auftraggeberAggregat.wins != null
                ? ` (${seite.auftraggeberAggregat.wins} von ${seite.auftraggeberAggregat.n})`
                : ""}.
              <span className="aus-muted"> Keine Aussage über den Vorgängervertrag dieser Ausschreibung.</span>
            </p>
          ) : null}
        </section>
      ) : null}

      {seite.aktiveAnbieter != null ? (
        <section className="aus-block">
          <h2>Wettbewerb</h2>
          <p>{seite.aktiveAnbieter} Zuschläge im Feld{seite.region ? ` (${seite.region})` : ""}.</p>
        </section>
      ) : null}

      {seite.leistung ? (
        <section className="aus-block">
          <h2>Leistung in Kürze</h2>
          <p className="aus-leistung">{seite.leistung}</p>
          <p className="aus-muted aus-klein">Automatisch aus der Bekanntmachung erstellt.</p>
        </section>
      ) : null}

      {seite.lose.length > 0 ? (
        <section className="aus-block">
          <h2>Lose</h2>
          <ul className="aus-liste">
            {seite.lose.map((l, i) => (
              <li key={i}>{l.nr != null ? `${l.nr}. ` : ""}{l.titel}{l.cpv ? ` (CPV ${l.cpv})` : ""}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {seite.unterlagenUrl ? (
        <p className="aus-unterlagen">
          <a href={seite.unterlagenUrl} rel="nofollow noopener" target="_blank">Vergabeunterlagen</a>
        </p>
      ) : null}

      <footer className="aus-fuss">
        Quelle: TED (bearbeitet) {"·"} Stand {stand}. Aufbereitung und abgeleitete Aussagen stammen von goVisor.
      </footer>
    </main>
  );
}

function kurz(s: string, n: number): string {
  const t = (s ?? "").replace(/\s+/g, " ").trim();
  return t.length <= n ? t : t.slice(0, n - 1).trimEnd() + "…";
}

function zustandWort(z: OeffentlicheSeite["zustand"]): string {
  return { offen: "veröffentlicht", wertung: "in Wertung", zuschlag: "Zuschlag erteilt", unbekannt: "Status offen" }[z];
}

function verfahrenWort(v: string): string {
  const m: Record<string, string> = { wettbewerb: "Wettbewerb", offen: "Offenes Verfahren", verhandlung: "Verhandlungsverfahren" };
  return m[v] ?? v;
}
