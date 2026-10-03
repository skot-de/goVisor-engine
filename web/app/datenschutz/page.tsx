import type { Metadata } from "next";
import RechtsSeite from "@/components/RechtsSeite";
import { ANBIETER, anschrift } from "@/lib/anbieter";
import { VERARBEITER, ohneVertrag } from "@/lib/verarbeiter";

/**
 * Datenschutzerklaerung — und zwar die, die zu DIESER Anwendung gehoert.
 *
 * ⚠ JEDER ABSCHNITT IST AM CODE GEMESSEN, nicht aus einer Vorlage uebernommen. Eine
 * Datenschutzerklaerung ist nur dann richtig, wenn sie beschreibt, was die Anwendung
 * tatsaechlich tut; eine Vorlage beschreibt, was eine gedachte Anwendung tut. Gemessen am
 * 2026-10-02 (Tabellen in `supabase/`, ausgehende Aufrufe in `web/lib`, Cookies in
 * `web/middleware.ts`, Upload-Pfad in `scripts/process_upload.py`).
 *
 * Was dabei herauskam und in keiner Vorlage stuende:
 *   · Es gibt KEINE Reichweitenmessung und KEINE Marketing-Cookies. Deshalb braucht diese
 *     Anwendung auch kein Einwilligungsbanner. Das ist eine Aussage ueber den Code, keine
 *     Absichtserklaerung.
 *   · Hochgeladene Vergabeunterlagen gehen an ein Sprachmodell in den USA. Das ist der
 *     eingriffsintensivste Vorgang der ganzen Anwendung und muss entsprechend dastehen.
 *   · Zahlung und Mailversand sind vorbereitet, aber ohne Schluessel nicht scharf. Sie als
 *     laufende Verarbeitung zu beschreiben waere falsch, sie wegzulassen auch.
 *
 * ⚠ DIESER TEXT IST EIN FACHLICH BELEGTER ENTWURF, KEINE RECHTSBERATUNG. Die Zuordnung der
 * Rechtsgrundlagen und die Formulierungen gehoeren vor dem Start einmal durch eine
 * anwaltliche Durchsicht. Was hier steht, ist die Sachverhaltsgrundlage dafuer, und die
 * ist der Teil, den nur jemand mit Zugriff auf den Code liefern kann.
 */

export const metadata: Metadata = {
  title: "Datenschutzerklärung",
  description: "Welche Daten goVisor verarbeitet, zu welchem Zweck und wie lange.",
  alternates: { canonical: "/datenschutz" },
  robots: { index: true, follow: true },
};



