import Link from "next/link";
import { loadDataFile } from "@/lib/dataSource";
import { EignungsCheck, type Check } from "./EignungsCheck";
import "../app/landing-oeffentlich.css";

/**
 * Öffentliche Startseite — was jemand sieht, der den Namen gehört hat und nachsieht.
 *
 * **Die Lücke, die sie schliesst.** Bis zum 2026-08-20 gab es zwei Eingänge: die
 * Outreach-Landing unter `/t/<token>` für Angeschriebene und `/login` für Kunden
 * („Willkommen zurück"). Wer weder das eine noch das andere war, fand keinen Satz darüber,
 * was goVisor tut.
 *
 * **Warum ein echter Vorgang im Blickfang steht.** Die erste Fassung erklärte in drei
 * Absätzen, dass zu jeder Anforderung ein wörtliches Zitat gehört. Svens Urteil: „wirkt
 * langweilig". Zu Recht — das Versprechen dieses Produkts lässt sich zeigen statt behaupten.
 * Rechts steht deshalb eine echte offene Ausschreibung mit ihren belegten Anforderungen,
 * ausgesucht von `scripts/export_landing.py` nach Kriterien (offen, Frist in der Zukunft,
 * mindestens drei VERSCHIEDENE Anforderungsarten). Von Hand ausgesucht stünde dort eines
 * Tages ein abgelaufenes Verfahren.
 *
 * **Alle Zahlen und der Beispielvorgang kommen aus `web/data/landing.json`.** Eine im
 * Quelltext getippte Zahl veraltet in dem Moment, in dem jemand sie tippt, und sieht im JSX
 * trotzdem aus wie eine Tatsache. Fehlt die Datei, entfallen Zahlenblock und Beispiel —
 * lieber weniger zeigen als Altes.
 */

type Punkt = { label: string; zitat: string; datei: string };
type Zahlen = {
  stand: string; vergaben: number; offen: number;
  laender: Record<string, { gesamt: number; offen: number }>;
  vergabestellen_de: number; fachgebiete_de: number;
  unterlagen_volltext: number; unterlagen_analysiert: number;
  auslaufend: number; auslaufend_24m: number; regionen: number; anbieter: number;
  fachgebiete: { schluessel: string; label: string; offen: number }[];
  beispiel: { titel: string; kaeufer: string; region: string; frist: string; punkte: Punkt[] } | null;
  check?: Check;
};

const LAND_NAME: Record<string, string> = { DE: "Deutschland", AT: "Österreich", CH: "Schweiz" };
const nf = (n: number) => n.toLocaleString("de-DE");

/** Tage bis zur Frist — auf der Startseite die einzige Zahl, die sich täglich ändert. */
function restTage(iso: string): number {
  const ms = Date.parse(`${iso}T23:59:59`) - Date.now();
  return Math.max(0, Math.ceil(ms / 86_400_000));
}

