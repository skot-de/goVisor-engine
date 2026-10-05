import type { Metadata } from "next";
import RechtsSeite from "@/components/RechtsSeite";
import { ANBIETER, anschrift, fehlendePflichtangaben } from "@/lib/anbieter";

/**
 * Anbieterkennung nach § 5 DDG (bis 2024: § 5 TMG).
 *
 * ⚠ DIESE SEITE MUSS OHNE ANMELDUNG UND OHNE UMWEG ERREICHBAR SEIN. Ein Impressum hinter
 * der Coming-Soon-Sperre ist kein Impressum; die Pflicht knuepft an die Erreichbarkeit des
 * Angebots, nicht an den Zustand der Baustelle. Verdrahtet in `web/middleware.ts` ueber
 * `RECHTLICHES`, zusammen mit der Datenschutzerklaerung.
 *
 * ⚠ WAS HIER STEHT, IST GEPRUEFT ODER ES STEHT NICHT DA. Fehlende Pflichtangaben werden
 * nicht durch Platzhalter ersetzt und nicht geraten — sie fehlen sichtbar, und
 * `tests/test_rechtstexte.py` meldet sie, bis sie da sind. Eine erfundene Registernummer
 * waere schlimmer als eine fehlende: sie sieht richtig aus.
 */

const SEITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://govisor.eu";

export const metadata: Metadata = {
  title: "Impressum",
  description: `Anbieterkennung nach § 5 DDG für ${SEITE}.`,
  alternates: { canonical: "/impressum" },
  robots: { index: true, follow: true },
};

export default function ImpressumSeite() {
  const fehlt = fehlendePflichtangaben();
  return (
    <RechtsSeite
      titel="Impressum"
      stand="2026-10-02"
      kinder={
        <>
          <h2>Angaben gemäß § 5 DDG</h2>
          <address className="rs-anschrift">
            {anschrift().map((zeile) => (
              <span key={zeile}>
                {zeile}
                <br />
              </span>
            ))}
          </address>

          <h2>Vertreten durch</h2>
          <p>{ANBIETER.vertreten}, Geschäftsführer</p>

          {ANBIETER.email || ANBIETER.telefon ? (
            <>
              <h2>Kontakt</h2>
              {ANBIETER.email ? (
                <p>
                  E-Mail: <a href={`mailto:${ANBIETER.email}`}>{ANBIETER.email}</a>
                </p>
              ) : null}
              {ANBIETER.telefon ? <p>Telefon: {ANBIETER.telefon}</p> : null}
            </>
          ) : null}

          {ANBIETER.registergericht && ANBIETER.registernummer ? (
            <>
              <h2>Registereintrag</h2>
              <p>
                Registergericht: {ANBIETER.registergericht}
                <br />
                Registernummer: {ANBIETER.registernummer}
              </p>
            </>
          ) : null}

          <h2>Umsatzsteuer-Identifikationsnummer</h2>
          <p>Gemäß § 27 a Umsatzsteuergesetz: {ANBIETER.ustIdNr}</p>

          {fehlt.length ? (
            <div className="rs-hinweis">
              <strong>Diese Anbieterkennung ist noch nicht vollständig.</strong> Es fehlen:{" "}
              {fehlt.join(", ")}. Die Angaben werden ergänzt, sobald sie vorliegen. Bis
              dahin erreichen Sie uns postalisch unter der oben genannten Anschrift.
            </div>
          ) : null}

          <h2>Verbraucherstreitbeilegung</h2>
          <p>
            Wir sind nicht bereit und nicht verpflichtet, an Streitbeilegungsverfahren vor
            einer Verbraucherschlichtungsstelle teilzunehmen.
          </p>

          <h2>Haftung für Inhalte</h2>
          <p>
            Als Diensteanbieter sind wir für eigene Inhalte auf diesen Seiten nach den
            allgemeinen Gesetzen verantwortlich. Wir sind nicht verpflichtet, übermittelte
            oder gespeicherte fremde Informationen zu überwachen oder nach Umständen zu
            forschen, die auf eine rechtswidrige Tätigkeit hinweisen. Verpflichtungen zur
            Entfernung oder Sperrung der Nutzung von Informationen nach den allgemeinen
            Gesetzen bleiben hiervon unberührt. Eine diesbezügliche Haftung ist erst ab dem
            Zeitpunkt der Kenntnis einer konkreten Rechtsverletzung möglich. Bei Bekanntwerden
            entsprechender Rechtsverletzungen entfernen wir diese Inhalte umgehend.
          </p>

          <h2>Hinweis zu den dargestellten Vergabedaten</h2>
          <p>
            goVisor wertet öffentlich bekannt gemachte Vergabeinformationen aus, insbesondere
            aus dem Amtsblatt der Europäischen Union (TED) und aus nationalen
            Veröffentlichungsstellen. Verbindlich ist in jedem Fall allein die
            Bekanntmachung der jeweiligen Vergabestelle. Auswertungen, Prognosen und
            abgeleitete Kennzahlen von goVisor sind keine amtlichen Angaben und begründen
            keinen Anspruch.
          </p>

          <h2>Haftung für Links</h2>
          <p>
            Unser Angebot enthält Links zu externen Webseiten Dritter, auf deren Inhalte wir
            keinen Einfluss haben. Deshalb können wir für diese fremden Inhalte auch keine
            Gewähr übernehmen. Für die Inhalte der verlinkten Seiten ist stets der jeweilige
            Anbieter oder Betreiber der Seiten verantwortlich.
          </p>

          <p className="rs-fuss">
            Datenschutzhinweise finden Sie unter <a href="/datenschutz">Datenschutz</a>.
          </p>
        </>
      }
    />
  );
}
