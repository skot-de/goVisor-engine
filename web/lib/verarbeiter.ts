/**
 * Die Auftragsverarbeiter — und der Stand ihrer Vertraege.
 *
 * ⚠ WARUM DER VERTRAGSSTAND HIER ALS DATEN STEHT UND NICHT ALS SATZ IM TEXT.
 *
 * Eine Datenschutzerklaerung sagt ueblicherweise: „Die Uebermittlung erfolgt auf Grundlage
 * der Standardvertragsklauseln." Das ist kein beschreibender Satz, sondern eine
 * BEHAUPTUNG ueber einen abgeschlossenen Vertrag. Liegt der Vertrag nicht vor, ist der
 * Satz falsch — und zwar in dem Dokument, mit dem man seine Rechtmaessigkeit belegt.
 *
 * Genau das stand hier am 2026-10-02 drin, von mir geschrieben, ohne dass ein einziger
 * AV-Vertrag nachgewiesen war. Aufgefallen ist es erst, als eine Nachbarsitzung dieselbe
 * Voraussetzung unabhaengig aufschrieb.
 *
 * Deshalb steht der Stand jetzt als Feld, die Seite rendert danach, und
 * `tests/test_rechtstexte.py` ist rot, solange ein `avv` auf „offen" steht. Eine
 * unbelegte Rechtsgrundlage ist damit ein sichtbarer Blocker statt eines stillen Satzes.
 *
 * ⚠ DAS IST EINE KAUFMAENNISCHE AUFGABE, KEINE TECHNISCHE. Kein Code kann einen Vertrag
 * herbeifuehren; er kann nur verhindern, dass man ihn vergisst und trotzdem behauptet.
 */

export type AvvStand =
  /** Vertrag liegt vor, Beleg abgelegt. Erst dann darf die Seite ihn nennen. */
  | "liegt_vor"
  /** Noch nicht geschlossen. Die Seite nennt dann keine Rechtsgrundlage fuer diesen Weg. */
  | "offen";

export type Verarbeiter = {
  name: string;
  zweck: string;
  /** Wo verarbeitet wird. Nur nennen, was belegt ist. */
  ort: string;
  avv: AvvStand;
  /** Woher der Stand kommt, damit er nachpruefbar ist statt geglaubt. */
  beleg: string;
};

