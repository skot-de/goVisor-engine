import Link from "next/link";
import { loadDataFile } from "@/lib/dataSource";
import "../app/landing-oeffentlich.css";

/**
 * Öffentliche Startseite — was jemand sieht, der den Namen gehört hat und nachsieht.
 *
 * **Die Lücke, die sie schliesst.** Bis zum 2026-08-20 gab es zwei Eingänge: die
 * Outreach-Landing unter `/t/<token>` für Angeschriebene, und `/login` für Kunden
 * („Willkommen zurück"). Wer weder angeschrieben noch Kunde war, fand keinen Satz darüber,
 * was goVisor eigentlich tut.
 *
 * **Warum die Zahlen aus einer Datei kommen** (`web/data/landing.json`, geschrieben von
 * `scripts/export_landing.py`): eine Startseite, die „über 100.000 Vergaben" im Quelltext
 * behauptet, veraltet in dem Moment, in dem jemand sie tippt, und niemand merkt es. Fehlt
 * die Datei, zeigt die Seite den Zahlenblock gar nicht — lieber keine Zahl als eine alte.
 *
 * **Provisorisch heisst hier: ehrlich statt vollständig.** Kein Preis, kein Testimonial,
 * keine Feature-Matrix. Was drinsteht, ist gemessen und im Produkt nachprüfbar.
 */

type Zahlen = {
  stand: string; vergaben: number; offen: number;
  laender: Record<string, { gesamt: number; offen: number }>;
  vergabestellen_de: number; fachgebiete_de: number;
  unterlagen_volltext: number; unterlagen_analysiert: number;
};

const LAND_NAME: Record<string, string> = { DE: "Deutschland", AT: "Österreich", CH: "Schweiz" };
const nf = (n: number) => n.toLocaleString("de-DE");

export async function Landing() {
  let z: Zahlen | null = null;
  try {
    const roh = await loadDataFile("landing.json");
    z = roh ? (JSON.parse(roh) as Zahlen) : null;
  } catch { z = null; }

  return (
    <main className="lp">
      <header className="lp-kopf">
        <span className="lp-marke">goVisor</span>
        <nav className="lp-nav">
          <Link href="/login">Anmelden</Link>
          <Link className="lp-knopf" href="/onboarding">Kostenlos starten</Link>
        </nav>
      </header>

      <section className="lp-held">
        <h1>Öffentliche Aufträge, aufbereitet bis zur Entscheidung.</h1>
        <p className="lp-lead">
          goVisor sammelt Ausschreibungen aus Deutschland, Österreich und der Schweiz,
          liest die Vergabeunterlagen aus und sagt euch, was drinsteht: welche Nachweise
          gefordert sind, wie der Zuschlag gewichtet wird, wer bisher gewonnen hat.
        </p>
        <div className="lp-aktionen">
          <Link className="lp-knopf lp-knopf-gross" href="/onboarding">Kostenlos starten</Link>
          <Link className="lp-still" href="/login">Ich habe schon ein Konto</Link>
        </div>
      </section>

      {z ? (
        <section className="lp-zahlen" aria-label="Bestand">
          <div><b>{nf(z.vergaben)}</b><span>Vergaben im Bestand</span></div>
          <div><b>{nf(z.offen)}</b><span>davon offen</span></div>
          <div><b>{nf(z.vergabestellen_de)}</b><span>Vergabestellen in DE</span></div>
          <div><b>{nf(z.unterlagen_analysiert)}</b><span>Unterlagen ausgewertet</span></div>
        </section>
      ) : null}

      <section className="lp-block">
        <h2>Drei Dinge, die anderswo fehlen</h2>
        <div className="lp-drei">
          <article>
            <h3>Auch unterhalb der Schwelle</h3>
            <p>
              Der grösste Teil der öffentlichen Aufträge wird nie EU-weit ausgeschrieben.
              goVisor liest die nationalen Pflichtveröffentlichungen mit, nicht nur TED.
            </p>
          </article>
          <article>
            <h3>Die Unterlagen, nicht nur die Anzeige</h3>
            <p>
              Was zählt, steht selten in der Bekanntmachung. Wir holen die Vergabeunterlagen,
              lesen Leistungsverzeichnis und Eignungskriterien aus und zeigen die Anforderungen
              im Klartext.
            </p>
          </article>
          <article>
            <h3>Jede Aussage mit Beleg</h3>
            <p>
              Zu jeder Anforderung steht das wörtliche Zitat aus dem Dokument daneben. Was sich
              nicht belegen lässt, wird verworfen statt geschätzt.
            </p>
          </article>
        </div>
      </section>

      <section className="lp-block lp-hell">
        <h2>Woher die Daten kommen</h2>
        <p className="lp-quellen">
          {z
            ? Object.entries(z.laender).map(([k, v], i) => (
                <span key={k}>
                  {i > 0 ? " · " : ""}
                  <b>{LAND_NAME[k] ?? k}</b> {nf(v.gesamt)} Vergaben, {nf(v.offen)} offen
                </span>
              ))
            : "Deutschland, Österreich und die Schweiz"}
        </p>
        <p className="lp-klein">
          Amtliche Quellen: TED für die EU-weiten Verfahren, die nationalen Portale für alles
          darunter. Kein Zukauf, keine Zweitverwertung. Was fehlt, sagen wir statt es zu
          erfinden.
          {z ? ` Stand ${new Date(z.stand).toLocaleDateString("de-DE")}.` : ""}
        </p>
      </section>

      <section className="lp-block lp-schluss">
        <h2>Anfangen kostet nichts</h2>
        <p>
          Profil anlegen, Fachgebiet und Umkreis wählen, passende Ausschreibungen ansehen.
          Ohne Vertrag, ohne Kündigungsfrist.
        </p>
        <Link className="lp-knopf lp-knopf-gross" href="/onboarding">Kostenlos starten</Link>
      </section>

      <footer className="lp-fuss">
        <span>goVisor</span>
        <span className="lp-klein">Diese Seite ist vorläufig und wird noch überarbeitet.</span>
      </footer>
    </main>
  );
}
