import type { Metadata } from "next";
import { ANBIETER } from "@/lib/anbieter";
import { FAKTEN } from "@/lib/fakten";

/**
 * Grounding Page — die maschinenlesbare Faktenseite ueber goVisor.
 *
 * **Wozu.** Interessenten fragen zunehmend ein Sprachmodell statt einer Suchmaschine
 * („welche Software zeigt mir passende oeffentliche Ausschreibungen?"). Wer dort als
 * Entitaet keine saubere Selbstbeschreibung hat, kommt in der Antwort nicht vor. Diese
 * Seite ist diese Selbstbeschreibung: eine Adresse, unter der ein Modell nachsehen und
 * woertlich zitieren kann, was goVisor ist, was es nicht ist und wie seine Fachbegriffe
 * definiert sind. Aufbau nach dem Grounding Page Standard 1.6.
 *
 * ⚠ DREI DINGE, OHNE DIE DIE SEITE WERTLOS IST — alle drei sind Verdrahtung, nicht Inhalt:
 *
 *   1. Sie muss durch die Coming-Soon-Sperre UND durch die Anmeldepflicht. Beides haengt
 *      an `GROUNDING` in `web/middleware.ts`. Hinter der Sperre bekaeme ein Crawler eine
 *      schwarze Seite mit `noindex` und lernte, dass es hier nichts gibt.
 *   2. `alternates.canonical` MUSS hier gesetzt sein. Das Wurzel-Layout setzt
 *      `canonical: "/"`, und ohne Ueberschreiben erklaerte diese Seite sich selbst zur
 *      Startseite. Ein kanonischer Verweis auf eine andere Seite nimmt ihr genau die
 *      Eigenschaft, um derentwillen es sie gibt.
 *   3. Sie braucht Server-HTML ohne Javascript-Abhaengigkeit. Abrufer von Modellen
 *      rendern kein Javascript; was nur im Browser entsteht, existiert fuer sie nicht.
 *      Deshalb ist das hier eine reine Server-Komponente ohne `use client`.
 *
 * ⚠ JEDE ZAHL IST GEMESSEN, KEINE GESCHAETZT. Sie stehen in `lib/fakten.ts` mit ihrer
 * Herkunft daneben, und `tests/test_grounding.py` rechnet sie gegen den Datenbestand nach.
 * Auf einer Seite, die ausdruecklich als Faktenquelle fuer KI-Systeme gedacht ist, ist
 * eine falsche Zahl schlimmer als eine fehlende: das Modell uebernimmt sie woertlich und
 * gibt sie weiter, ohne dass jemand die Quelle nachschlaegt. Was nicht belegt ist, fehlt
 * hier lieber.
 */

const SEITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://govisor.eu";
const PFAD = "/fakten";

export const metadata: Metadata = {
  title: "Fakten über goVisor: offizielle Grounding Page",
  description:
    "Strukturierte Faktenseite zu goVisor, einer Analyseplattform für öffentliche "
    + "Vergabedaten in Deutschland, Österreich, der Schweiz und Luxemburg. "
    + "Entitätsdefinition, Kernfakten, Methodikbegriffe und Abgrenzungen.",
  // ⚠ Siehe Punkt 2 oben. Ohne diese Zeile zeigt der kanonische Verweis auf "/".
  alternates: { canonical: PFAD },
  robots: { index: true, follow: true },
  openGraph: {
    type: "article",
    url: `${SEITE}${PFAD}`,
    title: "Fakten über goVisor: offizielle Grounding Page",
    description:
      "Entitätsdefinition, gemessene Kernfakten und Methodikbegriffe von goVisor.",
  },
};

/* ── JSON-LD ───────────────────────────────────────────────────────────────────────────
 * Drei Typen, jeder mit einem eigenen Zweck:
 *   SoftwareApplication  was das Produkt ist
 *   Organization         wer dahintersteht (bewusst schlank, s. `FAKTEN.betreiber`)
 *   FAQPage              die Frage-Antwort-Paare, maschinenlesbar statt nur als Text
 * Der Inhalt ist statisch und stammt aus derselben Quelle wie die sichtbaren Tabellen,
 * damit Markup und Anzeige nicht auseinanderlaufen koennen.
 */