export const VERARBEITER: Verarbeiter[] = [
  {
    name: "Supabase",
    zweck: "Datenbank und Anmeldeverwaltung (Konto, Profil, gespeicherte Einstellungen)",
    // ⚠ Region ungeprueft, s. Kommentar in der Seite. Der Hostname steht hinter
    // Cloudflare-Anycast; sie steht im Dashboard unter Project Settings, General, Region.
    ort: "Region nach Projekteinstellung, Vertragspartner Supabase Pte. Ltd., Singapur",
    // Das DPA ist Bestandteil der Nutzungsbedingungen („supplements and forms part of the
    // Supabase Terms of Service", Version 1 vom 2026-08-01, supabase.com/legal/dpa). Es
    // gilt also mit dem Vertragsschluss, ohne gesonderte Unterschrift.
    avv: "liegt_vor",
    beleg: "supabase.com/legal/dpa, Bestandteil der ToS, geprueft 2026-10-02",
  },
  {
    name: "Vercel",
    zweck: "Betrieb der Webanwendung, Auslieferung der Seiten, Server-Protokolle",
    ort: "Vereinigte Staaten",
    // ⚠ VERCELS DPA GILT NUR AB PRO. Woertlich: „This Addendum applies to Vercel's
    // Processing of Personal Data as a Processor under the Agreement for Customers who are
    // on Enterprise and Pro plans" (vercel.com/legal/dpa, geprueft 2026-10-02). Auf dem
    // Hobby-Tarif gibt es keinen, und das laesst sich nicht erfragen, nur durch
    // Tarifwechsel loesen.
    avv: "offen",
    beleg: "vercel.com/legal/dpa deckt nur Pro und Enterprise; Tarif zu klaeren",
  },
  {
    name: "OpenRouter",
    zweck: "Auswertung hochgeladener Vergabeunterlagen durch ein Sprachmodell",
    /* ⚠ DER RECHENSTANDORT IST BEI UNS EINE PREISFOLGE, KEINE ENTSCHEIDUNG.
     *
     * `govisor/llm.py` haengt `:floor` an das Modell; das waehlt den guenstigsten der
     * sieben Endpunkte. Selbst abgerufen am 2026-10-03, nachpruefbar mit:
     *
     *   GET https://openrouter.ai/api/v1/models/google/gemini-2.5-flash/endpoints
     *   (Metadaten, kostet nichts; Schluessel aus .secrets/openrouter.key)
     *
     *   $/Mio ein  $/Mio aus  tag
     *       0.150      1.250  google-ai-studio/flex        ← den nimmt :floor
     *       0.300      2.500  google-ai-studio
     *       0.300      2.500  google-vertex
     *       0.300      2.500  google-vertex/eu             ← es GIBT einen EU-Endpunkt
     *       0.300      2.500  google-vertex/global
     *       0.540      4.500  google-ai-studio/priority
     *       0.540      4.500  google-vertex/global/priority
     *
     * ⚠ Die Region steht im Feld `tag`; `provider_region` ist bei allen sieben leer.
     *
     * Ein EU-Endpunkt existiert also und wird nur deshalb nicht genommen, weil er nicht
     * der guenstigste ist. Er ist dabei NICHT teurer als der Normalpreis — er liegt in
     * derselben Stufe wie drei andere. Der Aufpreis ist der Verzicht auf den Flex-Rabatt,
     * also ungefaehr eine Verdoppelung der LLM-Rechnung.
     *
     * ⓘ Das ist eine Produktentscheidung mit Preisschild und gehoert Sven vorgelegt, nicht
     * in diese Datei: `google-vertex/eu` festnageln macht aus einer Drittlandsuebermittlung
     * eine EU-Verarbeitung. Solange `:floor` gilt, gilt der Text unten.
     *
     * ⚠ UND `:floor` ALLEIN ZWINGT NICHT. `llm.py` hat das gemessen: ueber 311 Aufrufe,
     * alle mit `:floor` gesendet, liefen **304 ueber die Standardstufe** (Vertex) und nur
     * 5 ueber Flex, weil `allow_fallbacks` eine Stufe hoeher geht, sobald der billigste
     * Endpunkt nicht sofort liefert. Was zwingt, ist der Preisdeckel `max_price`, und der
     * steht seit `OR_STRENG` standardmaessig an.
     *
     * Fuer den Standort heisst das: MIT Deckel landet der Aufruf verlaesslich auf
     * `google-ai-studio/flex`, OHNE Deckel driftet er auf Vertex. Keiner von beiden ist
     * der EU-Endpunkt — die Aussage „ausserhalb der EU" gilt also in beiden Faellen, nur
     * die Begruendung ist eine andere. */
    ort: "Vereinigte Staaten und weitere, Rechenstandort nach Preis gewaehlt",
    // OpenRouters Datenschutzerklaerung kennt AV-Vertraege („If you have a Data Processing
    // Agreement with us"), bietet sie aber nicht zum Selbstbedienen an. Anzufragen.
    avv: "offen",
    beleg: "openrouter.ai/privacy nennt DPAs nur auf Anfrage; nicht geschlossen. "
      + "Endpunkte und Preise am 2026-10-03 ueber die OpenRouter-API abgerufen.",
  },
];

/** Verarbeiter ohne Vertrag. Leer heisst: die Seite darf eine Rechtsgrundlage nennen. */
export function ohneVertrag(): Verarbeiter[] {
  return VERARBEITER.filter((v) => v.avv === "offen");
}
