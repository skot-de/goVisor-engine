/**
 * Testprofile — mit welcher Kundensicht man sich einwählt.
 *
 * WARUM ZWEI ARTEN. Sie sehen gleich aus und sind es nicht:
 *
 *   `test`        volle Rechte. Zum Durchklicken, Formulare ausfüllen, Zustände erzeugen.
 *   `vorfuehrung` NUR LESEN. Zum Zeigen — man klickt vor Publikum und kann nichts kaputt
 *                 machen, auch nicht versehentlich.
 *
 * Die Trennung ist nicht Bequemlichkeit, sondern Schadensbegrenzung: der teuerste Fehler in
 * einer Demo ist der, bei dem man live in echten Daten etwas verändert und es erst merkt,
 * wenn ein Kunde sich über seine Zahlen wundert.
 *
 * ⚠ DER SCHREIBSCHUTZ HIER IST NUR DIE HALBE MIETE. Er verhindert, dass die Oberfläche
 * Schreib-Aktionen anbietet. Verbindlich durchsetzen kann ihn nur der Server (RLS bzw. die
 * API-Route) — ein Client-Flag ist eine Bequemlichkeit, keine Sicherheitsgrenze. Solange die
 * Profile ausschließlich aus dieser Liste kommen und auf eigene Test-Konten zeigen, ist das
 * vertretbar; sobald ein Profil auf ECHTE Kundendaten zeigt, muss die Prüfung serverseitig
 * nachgezogen werden. Das ist hier bewusst als offener Punkt vermerkt und nicht stillschweigend
 * als erledigt behandelt.
 */

export type ProfilArt = "test" | "vorfuehrung";

export type Testprofil = {
  id: string;
  name: string;
  art: ProfilArt;
  /** Was dieses Profil zeigen soll — steuert Onboarding-Vorbelegung und Relevanz. */
  beschreibung: string;
  branche: string;
  ort?: string;
};

/**
 * Bewusst im Code und nicht in der Datenbank: die Liste ist Teil des Testaufbaus, sie soll
 * versioniert sein und in einem Review auffallen, wenn jemand ein Profil hinzufügt.
 */
export const TESTPROFILE: Testprofil[] = [
  {
    id: "test-bau",
    name: "Bauunternehmen (Test)",
    art: "test",
    beschreibung: "Mittelständischer Hochbau, Umkreis 50 km — der häufigste Fall.",
    branche: "bau",
    ort: "Dortmund",
  },
  {
    id: "test-it",
    name: "IT-Dienstleister (Test)",
    art: "test",
    beschreibung: "Software und Betrieb, bundesweit — prüft die Ortsunabhängigkeit.",
    branche: "it",
  },
  {
    id: "demo-bau",
    name: "Bauunternehmen (Vorführung)",
    art: "vorfuehrung",
    beschreibung: "Wie das Test-Bauunternehmen, aber schreibgeschützt.",
    branche: "bau",
    ort: "Dortmund",
  },
  {
    id: "demo-it",
    name: "IT-Dienstleister (Vorführung)",
    art: "vorfuehrung",
    beschreibung: "Wie der Test-IT-Dienstleister, aber schreibgeschützt.",
    branche: "it",
  },
];

export const PROFIL_COOKIE = "gv_profil";

export function profilVonId(id: string | null | undefined): Testprofil | null {
  if (!id) return null;
  return TESTPROFILE.find((p) => p.id === id) ?? null;
}

/** Darf in dieser Sitzung geschrieben werden? Ohne gewähltes Profil: ja (normaler Betrieb). */
export function darfSchreiben(profil: Testprofil | null): boolean {
  return profil === null || profil.art === "test";
}

/** Aktuell gewaehltes Profil aus dem Cookie. Nur im Browser sinnvoll.
 *
 * Steht hier und nicht in der Startseite: eine Next.js-Seite darf ausser der Komponente und
 * ein paar bekannten Feldern nichts exportieren — der Build bricht sonst ab. Und der Banner
 * braucht dieselbe Funktion, zwei Kopien waeren der Anfang vom Auseinanderlaufen.
 */
export function gewaehltesProfil(): Testprofil | null {
  if (typeof document === "undefined") return null;
  const treffer = document.cookie.match(new RegExp(`(?:^|; )${PROFIL_COOKIE}=([^;]*)`));
  return profilVonId(treffer ? decodeURIComponent(treffer[1]) : null);
}
