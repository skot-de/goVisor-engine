/**
 * Informationsdichte eines Leads — wie viel können wir über diese Vergabe sagen?
 *
 * **Warum es das gibt.** Gemessen 2026-08-16: nur **21,6 %** der offenen Ausschreibungen
 * haben bei uns überhaupt Unterlagen. Wer in einer Liste klickt, trifft mit vier von fünf
 * Klicks eine, zu der wir wenig sagen können. Ob das die Nutzer stört, wissen wir NICHT —
 * und genau diese Frage soll messbar werden, bevor wir ein Symbol dagegen bauen.
 *
 * **Warum keine Punktzahl.** Ein naives Zählen der vorhandenen Felder führt in die Irre:
 * einen Unterlagen-LINK haben 74,6 %, Lose 56,0 % — beides sagt nichts darüber, ob man die
 * Vergabe beurteilen kann. Das einzige Merkmal, das das bedeutet, ist „Signale aus den
 * Unterlagen gelesen", und das liegt bei 20,5 %. Eine Punktzahl hätte diese eine wichtige
 * Eigenschaft unter fünf billigen begraben.
 *
 * Gemessen über alle Fachgebiete (36.238 Leads):
 *
 *     reich     7.434   20,5 %   Unterlagen ausgewertet
 *     mittel    7.784   21,5 %   ausführlicher Text oder Frist + Lose
 *     dünn     21.020   58,0 %   nur Kopfdaten
 *
 * **Einschränkung, die dazugehört:** von den „reichen" tragen nur 32 % erfasste
 * Eignungsanforderungen; bei den übrigen kommt der Inhalt aus Bindefrist oder Bürgschaft.
 * Wer daraus ein Versprechen an der Oberfläche macht, muss das benennen — deshalb gibt
 * `merkmale()` zurück, was KONKRET vorliegt, statt nur eine Stufe.
 */

export type Dichte = "reich" | "mittel" | "duenn";

/**
 * Eingabe bewusst DURCHLÄSSIG. Die Lead-Objekte stammen aus JSON und tragen einen locker
 * gehaltenen Typ, der `anf`/`hasDetail` gar nicht deklariert. Hier eine enge Struktur zu
 * verlangen hiesse, am Aufrufort eine Typ-Zusicherung zu schreiben — und die behauptet
 * etwas, statt es zu prüfen. Also lieber hier prüfen, wo es hingehört.
 */
export type LeadArtig = Record<string, unknown> | null | undefined;

type Anf = {
  eignung?: unknown[]; zertifikate?: unknown[];
  bindefristTage?: number | null; buergschaft?: boolean | null;
};

function anfVon(l: LeadArtig): Anf {
  const a = (l as Record<string, unknown> | null)?.anf;
  return (a && typeof a === "object" ? a : {}) as Anf;
}

/** Wurden die Vergabeunterlagen ausgewertet? Das ist die eine Frage, die zählt. */
function unterlagenAusgewertet(l: LeadArtig): boolean {
  const a = anfVon(l);
  return Boolean(
    a.eignung?.length || a.zertifikate?.length || a.bindefristTage || a.buergschaft,
  );
}

export function dichte(l: LeadArtig): Dichte {
  if (!l) return "duenn";
  // REICH: die Unterlagen sind gelesen. Nur das trägt Checkliste, Eignungsabgleich und
  // Aufwandsschätzung — also alles, wofür man das Produkt benutzt.
  if (unterlagenAusgewertet(l)) return "reich";
  // MITTEL: keine Unterlagen, aber genug für eine erste Einschätzung aus der Bekanntmachung.
  if (l.hasDetail || (l.frist && l.lose)) return "mittel";
  return "duenn";
}

/**
 * Was konkret vorliegt — für Tooltips und für die Auswertung.
 *
 * Eine Stufe allein wäre für die spätere Frage „warum wurde geklickt/nicht geklickt" zu
 * grob: „reich wegen Eignung" und „reich wegen Bürgschaft" sind sehr verschiedene Leads.
 */
export function merkmale(l: LeadArtig): string[] {
  if (!l) return [];
  const a = anfVon(l);
  const m: string[] = [];
  if (a.eignung?.length) m.push("eignung");
  if (a.zertifikate?.length) m.push("zertifikate");
  if (a.bindefristTage) m.push("bindefrist");
  if (a.buergschaft) m.push("buergschaft");
  if (l.hasDetail) m.push("beschreibung");
  if (l.lose) m.push("lose");
  if (l.frist) m.push("frist");
  return m;
}