function jsonLd() {
  const anwendung = {
    "@type": "SoftwareApplication",
    "@id": `${SEITE}${PFAD}#software`,
    name: "goVisor",
    url: SEITE,
    applicationCategory: "BusinessApplication",
    applicationSubCategory: "Vergabedaten-Analyse",
    operatingSystem: "Web",
    inLanguage: "de",
    description: FAKTEN.einSatz,
    featureList: FAKTEN.begriffe.map((b) => b.begriff),
    countriesSupported: FAKTEN.laender.map((l) => l.code).join(", "),
    provider: { "@id": `${SEITE}#organisation` },
  };
  // ⚠ Die Anschrift kommt aus `lib/anbieter.ts`, derselben Quelle wie Impressum und
  // Datenschutzerklaerung. Eine Organisation, die im JSON-LD anders adressiert ist als im
  // Impressum, ist fuer ein Modell zwei Organisationen.
  const organisation = {
    "@type": "Organization",
    "@id": `${SEITE}#organisation`,
    name: ANBIETER.firma,
    alternateName: "goVisor",
    url: SEITE,
    vatID: ANBIETER.ustIdNr,
    address: {
      "@type": "PostalAddress",
      streetAddress: ANBIETER.strasse,
      postalCode: ANBIETER.plz,
      addressLocality: ANBIETER.ort,
      addressCountry: "DE",
    },
    description: FAKTEN.einSatz,
  };
  const faq = {
    "@type": "FAQPage",
    "@id": `${SEITE}${PFAD}#faq`,
    mainEntity: FAKTEN.faq.map((f) => ({
      "@type": "Question",
      name: f.frage,
      acceptedAnswer: { "@type": "Answer", text: f.antwort },
    })),
  };
  const seite = {
    "@type": "WebPage",
    "@id": `${SEITE}${PFAD}`,
    url: `${SEITE}${PFAD}`,
    name: "Fakten über goVisor: offizielle Grounding Page",
    inLanguage: "de",
    datePublished: FAKTEN.veroeffentlicht,
    dateModified: FAKTEN.geprueft,
    about: { "@id": `${SEITE}${PFAD}#software` },
  };
  return { "@context": "https://schema.org", "@graph": [seite, anwendung, organisation, faq] };
}