export default function DatenschutzSeite() {
  return (
    <RechtsSeite
      titel="Datenschutzerklärung"
      stand="2026-10-02"
      kinder={
        <>
          <h2>1. Verantwortlicher</h2>
          <address className="rs-anschrift">
            {anschrift().map((zeile) => (
              <span key={zeile}>
                {zeile}
                <br />
              </span>
            ))}
            Vertreten durch {ANBIETER.vertreten}
          </address>
          {ANBIETER.datenschutzbeauftragter ? (
            <p>Datenschutzbeauftragter: {ANBIETER.datenschutzbeauftragter}</p>
          ) : (
            <p>
              Ein Datenschutzbeauftragter ist nicht benannt. Die gesetzlichen
              Voraussetzungen für eine Benennungspflicht liegen derzeit nicht vor.
            </p>
          )}

          <h2>2. Der kurze Überblick</h2>
          <p>
            goVisor wertet öffentlich bekannt gemachte Vergabeinformationen aus. Der weit
            überwiegende Teil der verarbeiteten Daten stammt daher aus amtlichen
            Veröffentlichungen und betrifft Unternehmen und Vergabestellen, nicht Sie.
            Personenbezogene Daten über Sie verarbeiten wir vor allem dort, wo Sie ein Konto
            führen.
          </p>
          <p>
            <strong>
              Wir setzen keine Reichweitenmessung, keine Analysewerkzeuge und keine
              Marketing-Cookies ein.
            </strong>{" "}
            Aus diesem Grund fragt diese Seite auch nicht nach einer Einwilligung für
            Cookies. Die wenigen Cookies, die gesetzt werden, sind für den Betrieb
            erforderlich und werden unter Punkt 4 einzeln benannt.
          </p>

          <h2>3. Aufruf der Website</h2>
          <p>
            Beim Aufruf übermittelt Ihr Browser technisch notwendige Daten an unseren
            Hoster, der sie in Server-Protokollen festhält: IP-Adresse, Zeitpunkt der
            Anfrage, aufgerufene Adresse, übertragene Datenmenge, Browserkennung und
            übermittelte Herkunftsseite. Diese Daten sind erforderlich, um die Seite
            auszuliefern und den Betrieb abzusichern.
          </p>
          <p>
            Rechtsgrundlage ist unser berechtigtes Interesse am sicheren und
            funktionsfähigen Betrieb (Artikel 6 Absatz 1 Buchstabe f DSGVO).
          </p>

          <h2>4. Cookies</h2>
          <p>Gesetzt werden ausschließlich diese Cookies:</p>
          <div className="rs-scroll">
            <table>
              <thead>
                <tr>
                  <th>Cookie</th>
                  <th>Zweck</th>
                  <th>Dauer</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">Anmeldung</th>
                  <td>
                    Hält Ihre Sitzung aufrecht, damit Sie nicht bei jedem Seitenwechsel neu
                    angemeldet werden müssen. Wird von unserem Anmeldedienst gesetzt.
                  </td>
                  <td>Sitzung bis Abmeldung</td>
                </tr>
                <tr>
                  <th scope="row">gv_preview</th>
                  <td>
                    Merkt sich, dass ein Vorschauzugang während der Aufbauphase genutzt
                    wurde, damit der Schlüssel nicht in jeder Adresse mitgeführt werden muss.
                  </td>
                  <td>30 Tage</td>
                </tr>
                <tr>
                  <th scope="row">gv_vorhang</th>
                  <td>
                    Erfüllt denselben Zweck für den zweiten Zugangsweg während der
                    Aufbauphase.
                  </td>
                  <td>30 Tage</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p>
            Alle drei sind für die von Ihnen gewünschte Nutzung unbedingt erforderlich
            (§ 25 Absatz 2 Nummer 2 TDDDG). Eine Einwilligung ist dafür nicht nötig.
          </p>

          <h2>5. Nutzerkonto und Suchprofil</h2>
          <p>
            Für ein Konto verarbeiten wir Ihre E-Mail-Adresse und ein Passwort, das nur als
            Prüfwert gespeichert wird. Hinzu kommen die Angaben, die Sie selbst machen: der
            Name Ihres Unternehmens sowie Ihr Suchprofil, also die Leistungsbereiche
            (CPV-Codes), Regionen und Auftragsgrößen, für die Sie Ausschreibungen angezeigt
            bekommen wollen.
          </p>
          <p>
            Dazu kommen die Daten, die bei der Nutzung entstehen: welche Ausschreibungen Sie
            sich gemerkt, ausgeblendet oder mit einem Bearbeitungsstand versehen haben,
            welche Vergabestellen Sie beobachten, Ihre Benachrichtigungseinstellungen und
            gespeicherte Filter.
          </p>
          <p>
            Rechtsgrundlage ist die Erfüllung des Nutzungsvertrags (Artikel 6 Absatz 1
            Buchstabe b DSGVO).
          </p>

          <h2>6. Prüfung der Unternehmenszugehörigkeit</h2>
          <p>
            Bei der Registrierung prüfen wir, ob die Domain Ihrer E-Mail-Adresse zu dem
            Unternehmen gehört, dessen Profil Sie nutzen möchten. Dazu ruft unser Server die
            Anbieterkennung der betreffenden Internetseite ab und vergleicht sie mit den uns
            vorliegenden Firmendaten.
          </p>
          <p>
            Gespeichert wird dabei nur das Ergebnis dieser Prüfung, nicht der Inhalt der
            abgerufenen Seite. Die Prüfung läuft auf unserem Server, nicht in Ihrem Browser.
            Rechtsgrundlage ist unser berechtigtes Interesse daran, dass Unternehmensprofile
            nicht von Unbefugten übernommen werden (Artikel 6 Absatz 1 Buchstabe f DSGVO).
          </p>

          <h2>7. Auswertung hochgeladener Vergabeunterlagen</h2>
          <p>
            Wenn Sie Vergabeunterlagen hochladen, werden deren Texte zur Auswertung an einen
            Dienstleister für Sprachmodelle übermittelt (OpenRouter, Vereinigte Staaten).
            Dort werden sie verarbeitet, um Eignungsnachweise, Zuschlagskriterien, Fristen
            und Leistungspositionen zu erkennen.
          </p>
          <div className="rs-hinweis">
            <strong>Bitte beachten Sie:</strong> Vergabeunterlagen enthalten gelegentlich
            Namen und Kontaktdaten von Ansprechpartnern der Vergabestelle. Diese Angaben
            werden derzeit mit übertragen. Laden Sie keine Unterlagen hoch, die darüber
            hinaus personenbezogene Daten enthalten, insbesondere keine Lebensläufe,
            Personallisten oder Angebotsunterlagen mit Personendaten.
          </div>
          <p>
            Rechtsgrundlage ist die Erfüllung des Nutzungsvertrags (Artikel 6 Absatz 1
            Buchstabe b DSGVO), soweit die Auswertung die von Ihnen angeforderte Leistung
            ist.
          </p>

          <h2>8. Schutz vor missbräuchlicher Nutzung</h2>
          <p>
            Einzelne Funktionen sind gegen übermäßige Abfragen gebremst. Dafür wird Ihre
            IP-Adresse kurzzeitig im Arbeitsspeicher des Servers gehalten und gezählt. Eine
            dauerhafte Speicherung oder eine Zusammenführung mit Ihrem Konto findet nicht
            statt. Rechtsgrundlage ist unser berechtigtes Interesse an der Abwehr von
            Missbrauch (Artikel 6 Absatz 1 Buchstabe f DSGVO).
          </p>

          <h2>9. Kalender-Feed</h2>
          <p>
            Sie können Fristen als Kalender abonnieren. Der Zugang erfolgt über eine Adresse
            mit einem geheimen Bestandteil; wer diese Adresse kennt, sieht die darin
            enthaltenen Termine. Behandeln Sie die Adresse deshalb wie ein Passwort und
            geben Sie sie nicht weiter.
          </p>

          <h2>10. Benachrichtigungen und Zahlungen</h2>
          <p>
            Benachrichtigungen per E-Mail und die Abwicklung von Zahlungen sind in der
            Anwendung vorbereitet, derzeit aber nicht in Betrieb. Es werden gegenwärtig
            weder Benachrichtigungen versendet noch Zahlungsdaten erhoben oder an einen
            Zahlungsdienstleister übermittelt. Sobald sich das ändert, wird diese Erklärung
            vorher angepasst.
          </p>

          <h2>11. Empfänger</h2>
          <p>
            Wir setzen folgende Dienstleister ein, die Daten in unserem Auftrag und nach
            unseren Weisungen verarbeiten:
          </p>
          <div className="rs-scroll">
            <table>
              <thead>
                <tr>
                  <th>Empfänger</th>
                  <th>Zweck</th>
                  <th>Ort der Verarbeitung</th>
                </tr>
              </thead>
              <tbody>
                {VERARBEITER.map((e) => (
                  <tr key={e.name}>
                    <th scope="row">{e.name}</th>
                    <td>{e.zweck}</td>
                    <td>{e.ort}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>
            Eine Weitergabe Ihrer Daten zu Werbezwecken oder ein Verkauf an Dritte findet
            nicht statt.
          </p>

          <h2>12. Übermittlung in Drittländer</h2>
          {/* ⚠ HIER STAND EINE BEHAUPTUNG, KEINE BESCHREIBUNG. Der uebliche Satz „erfolgt
              auf Grundlage der Standardvertragsklauseln" sagt, dass ein Vertrag
              geschlossen WURDE. Liegt er nicht vor, ist der Satz falsch, und zwar in dem
              Dokument, mit dem man seine Rechtmaessigkeit belegt. Deshalb haengt er jetzt
              am gepflegten Vertragsstand in `lib/verarbeiter.ts` und erscheint erst,
              wenn fuer alle Empfaenger ein Vertrag vermerkt ist. */}
          {ohneVertrag().length === 0 ? (
            <p>
              Soweit die unter Punkt 11 genannten Dienstleister Daten ausserhalb der
              Europäischen Union verarbeiten, erfolgt die Übermittlung auf Grundlage der
              Standardvertragsklauseln der Europäischen Kommission oder, soweit der
              jeweilige Anbieter zertifiziert ist, auf Grundlage des
              Angemessenheitsbeschlusses zum EU-US Data Privacy Framework.
            </p>
          ) : (
            <p>
              Ein Teil der unter Punkt 11 genannten Dienstleister verarbeitet Daten
              ausserhalb der Europäischen Union. Die vertragliche Grundlage dieser
              Übermittlungen wird derzeit abgeschlossen; bis dahin machen wir dazu keine
              Angabe, die wir nicht belegen können. Diese Erklärung wird ergänzt, sobald
              die Verträge vorliegen.
            </p>
          )}

          <h2>13. Speicherdauer</h2>
          <ul>
            <li>
              Kontodaten und Suchprofil: bis zur Löschung Ihres Kontos. Nach der Löschung
              werden sie entfernt, soweit keine gesetzliche Aufbewahrungspflicht entgegensteht.
            </li>
            <li>Server-Protokolle: wenige Tage, nach Vorgabe unseres Hosters.</li>
            <li>Zählwerte der Missbrauchsbremse: Minuten, nur im Arbeitsspeicher.</li>
            <li>
              Hochgeladene Unterlagen und ihre Auswertung: bis Sie sie löschen oder Ihr
              Konto beenden.
            </li>
          </ul>

          <h2>14. Ihre Rechte</h2>
          <p>Sie haben uns gegenüber das Recht auf</p>
          <ul>
            <li>Auskunft über die zu Ihnen gespeicherten Daten (Artikel 15 DSGVO),</li>
            <li>Berichtigung unrichtiger Daten (Artikel 16 DSGVO),</li>
            <li>Löschung (Artikel 17 DSGVO),</li>
            <li>Einschränkung der Verarbeitung (Artikel 18 DSGVO),</li>
            <li>Datenübertragbarkeit (Artikel 20 DSGVO),</li>
            <li>
              Widerspruch gegen Verarbeitungen, die auf einem berechtigten Interesse beruhen
              (Artikel 21 DSGVO).
            </li>
          </ul>
          <p>
            Eine erteilte Einwilligung können Sie jederzeit mit Wirkung für die Zukunft
            widerrufen. Wenden Sie sich für alle genannten Rechte an die im{" "}
            <a href="/impressum">Impressum</a> genannte Anschrift.
          </p>

          <h2>15. Beschwerderecht</h2>
          <p>
            Sie können sich bei einer Datenschutz-Aufsichtsbehörde beschweren. Für uns
            zuständig ist die Landesbeauftragte für Datenschutz und Informationsfreiheit
            Nordrhein-Westfalen, Kavalleriestraße 2 bis 4, 40213 Düsseldorf.
          </p>

          <h2>16. Änderungen dieser Erklärung</h2>
          <p>
            Wir passen diese Erklärung an, wenn sich die Verarbeitung ändert. Maßgeblich ist
            die jeweils hier veröffentlichte Fassung mit dem oben genannten Stand.
          </p>
        </>
      }
    />
  );
}