export async function Landing() {
  let z: Zahlen | null = null;
  try {
    const roh = await loadDataFile("landing.json");
    z = roh ? (JSON.parse(roh) as Zahlen) : null;
  } catch { z = null; }
  const b = z?.beispiel ?? null;
  // Der kleinste veröffentlichte Auftragswert im offenen Bestand — gemessen, nicht gerundet.
  const vol = z?.check?.wert?.min != null ? `${nf(z.check.wert.min)} €` : null;

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
        <div className="lp-held-text">
          <p className="lp-auge">Ausschreibungen aus DACH, bis zur Entscheidung aufbereitet</p>
          <h1>
            Ihr seht nicht nur, <em>dass</em> ausgeschrieben wird.
            <br />Ihr seht, <em>was</em> drinsteht.
          </h1>
          <p className="lp-lead">
            goVisor holt die Vergabeunterlagen, liest sie aus und legt die Anforderungen offen:
            welche Nachweise gefordert sind, welche Summen dahinterstehen, wo die K.-o.-Kriterien
            liegen. Zu jeder Aussage das wörtliche Zitat aus dem Dokument.
          </p>
          <div className="lp-aktionen">
            <Link className="lp-knopf lp-knopf-gross" href="/onboarding">Kostenlos starten</Link>
            <Link className="lp-still" href="/login">Ich habe schon ein Konto</Link>
          </div>
          <p className="lp-fussnote">Kein Vertrag, keine Kündigungsfrist.</p>
        </div>

        {b ? (
          <aside className="lp-probe" aria-label="Beispiel aus dem Bestand">
            <div className="lp-probe-kopf">
              <span className="lp-marker">Echter Vorgang, gerade offen</span>
              <span className="lp-frist">noch {restTage(b.frist)} Tage</span>
            </div>
            <h2>{b.titel}</h2>
            <p className="lp-probe-meta">{b.kaeufer}{b.region ? ` · ${b.region}` : ""}</p>
            <ul className="lp-punkte">
              {b.punkte.map((p, i) => (
                <li key={i}>
                  <span className="lp-punkt-label">{p.label}</span>
                  <blockquote>„{p.zitat}"</blockquote>
                  {p.datei ? <cite>{p.datei}</cite> : null}
                </li>
              ))}
            </ul>
            <p className="lp-probe-fuss">
              Ausgelesen aus den Vergabeunterlagen. Was sich nicht wörtlich belegen lässt,
              verwerfen wir.
            </p>
          </aside>
        ) : null}
      </section>

      {/* FÜR WEN — die Zeile, die vorher fehlte.
          Die Seite sprach niemanden an: kein einziges Gewerk genannt. Ein Dachdecker
          entscheidet in drei Sekunden, ob eine Seite ihn meint, und „117.493 Vergaben" sagt
          ihm nichts; „11.733 offene Bauvergaben" schon. Die Zahl je Gebiet zaehlt nur
          Vorgaenge mit LAUFENDER Frist — was abgelaufen ist, interessiert niemanden. */}
      {z?.fachgebiete?.length ? (
        <section className="lp-fach" aria-label="Fachgebiete">
          <h2 className="lp-fach-h">Offen in eurem Fachgebiet</h2>
          <ul>
            {z.fachgebiete.map((f) => (
              <li key={f.schluessel}>
                <b>{nf(f.offen)}</b>
                <span>{f.label}</span>
              </li>
            ))}
          </ul>
          <p className="lp-klein">
            Dazu alles, was sich keinem dieser Gebiete zuordnen lässt: Lieferungen,
            Dienstleistungen, Sonderfälle. Der Zuschnitt läuft über CPV-Codes, nicht über
            Schlagworte.
          </p>
        </section>
      ) : null}

      {/* EIGNUNGS-CHECK — Svens Einwand: „wir sprechen die zielgruppe nicht an … wir haben
          auch noch was gebaut wo man checken kann, ob man die vorgaben erfüllt." Den
          Abgleich gibt es drinnen seit #27, aber erst nach Konto und Onboarding. Hier steht
          er offen, mit drei Klicks und ohne Firmendaten. Fehlt der vorberechnete Würfel in
          landing.json, entfällt der Abschnitt — lieber nichts als ein Formular, das nichts
          rechnet. */}
      {z?.check && z.fachgebiete?.length ? (
        <EignungsCheck check={z.check} fachgebiete={z.fachgebiete} />
      ) : null}

      {/* PLANUNGSHORIZONT — die Zeitachse, die der ersten Fassung fehlte.
          Sie zeigte nur den Einzelfall: eine offene Ausschreibung mit ihren Anforderungen.
          Dass man damit Jahre voraus planen kann, stand nirgends — dabei ist es das
          stärkere Argument. Wer heute eine laufende Ausschreibung sieht, ist meist zu spät;
          wer einen Amtsinhaber verdrängen will, fängt ein Jahr vorher an.

          Bewusst „euer/eure" statt der nackten Bestandszahl: 437 Regionen sind eine
          Datenbankauskunft, „eure Region" ist ein Angebot. Die Zahl steht klein daneben,
          weil sie den Zuschnitt belegt, nicht ersetzt. */}
      {z ? (
        <section className="lp-block">
          <h2 className="lp-h2">Wie weit reicht euer Planungshorizont?</h2>
          <ol className="lp-horizont">
            <li>
              <span className="lp-stufe">Jetzt</span>
              <h3>Bieten, worauf ihr bieten könnt</h3>
              <p>
                Offene Verfahren in eurem Fachgebiet und Umkreis, mit ausgewerteten Unterlagen
                und der Frist im Blick.
              </p>
              <span className="lp-stufe-zahl">{nf(z.offen)} offene Verfahren im Bestand</span>
            </li>
            <li>
              <span className="lp-stufe">Nächste 24 Monate</span>
              <h3>Da anfangen, wo andere noch nicht hinsehen</h3>
              <p>
                Welche Verträge in eurem Gebiet auslaufen, wer sie heute hält und was beim
                letzten Mal gefordert war. Zeit genug, den Auftraggeber vorher kennenzulernen.
              </p>
              <span className="lp-stufe-zahl">
                {nf(z.auslaufend_24m)} Verträge laufen in 24 Monaten aus
              </span>
            </li>
            <li>
              <span className="lp-stufe">Dauerhaft</span>
              <h3>Euren Markt kennen, nicht nur eure Aufträge</h3>
              <p>
                Eure Region gegen den Durchschnitt, eure Wettbewerber mit ihren Zuschlägen,
                euer Fachgebiet im Jahresverlauf. Wo ihr stark seid und wo jemand anderes sitzt.
              </p>
              <span className="lp-stufe-zahl">
                {nf(z.regionen)} Regionen · {nf(z.anbieter)} Anbieter im Wettbewerbsbild
              </span>
            </li>
          </ol>
        </section>
      ) : null}

      {z ? (
        <section className="lp-zahlen" aria-label="Bestand">
          <div><b>{nf(z.vergaben)}</b><span>Vergaben im Bestand</span></div>
          <div><b>{nf(z.offen)}</b><span>davon offen</span></div>
          <div><b>{nf(z.vergabestellen_de)}</b><span>Vergabestellen in DE</span></div>
          <div><b>{nf(z.unterlagen_analysiert)}</b><span>Unterlagen ausgewertet</span></div>
        </section>
      ) : null}

      {/* Herkunft der Daten: EIN Satz unter den Zahlen statt eines eigenen Abschnitts.
          Als Abschnitt („Woher die Daten kommen", mit Laenderkacheln) war es korrekt und
          langweilig — Sven: „ist vll auch nicht so der hit". Es ist ein Vertrauenssignal,
          kein Verkaufsargument, und Vertrauenssignale gehoeren neben die Zahl, die sie
          stuetzen. */}
      {z ? (
        <p className="lp-herkunft">
          {Object.entries(z.laender).map(([k, v], i) => (
            <span key={k}>{i > 0 ? " · " : ""}{LAND_NAME[k] ?? k} {nf(v.gesamt)}</span>
          ))}
          {" · "}Amtliche Quellen: TED und die nationalen Portale. Kein Zukauf, keine
          Zweitverwertung. Stand {new Date(z.stand).toLocaleDateString("de-DE")}.
        </p>
      ) : null}

      <section className="lp-block">
        {/* ⚠ Hiess bis zum 2026-08-20 „Drei Dinge, die anderswo fehlen". Sven: „stimmen
            nicht, ich glaube nicht das wir die einzigen sind." Er hat recht, und wir haben
            es sogar gemessen: die Analyse eines Wettbewerbers zum Single-Bieter-Anteil war
            methodisch gleichwertig (s. Auto-Memory `govisor-wettbewerber-auftraege-io`).
            Eine Behauptung ueber andere, die wir nicht pruefen koennen, ist genau das, was
            das Produkt drinnen nirgends zulaesst. Also Tatsachen ueber uns statt Urteile
            ueber andere — das ist ohnehin die staerkere Aussage, weil sie ueberpruefbar ist. */}
        <h2 className="lp-h2">So arbeitet goVisor</h2>
        <div className="lp-drei">
          <article>
            <span className="lp-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 8h18" /><path d="M6 8V5.5A1.5 1.5 0 0 1 7.5 4h9A1.5 1.5 0 0 1 18 5.5V8" />
                <path d="M5 8v10.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V8" />
                <path d="M9 13h6" strokeWidth="2.2" />
              </svg>
            </span>
            <h3>{vol ? `Auftragsvolumen ab ${vol}, nach oben offen` : "Vom Kleinauftrag bis zum Grossprojekt"}</h3>
            <p>
              Öffentliche Aufträge gelten als eine Sache für Grosse. Der grösste Teil wird
              nie EU-weit ausgeschrieben, und wir lesen die nationalen Pflichtveröffent&shy;lichungen
              mit, nicht nur TED. Deshalb steht hier auch der Auftrag über ein paar tausend
              Euro neben dem über dreistellige Millionen.
            </p>
          </article>
          <article>
            <span className="lp-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M6 3h8l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
                <path d="M14 3v4h4" /><path d="M8 12h7M8 15.5h7M8 19h4" />
              </svg>
            </span>
            <h3>Die Unterlagen, nicht nur die Anzeige</h3>
            <p>
              Was zählt, steht selten in der Bekanntmachung. Wir holen die Vergabeunterlagen,
              lesen Leistungsverzeichnis und Eignungskriterien aus und zeigen die Anforderungen
              im Klartext, mit Frist und Fundstelle.
            </p>
          </article>
          <article>
            <span className="lp-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6 9 17l-5-5" strokeWidth="2.4" />
              </svg>
            </span>
            <h3>Jede Aussage mit Beleg</h3>
            <p>
              Zu jeder Anforderung steht das wörtliche Zitat aus dem Dokument daneben. Was sich
              nicht belegen lässt, verwerfen wir, statt es zu schätzen.
            </p>
          </article>
          <article>
            <span className="lp-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 11.5 11 13.5 15.5 9" /><path d="M12 3 4 6.5v5c0 4.6 3.2 8.4 8 9.5
                  4.8-1.1 8-4.9 8-9.5v-5L12 3Z" />
              </svg>
            </span>
            <h3>Der Abgleich mit eurem Profil</h3>
            <p>
              Ihr hinterlegt einmal, was ihr habt: Umsatz, Referenzen, Zertifikate,
              Bürgschaftsrahmen. Danach steht an jedem Verfahren, was ihr erfüllt, was fehlt
              und wovon wir abraten, weil eine Pflichtanforderung nicht passt.
            </p>
          </article>
        </div>
      </section>

      <section className="lp-block lp-schluss">
        <h2 className="lp-h2">Anfangen kostet nichts</h2>
        <p>
          Profil anlegen, Fachgebiet und Umkreis wählen, passende Ausschreibungen ansehen.
          Wenn nichts dabei ist, habt ihr zehn Minuten verloren und wisst mehr über euren Markt.
        </p>
        <Link className="lp-knopf lp-knopf-gross" href="/onboarding">Kostenlos starten</Link>
      </section>

      <footer className="lp-fuss">
        <span className="lp-marke">goVisor</span>
        <span className="lp-klein">Diese Seite ist vorläufig und wird noch überarbeitet.</span>
      </footer>
    </main>
  );
}