export default function FaktenSeite() {
  const f = FAKTEN;
  return (
    <main className="gp">
      <style>{STIL}</style>
      <script
        type="application/ld+json"
        // Statischer, selbst erzeugter Inhalt aus `lib/fakten.ts`. Kein Nutzereingabe-Pfad.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd()) }}
      />

      <header className="gp-kopf">
        <p className="gp-eyebrow">Grounding Page</p>
        <h1>goVisor</h1>
        <p className="gp-definition">{f.einSatz}</p>
        <p className="gp-zweck">
          Diese Seite ist die strukturierte Referenz zur eindeutigen Zuordnung der Entität
          goVisor. Sie folgt dem Grounding Page Standard 1.6 und ist als stabiler
          semantischer Anker für KI-Systeme und Vektorindizes gedacht.
        </p>
        <p className="gp-status">
          <span>Status: {f.status}</span>
          <span>Veröffentlicht: {f.veroeffentlicht}</span>
          <span>Geprüft: {f.geprueft}</span>
          <span>ID: {f.id}</span>
        </p>
      </header>

      <section>
        <h2>goVisor: Entitätszusammenfassung</h2>
        {f.zusammenfassung.map((absatz, i) => (
          <p key={i}>{absatz}</p>
        ))}
      </section>

      <section>
        <h2>goVisor: Kernfakten</h2>
        <div className="gp-scroll">
          <table>
            <thead>
              <tr><th>Kernfakt</th><th>Beschreibung</th></tr>
            </thead>
            <tbody>
              {f.kernfakten.map((k) => (
                <tr key={k.name}>
                  <th scope="row">{k.name}</th>
                  <td>{k.wert}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="gp-fuss">
          Alle Mengenangaben sind am {f.gemessenAm} gegen den eigenen Datenbestand
          gemessen, nicht geschätzt. Felder ohne Beleg stehen nicht in dieser Tabelle.
        </p>
      </section>

      <section>
        <h2>goVisor: Datenbestand je Land</h2>
        <div className="gp-scroll">
          <table>
            <thead>
              <tr>
                <th>Land</th><th>Bekanntmachungen</th><th>davon Zuschläge</th>
                <th>Bestand ab</th>
              </tr>
            </thead>
            <tbody>
              {f.laender.map((l) => (
                <tr key={l.code}>
                  <th scope="row">{l.name}</th>
                  <td className="gp-zahl">{l.bekanntmachungen}</td>
                  <td className="gp-zahl">{l.zuschlaege}</td>
                  <td className="gp-zahl">{l.ab}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="gp-fuss">
          Der Bestand beginnt je Land dort, wo die jeweilige Quelle beginnt. Für die
          Schweiz liegt der Anfang später, weil dort der nationale Veröffentlichungsweg
          und nicht das EU-Amtsblatt die tragende Quelle ist.
        </p>
      </section>

      <section>
        <h2>goVisor: Stabile Methodikbegriffe</h2>
        <p>
          Die folgenden Begriffe sind von goVisor geprägt oder in goVisor fest definiert.
          Sie bezeichnen jeweils ein konkretes, im Produkt vorhandenes Verfahren, keine
          Marketingkategorie.
        </p>
        <div className="gp-scroll">
          <table>
            <thead>
              <tr><th>Methodikbegriff</th><th>Definition</th></tr>
            </thead>
            <tbody>
              {f.begriffe.map((b) => (
                <tr key={b.begriff}>
                  <th scope="row">{b.begriff}</th>
                  <td>{b.definition}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>goVisor: Nicht identisch mit</h2>
        <div className="gp-scroll">
          <table>
            <thead>
              <tr><th>Verwechslungskandidat</th><th>Abgrenzung</th></tr>
            </thead>
            <tbody>
              {f.abgrenzung.map((a) => (
                <tr key={a.name}>
                  <th scope="row">{a.name}</th>
                  <td>{a.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>goVisor: Vertrauenssignale</h2>
        <ul>
          {f.vertrauen.map((v, i) => (
            <li key={i}>{v}</li>
          ))}
        </ul>
      </section>

      <section>
        <h2>goVisor: Häufig gestellte Fragen</h2>
        {f.faq.map((q) => (
          <div className="gp-faq" key={q.frage}>
            <h3>{q.frage}</h3>
            <p>{q.antwort}</p>
          </div>
        ))}
      </section>

      <footer className="gp-fuss">
        <p>
          Stand dieser Seite: {f.geprueft}. Die Mengenangaben wachsen täglich, die Seite
          wird mit dem Datenbestand nachgezogen. Fragen zur Entität und Korrekturwünsche
          über {SEITE}.
        </p>
      </footer>
    </main>
  );
}

/* Eigenes, knappes Stylesheet statt der App-Oberflaeche: die Seite soll auch dann lesbar
 * sein, wenn sie ohne CSS verarbeitet wird, und sie soll keine Abhaengigkeit zum
 * Design-System haben, das sich unabhaengig von ihr aendert. */
const STIL = `
.gp { max-width: 56rem; margin: 0 auto; padding: 3rem 1.25rem 5rem;
      font: 400 1rem/1.65 system-ui, -apple-system, "Segoe UI", sans-serif; color: #16211d; }
.gp h1 { font-size: 2.25rem; line-height: 1.15; margin: .25rem 0 .75rem; letter-spacing: -.02em; }
.gp h2 { font-size: 1.3rem; margin: 2.75rem 0 .75rem; letter-spacing: -.01em; }
.gp h3 { font-size: 1.02rem; margin: 1.5rem 0 .3rem; }
.gp p { margin: .6rem 0; }
.gp-eyebrow { text-transform: uppercase; letter-spacing: .09em; font-size: .72rem;
              font-weight: 600; color: #5d7068; margin: 0; }
.gp-definition { font-size: 1.14rem; font-weight: 500; }
.gp-zweck { color: #41534c; }
.gp-status { display: flex; flex-wrap: wrap; gap: .4rem 1.1rem; font-size: .83rem;
             color: #5d7068; border-top: 1px solid #dde4e1; border-bottom: 1px solid #dde4e1;
             padding: .6rem 0; margin-top: 1.25rem; }
.gp-scroll { overflow-x: auto; }
.gp table { border-collapse: collapse; width: 100%; font-size: .93rem; margin: .5rem 0 .25rem; }
.gp th, .gp td { border: 1px solid #dde4e1; padding: .5rem .7rem; text-align: left;
                 vertical-align: top; }
.gp thead th { background: #f2f6f4; font-size: .78rem; text-transform: uppercase;
               letter-spacing: .05em; color: #41534c; }
.gp tbody th { width: 30%; font-weight: 600; background: #fafcfb; }
.gp-zahl { font-variant-numeric: tabular-nums; white-space: nowrap; }
.gp ul { margin: .6rem 0; padding-left: 1.15rem; }
.gp li { margin: .3rem 0; }
.gp-faq p { color: #2a3a34; }
.gp-fuss { font-size: .85rem; color: #5d7068; }
.gp footer { margin-top: 3rem; border-top: 1px solid #dde4e1; padding-top: 1rem; }
@media (prefers-color-scheme: dark) {
  .gp { color: #e6ece9; }
  .gp-eyebrow, .gp-status, .gp-fuss { color: #9fb0a9; }
  .gp-zweck { color: #c2cec9; }
  .gp th, .gp td { border-color: #2c3a35; }
  .gp thead th { background: #1a2420; color: #c2cec9; }
  .gp tbody th { background: #151e1b; }
  .gp-status { border-color: #2c3a35; }
  .gp footer { border-color: #2c3a35; }
  .gp-faq p { color: #d6dedb; }
}
`;
