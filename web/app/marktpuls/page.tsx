import { loadDataFile } from "@/lib/dataSource";
import Marktpuls, { type MarktpulsDaten } from "@/components/Marktpuls";

/**
 * Vorschau-/Referenz-Einbau des Marktpuls-Elements.
 *
 * Der eigentliche Einbauort ist laut Briefing (§1, §9-1) noch offen — Landingpage, Blog oder
 * Strategie-Bereich. Diese Seite ist deshalb KEIN Produktbereich, sondern die Stelle, an der
 * das Element ansehbar und prüfbar ist, und zugleich das Muster für den späteren Einbau:
 * die Server-Komponente lädt das vorberechnete JSON und reicht es als Prop durch, so dass
 * das Element vollständig ohne JavaScript-Nachladen rendert (Briefing §5).
 *
 * Wer es woanders einbaut, kopiert genau diese vier Zeilen — mehr braucht das Element nicht.
 */
export const revalidate = 3600;

export const metadata = {
  title: "Marktpuls — öffentliche Vergaben im Jahresverlauf",
  description:
    "Wann wird ausgeschrieben, und was läuft gerade? Saisonalität und aktuelle Marktlage "
    + "öffentlicher Vergaben, gezählt je Verfahren.",
};

export default async function MarktpulsSeite() {
  const roh = await loadDataFile("marktpuls.json");
  let daten: MarktpulsDaten | null = null;
  try {
    daten = roh ? (JSON.parse(roh) as MarktpulsDaten) : null;
  } catch {
    daten = null;                       // kaputte Datei → das Element zeigt seinen Fehlerfall
  }

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: "32px 20px 64px" }}>
      <Marktpuls daten={daten} />
    </main>
  );
}
