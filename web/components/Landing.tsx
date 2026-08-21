import Link from "next/link";
import { loadDataFile } from "@/lib/dataSource";
import { EignungsCheck, type Check } from "./EignungsCheck";
import { StartForm } from "./StartForm";
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
  masse?: {
    offen: number;
    verdraengbar: Record<string, number>;
    buergschaft: Record<string, number>;
    bindefrist: { n: number; median: number | null; p90: number | null };
    zuschlag: Record<string, number>;
  };
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

  return (
    <main className="lp">
      {/* Gründungsleiste. Bewusst OHNE Preisversprechen: die Vorlage warb mit einem
          „Einführungspreis", und der ist nicht beschlossen. Was stimmt und trotzdem trägt,
          ist der Zeitpunkt — wer jetzt kommt, redet mit den Leuten, die es bauen. */}
      <p className="lp-gruendung">
        <b>Gründungsphase.</b> Der Bestand wächst täglich, das Produkt auch. Wer jetzt
        einsteigt, redet direkt mit denen, die es bauen.
      </p>

      <header className="lp-kopf">
        {/* Das echte Zeichen statt getippter Buchstaben: dieselbe Datei, die die Anwendung
            in der Seitenleiste trägt (`Rail.tsx`). Ein Schriftzug, der auf der Startseite
            anders aussieht als drinnen, ist zwei Marken. */}
        <img className="lp-logo" src="/govisor-wordmark.png" alt="goVisor" width={1004}
             height={252} />
        <nav className="lp-nav">
          {/* Nur Anker auf diese Seite: eine Navigation, die auf Seiten zeigt, die es noch
              nicht gibt, ist der erste gebrochene Klick des ersten Besuchers. */}
          {/* ⚠ Standen als „Was ist offen" (Frage), „Arbeitsweise" (Substantiv) und
              „Anfangen" (Verb) nebeneinander: drei Register in drei Wörtern. Jetzt drei
              Substantive, damit die Leiste eine Stimme hat. */}
          <a href="#check">Offene Vergaben</a>
          <a href="#arbeitsweise">Arbeitsweise</a>
          <a href="#starten">Einstieg</a>
          <Link href="/login">Anmelden</Link>
          <Link className="lp-knopf" href="/onboarding">Kostenlos starten</Link>
        </nav>
      </header>

      <section className="lp-held lp-halt">
        <div className="lp-held-text">
          <p className="lp-auge">Ausschreibungen aus DACH, bis zur Entscheidung aufbereitet</p>
          {/* „Gezielt bieten" statt der langen Doppelzeile: die Vorlage sagt in zwei Wörtern,
              wofür wir vier Zeilen brauchten. Der Satz darunter nennt das Unangenehme, das
              sonst niemand anbietet — wo ihr es lassen solltet. Genau davon lebt das
              Erlösmodell: wir verdienen mit, wenn ihr gewinnt, nicht wenn ihr bietet. */}
          <h1>Gezielt bieten.</h1>
          <p className="lp-lead">
            Ihr seht nicht nur, <em>dass</em> ausgeschrieben wird, sondern <em>was</em>
            {" "}drinsteht: welche Nachweise gefordert sind, welche Summen dahinterstehen, wo die
            K.-o.-Kriterien liegen. Und wo ihr besser <b>nicht</b> bietet.
          </p>
          <div className="lp-aktionen">
            <Link className="lp-knopf lp-knopf-gross" href="/onboarding">Kostenlos starten</Link>
            <Link className="lp-still" href="/login">Ich habe schon ein Konto</Link>
          </div>
          <p className="lp-fussnote">Kein Vertrag, keine Kündigungsfrist.</p>
        </div>

        {/* Der Hinweis, dass es weitergeht. Sven wollte „einen pfeil runter als andeutung" —
            das ist der tragende Teil der Idee und kostet nichts. Er springt auf das Werkzeug,
            nicht irgendwohin, und trägt deshalb einen Text statt nur ein Zeichen. */}
        <a className="lp-weiter" href="#check">
          <span>Was heute offen ist</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
               strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 5v14M6 13l6 6 6-6" />
          </svg>
        </a>

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

      {/* ⚠ Hier stand bis zum 2026-08-20 ein eigener Abschnitt „Offen in eurem
          Fachgebiet": sechs Zahlen zum Anschauen, direkt über einem Check, der dieselbe
          Auswahl noch einmal als Aufklappmenü stellte. Sven: „sollte man besser verbinden."
          Die Kacheln sind jetzt die Auswahl des Checks (s. EignungsCheck.tsx) — und sie
          rechnen mit der gewählten Region mit. */}
      {/* EIGNUNGS-CHECK — Svens Einwand: „wir sprechen die zielgruppe nicht an … wir haben
          auch noch was gebaut wo man checken kann, ob man die vorgaben erfüllt." Den
          Abgleich gibt es drinnen seit #27, aber erst nach Konto und Onboarding. Hier steht
          er offen, mit drei Klicks und ohne Firmendaten. Fehlt der vorberechnete Würfel in
          landing.json, entfällt der Abschnitt — lieber nichts als ein Formular, das nichts
          rechnet. */}
      {z?.check && z.fachgebiete?.length ? (
        <EignungsCheck check={z.check} fachgebiete={z.fachgebiete} />
      ) : null}

      {/* DREI MASSE. Aus der Vorlage `INPUT/…/govisor-landing-v28.html` („KPIs die wirklich
          helfen: Relevanz, Chance, Aufwand"). Sie stehen DIREKT hinter dem Werkzeug, nicht
          weiter unten: wer den Check gerade ausprobiert hat, hat eines der drei Masse eben
          in Betrieb gesehen — hier steht, wie die anderen beiden dazugehören. Vor dem
          Werkzeug wären sie Theorie vor dem Anfassen, und Anfassen überzeugt mehr. Nachgemessen tragen davon ohne Konto nur zwei
          etwas: `relevanz` steht bei allen 30.627 offenen Vorgängen auf „na", weil sie erst
          im Abgleich mit einem Profil entsteht, und ein Feld `chance` ist durchgehend leer.
          Deshalb steht hier bei der Relevanz kein Wert, sondern der Verweis auf den Check
          darüber — und die beiden anderen tragen gemessene Zahlen statt Balken. */}
      {z?.masse ? (
        <section className="lp-block" id="masse">
          <h2 className="lp-h2">Drei Masse, die die Entscheidung tragen</h2>
          <p className="lp-masse-lede">
            Eine Ausschreibung zu finden ist das Leichte. Die Frage ist, ob sie zu euch passt,
            ob ihr sie gewinnen könnt und was der Versuch kostet.
          </p>
          <ol className="lp-masse">
            <li>
              <span className="lp-masse-k">Relevanz</span>
              <h3>Passt sie zu euch?</h3>
              <p>
                Der Abgleich eurer Nachweise mit dem, was in den Unterlagen verlangt wird.
                Diese Zahl gibt es nur mit Profil, deshalb steht hier keine: probiert sie
                oben im <a href="#check">Eignungs-Check</a> aus, ohne Anmeldung.
              </p>
            </li>
            <li>
              <span className="lp-masse-k">Chance</span>
              <h3>Könnt ihr gewinnen?</h3>
              <p>
                Wie fest der bisherige Anbieter sitzt, aus Bieterzahl, Vorgeschichte und
                Zuschlagsmuster. Bei <b>{nf(z.masse.verdraengbar.hoch ?? 0)}</b> der{" "}
                {nf(z.masse.offen)} offenen Vergaben ist er verdrängbar, bei{" "}
                {nf(z.masse.verdraengbar.niedrig ?? 0)} sitzt er fest. Wo die Belege fehlen,
                steht kein Wert statt eines geratenen: {nf(z.masse.verdraengbar.na ?? 0)} Fälle.
              </p>
            </li>
            <li>
              <span className="lp-masse-k">Aufwand</span>
              <h3>Was kostet der Versuch?</h3>
              <p>
                Bindefrist, Bürgschaft, Zuschlagskriterien. Die Bindefrist liegt im Median bei{" "}
                <b>{z.masse.bindefrist.median ?? "?"} Tagen</b>, im oberen Zehntel bei{" "}
                {z.masse.bindefrist.p90 ?? "?"}; eine Bürgschaft ist bei{" "}
                {nf(z.masse.buergschaft.ja ?? 0)} Verfahren belegt, und bei{" "}
                {nf(z.masse.zuschlag.preis ?? 0)} entscheidet allein der Preis.
              </p>
            </li>
          </ol>
          <p className="lp-klein">
            Die Aufwandsangaben stammen aus den ausgewerteten Vergabeunterlagen und fehlen
            dort, wo noch keine ausgewertet sind: Bindefrist aus {nf(z.masse.bindefrist.n)}{" "}
            Verfahren, Zuschlagskriterien aus{" "}
            {nf((z.masse.zuschlag.preis ?? 0) + (z.masse.zuschlag.gemischt ?? 0))}.
          </p>
        </section>
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
        <section className="lp-block lp-halt" id="horizont">
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

      <section className="lp-block" id="arbeitsweise">
        {/* ⚠ Hiess bis zum 2026-08-20 „Drei Dinge, die anderswo fehlen". Sven: „stimmen
            nicht, ich glaube nicht das wir die einzigen sind." Er hat recht, und wir haben
            es sogar gemessen: die Analyse eines Wettbewerbers zum Single-Bieter-Anteil war
            methodisch gleichwertig (s. Auto-Memory `govisor-wettbewerber-auftraege-io`).
            Eine Behauptung ueber andere, die wir nicht pruefen koennen, ist genau das, was
            das Produkt drinnen nirgends zulaesst. Also Tatsachen ueber uns statt Urteile
            ueber andere — das ist ohnehin die staerkere Aussage, weil sie ueberpruefbar ist. */}
        {/* ⚠ Waren bis zum 2026-08-21 VIER Karten, und Sven hat recht: „die so arbeitet
            punkte sind alle ziemlich redundant". Sie waren es auf zwei Arten. „Die
            Unterlagen" und „Jede Aussage mit Beleg" sagten beide, dass wir Dokumente lesen
            und zitieren — jetzt eine Karte. „Der Abgleich mit eurem Profil" beschrieb genau
            das, was der Eignungs-Check darüber inzwischen VORFÜHRT; eine Karte, die eine
            Funktion erklärt, die zwei Bildschirmhöhen weiter oben schon lief, ist Füllung.
            Und die Wertspanne steht ebenfalls dort, mit echten Zahlen. Bleiben zwei Karten,
            die etwas sagen, das sonst nirgends steht. */}
        <h2 className="lp-h2">So arbeitet goVisor</h2>
        <div className="lp-drei lp-zwei">
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
              im Klartext, mit Frist und Fundstelle. Zu jeder steht das wörtliche Zitat aus dem
              Dokument daneben; was sich nicht belegen lässt, verwerfen wir, statt es zu
              schätzen.
            </p>
          </article>
          <article>
            <span className="lp-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
                   strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="9" /><path d="M3 12h18" />
                <path d="M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18Z" />
              </svg>
            </span>
            <h3>Drei Länder, auch unterhalb der Schwelle</h3>
            <p>
              Der grösste Teil der öffentlichen Aufträge wird nie EU-weit ausgeschrieben. Wir
              lesen die nationalen Pflichtveröffent&shy;lichungen in Deutschland, Österreich
              und der Schweiz mit, nicht nur TED. Deshalb steht hier der Auftrag über ein paar
              tausend Euro neben dem über dreistellige Millionen.
            </p>
          </article>
        </div>

        <p className="lp-bausteine-t">Dazu gehört, was danach kommt:</p>
        <div className="lp-bausteine">
          <span>Vergabestellen-Dossier</span>
          <span>Wettbewerber und ihre Zuschläge</span>
          <span>Regionenvergleich</span>
          <span>Marktpuls im Jahresverlauf</span>
          <span>Alarme auf eure Kriterien</span>
          <span>Bausteinbibliothek für Angebotstexte</span>
        </div>

        {/* ⚠ Hier stand bis zum 2026-08-21 die Erfolgsprämie („wenn ihr gewinnt, verdienen
            wir mit"). Sven: „wir haben die vergabeprämie verworfen, also nimm das von der
            seite." Was bleibt, ist die Stufenaussage ohne Beträge — die stehen nicht fest,
            und eine Zahl, die später anders ausfällt, ist auf einer öffentlichen Seite
            teuer. */}
        <p className="lp-preis">
          <b>Was es kostet:</b> Der Einstieg nichts. Suchen, filtern und Vergaben ansehen
          bleibt dauerhaft frei, ohne Zahlungsdaten und ohne Frist. Bezahlt wird später die
          Tiefe: die ausgewerteten Unterlagen und die Bewertung eines Verfahrens.
        </p>
      </section>

      {/* Schluss als dunkles Band, die Form aus der Vorlage. Dort stand ein E-Mail-Feld;
          hier steht die erste Frage des Onboardings selbst — wer die Firma tippt, hat den
          ersten Schritt hinter sich, und wir sammeln keine Adressen ein, mit denen wir
          nichts vorhätten. */}
      <section className="lp-schluss" id="starten">
        <div className="lp-schluss-text">
          <h2>Überzeugt euch selbst. Der Einstieg kostet nichts.</h2>
          <p>
            Firma eintragen, Fachgebiet und Umkreis wählen, passende Vergaben ansehen. Wenn
            nichts dabei ist, habt ihr zehn Minuten verloren und wisst mehr über euren Markt.
          </p>
        </div>
        <StartForm />
      </section>
      <p className="lp-zusagen">
        <span>Keine Zahlungsdaten, kein Verkaufsgespräch</span>
        <span>Dauerhaft frei, nicht vierzehn Tage</span>
        <span>Jederzeit kündbar, wir fragen höchstens warum</span>
      </p>

      <footer className="lp-fuss">
        <img className="lp-logo lp-logo-fuss" src="/govisor-wordmark.png" alt="goVisor"
             width={1004} height={252} />
        <span className="lp-klein">Diese Seite ist vorläufig und wird noch überarbeitet.</span>
      </footer>
    </main>
  );
}
