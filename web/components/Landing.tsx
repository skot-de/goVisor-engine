import Link from "next/link";
import { loadDataFile } from "@/lib/dataSource";
import { EignungsCheck, type Check } from "./EignungsCheck";
import { RelevanzEcho } from "./RelevanzEcho";
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
type Beispiel = { titel: string; kaeufer: string; region: string; frist: string; punkte: Punkt[] };
type Zahlen = {
  stand: string; vergaben: number; offen: number;
  laender: Record<string, { gesamt: number; offen: number }>;
  vergabestellen_de: number; fachgebiete_de: number;
  unterlagen_volltext: number; unterlagen_analysiert: number;
  auslaufend: number; auslaufend_24m: number; regionen: number; anbieter: number;
  fachgebiete: { schluessel: string; label: string; offen: number }[];
  beispiel: Beispiel | null;
  beispiele?: Beispiel[];
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

/**
 * Tage bis zur Frist — auf der Startseite die einzige Zahl, die sich täglich ändert.
 *
 * ⚠ Gibt bewusst auch NEGATIVE Werte zurück. Die Vorfassung klemmte bei 0 ab, und damit
 * hätte der Beweiskasten nach Fristablauf „noch 0 Tage" behauptet und den Vorgang weiter
 * als „gerade offen" ausgewiesen. Das passiert nicht theoretisch: der Kasten wird vom
 * Tageslauf frisch gewählt, und der Tageslauf ist in diesem Projekt schon tagelang
 * ausgefallen. Wer die Zahl abklemmt, macht aus einem stehengebliebenen Lauf eine
 * Falschaussage auf der öffentlichen Seite.
 */
function restTage(iso: string): number {
  return Math.ceil((Date.parse(`${iso}T23:59:59`) - Date.now()) / 86_400_000);
}

export async function Landing() {
  let z: Zahlen | null = null;
  try {
    const roh = await loadDataFile("landing.json");
    z = roh ? (JSON.parse(roh) as Zahlen) : null;
  } catch { z = null; }
  // Aus dem Vorrat den ersten nehmen, dessen Frist noch läuft. Der Tageslauf legt fünf
  // Kandidaten ab (s. export_landing.py); damit trägt ein einziger Export über Wochen,
  // ohne dass je ein abgelaufener Vorgang gezeigt wird.
  const vorrat: Beispiel[] = z?.beispiele?.length ? z.beispiele : z?.beispiel ? [z.beispiel] : [];
  const b = vorrat.find((k) => restTage(k.frist) > 0) ?? null;
  const rest = b ? restTage(b.frist) : 0;

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

      <section className={`lp-held lp-halt${b && rest > 0 ? "" : " lp-held-solo"}`}>
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
          {/* Sven: „mach das ‚kein vertrag, keine kündigungsfrist' weg oder mach es als
              ordentliche punkte darunter mit haken davor." Als Punkte — und sie schliessen
              zugleich die Lücke, die unter dieser Spalte klaffte: der Beweiskasten rechts
              ist 610 px hoch, der Text links war 300, also standen 310 px leer.
              Dieselben drei Zusagen standen bisher unten unter dem Schlussband; sie stehen
              jetzt nur noch hier, wo sie zur Entscheidung gehören. */}
          <ul className="lp-zusicherungen">
            <li>Kein Vertrag, keine Kündigungsfrist</li>
            <li>Dauerhaft kostenfrei, nicht vierzehn Tage</li>
            <li>Keine Zahlungsdaten, kein Verkaufsgespräch</li>
          </ul>
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

        {/* Der Kasten verschwindet, sobald die Frist durch ist: „Echter Vorgang, gerade
            offen" über einem abgelaufenen Verfahren wäre die peinlichste Zeile der Seite,
            und sie stünde ausgerechnet dann da, wenn der Tageslauf hängt. */}
        {b && rest > 0 ? (
          <aside className="lp-probe" aria-label="Beispiel aus dem Bestand">
            <div className="lp-probe-kopf">
              <span className="lp-marker">Echter Vorgang, gerade offen</span>
              <span className="lp-frist">noch {rest} {rest === 1 ? "Tag" : "Tage"}</span>
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
          <ol className="lp-masse">
            <li>
              <span className="lp-masse-k">Relevanz</span>
              <h3>Passt sie zu euch?</h3>
              {/* Wer den Check oben durchgespielt hat, sieht hier SEIN Ergebnis statt des
                  Verweises. Es kommt aus derselben Seitenansicht und wird nirgends
                  gespeichert (s. lib/checkErgebnis.ts). */}
              <RelevanzEcho />
            </li>
            <li>
              <span className="lp-masse-k">Chance</span>
              <h3>Könnt ihr gewinnen?</h3>
              <p>
                Wie fest der bisherige Anbieter sitzt. Bei{" "}
                <b>{nf(z.masse.verdraengbar.hoch ?? 0)}</b> der {nf(z.masse.offen)} offenen
                Vergaben ist er verdrängbar, bei {nf(z.masse.verdraengbar.niedrig ?? 0)} sitzt
                er fest, bei {nf(z.masse.verdraengbar.na ?? 0)} fehlt der Beleg.
              </p>
            </li>
            <li>
              <span className="lp-masse-k">Aufwand</span>
              <h3>Was kostet der Versuch?</h3>
              <p>
                Bindefrist im Median <b>{z.masse.bindefrist.median ?? "?"} Tage</b>{" "}
                ({nf(z.masse.bindefrist.n)} Verfahren), Bürgschaft bei{" "}
                {nf(z.masse.buergschaft.ja ?? 0)} belegt, und bei{" "}
                {nf(z.masse.zuschlag.preis ?? 0)} entscheidet allein der Preis.
              </p>
            </li>
          </ol>
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
              <p>Offene Verfahren in eurem Umkreis, mit ausgewerteten Unterlagen und Frist.</p>
              <span className="lp-stufe-zahl">{nf(z.offen)} offene Verfahren im Bestand</span>
            </li>
            <li>
              <span className="lp-stufe">Nächste 24 Monate</span>
              <h3>Da anfangen, wo andere noch nicht hinsehen</h3>
              <p>
                Welche Verträge auslaufen, wer sie hält, was beim letzten Mal gefordert war.
                Zeit genug, den Auftraggeber vorher kennenzulernen.
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
                euer Fachgebiet im Jahresverlauf.
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
      {/* ⚠ Bis zum 2026-08-21 hing unter fast jedem Block eine kleine Erklärzeile: unter dem
          Werkzeug, unter den drei Massen, unter dem Zahlenband. Sven: „das sieht aus, als
          wenn wir uns für alles erklären müssen." Genau so liest es sich auch — jede
          einzelne Zahl abzusichern wirkt unsicherer als eine Seite, die einmal sagt, woher
          alles kommt. Die Vorbehalte sind deshalb dorthin gewandert, wo sie hingehören:
          „mit laufender Frist" in die Kopfzeile des Werkzeugs, „(7.123 Verfahren)" in den
          Satz, zu dem die Zahl gehört. Übrig bleibt DIESE eine Zeile. */}
      {z ? (
        <p className="lp-herkunft">
          {Object.entries(z.laender).map(([k, v], i) => (
            <span key={k}>{i > 0 ? " · " : ""}{LAND_NAME[k] ?? k} {nf(v.gesamt)}</span>
          ))}
          {" · "}Amtliche Quellen: TED und die nationalen Portale, kein Zukauf. Fachgebiete
          nach CPV-Codes, nicht nach Schlagworten. Stand{" "}
          {new Date(z.stand).toLocaleDateString("de-DE")}.
        </p>
      ) : null}

      {/* Der Abschluss der Seite. Sven: „nimm den kasten da unten raus und mach dafür ‚was
          noch dazugehört' etwas grösser … gib dem featureset mehr platz mit grösseren
          kacheln und einem erklärsatz." Das dunkle Band mit dem Firmenfeld ist damit weg;
          der Einstieg liegt jetzt am Ende dieses Abschnitts und oben in der Leiste, wo er
          ohnehin die ganze Zeit steht. */}
      <section className="lp-block" id="arbeitsweise">
        <h2 className="lp-h2">Was noch dazugehört</h2>
        <p className="lp-bausteine-lede">
          Der Check zeigt, ob ihr passt. Danach fängt die Arbeit an, und dafür liegt in
          goVisor mehr als eine Liste von Ausschreibungen.
        </p>
        <ul className="lp-bausteine">
          <li>
            <span className="lp-baustein-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                <path d="M14 3v5h5" />
                <path d="M12 18v-6" />
                <path d="M9.5 14.5 12 12l2.5 2.5" />
              </svg>
            </span>
            <h3>Unterlagen rein, Checkliste zurück</h3>
            <p>Zieht das Portal-Paket herein: goVisor liest PDF, Word und Excel aus, auch
              verschachtelt, und gibt eine abhakbare Bieter-Checkliste zurück. Jede Angabe mit
              Fundstelle im Originaldokument.</p>
          </li>
          <li>
            <span className="lp-baustein-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 21h18" />
                <path d="M5 21V9.5L12 5l7 4.5V21" />
                <path d="M9 21v-5h6v5" />
                <path d="M9 12h.01M15 12h.01" />
              </svg>
            </span>
            <h3>Vergabestellen-Dossier</h3>
            <p>Was diese Stelle zuletzt vergeben hat, an wen, wie oft sie den Anbieter
              wechselt und wie lange sie bis zum Zuschlag braucht.</p>
          </li>
          <li>
            <span className="lp-baustein-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 20V13h4v7" />
                <path d="M10 20V6h4v14" />
                <path d="M16 20v-9h4v9" />
                <path d="M3 20h18" />
              </svg>
            </span>
            <h3>Wettbewerber und ihre Zuschläge</h3>
            <p>Wer in eurem Fachgebiet gewinnt, wo er sitzt und welche Aufträge er zuletzt
              geholt hat. Auch der, der gerade auf eurem Wunschauftrag sitzt.</p>
          </li>
          <li>
            <span className="lp-baustein-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 20V10" />
                <path d="M10 20V4" />
                <path d="M16 20v-7" />
                <path d="M22 20V8" />
              </svg>
            </span>
            <h3>Strategie: Pipeline und freie Felder</h3>
            <p>Was in den nächsten zwölf bis sechsunddreißig Monaten zu erwarten ist, welche
              Segmente eng besetzt sind und wo Platz ist. Abgeleitet aus den Vergaben eures
              Fachgebiets, nicht aus einer Umfrage.</p>
          </li>
          <li>
            <span className="lp-baustein-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                   strokeLinecap="round" strokeLinejoin="round">
                <circle cx="7" cy="7" r="3" />
                <circle cx="17" cy="17" r="3" />
                <path d="M10 7h4a3 3 0 0 1 3 3v4" />
                <path d="M7 10v4a3 3 0 0 0 3 3h4" />
              </svg>
            </span>
            <h3>Partnersuche für Mehr-Los-Vergaben</h3>
            <p>Vergaben mit mehreren Losen, bei denen ein Partner die übrigen abdecken könnte.
              Sichtbar wird das erst, wenn beide Seiten sich dafür freigeben.</p>
          </li>
          <li>
            <span className="lp-baustein-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 3 3 5.5v15L9 18l6 3 6-2.5v-15L15 6 9 3Z" />
                <path d="M9 3v15M15 6v15" />
              </svg>
            </span>
            <h3>Regionenvergleich</h3>
            <p>Eure Region gegen den Durchschnitt: wie viel dort vergeben wird, wie dicht der
              Wettbewerb ist, wo daneben mehr zu holen wäre.</p>
          </li>
          <li>
            <span className="lp-baustein-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 12h4l2.5-6 4 12L16 12h5" />
              </svg>
            </span>
            <h3>Marktpuls im Jahresverlauf</h3>
            <p>Wann in eurem Fachgebiet ausgeschrieben wird, über zwanzig Jahre gemessen.
              Wer die Saison kennt, plant seine Kapazität dagegen.</p>
          </li>
          <li>
            <span className="lp-baustein-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 9a6 6 0 1 0-12 0c0 5-2 6.5-2 6.5h16S18 14 18 9Z" />
                <path d="M10.5 19.5a2 2 0 0 0 3 0" />
              </svg>
            </span>
            <h3>Alarme auf eure Kriterien</h3>
            <p>Meldung, sobald etwas Passendes erscheint oder ein Vertrag ausläuft, den ihr
              im Blick habt. Keine Rundmail an alle.</p>
          </li>
          <li>
            <span className="lp-baustein-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                   strokeLinecap="round" strokeLinejoin="round">
                <rect x="3.5" y="4" width="6.5" height="7" rx="1.2" />
                <rect x="13.5" y="4" width="7" height="7" rx="1.2" />
                <rect x="3.5" y="14" width="17" height="6" rx="1.2" />
              </svg>
            </span>
            <h3>Bausteinbibliothek</h3>
            <p>Eure Standardtexte für wiederkehrende Nachweise an einem Ort, damit das
              nächste Angebot nicht wieder bei null anfängt.</p>
          </li>
        </ul>

        <p className="lp-preis">
          <b>Was es kostet:</b> Der Einstieg nichts. Suchen, filtern und Vergaben ansehen
          bleibt dauerhaft frei. Bezahlt wird die Tiefe: ausgewertete Unterlagen und Bewertung.
        </p>

        <div className="lp-abschluss" id="starten">
          <Link className="lp-knopf lp-knopf-gross" href="/onboarding">Kostenlos starten</Link>
          <p>
            Vier Schritte: Konto anlegen, Firma bestätigen, Fachgebiet und Umkreis wählen,
            passende Vergaben ansehen. Zehn Minuten, kein Vertrag, keine Kündigungsfrist.
          </p>
        </div>
      </section>

      <footer className="lp-fuss">
        <img className="lp-logo lp-logo-fuss" src="/govisor-wordmark.png" alt="goVisor"
             width={1004} height={252} />
        <span className="lp-klein">Diese Seite ist vorläufig und wird noch überarbeitet.</span>
      </footer>
    </main>
  );
}
