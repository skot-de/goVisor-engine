/**
 * Der eine Wert, den der Eignungs-Check nach unten weiterreicht.
 *
 * **Warum ein Speicher und kein Zustand im Elternteil.** Der Check ist ein Client-Baustein
 * mitten in einer Seite, die auf dem Server gerendert wird; die Massen-Spalte zwei
 * Abschnitte tiefer ist ein anderer Baustein im selben Baum. Den Zustand nach oben zu
 * ziehen hiesse, die ganze Startseite zum Client-Baustein zu machen — für einen Satz.
 * Also ein winziger Speicher mit `useSyncExternalStore`: der Check schreibt, wer will,
 * hört zu.
 *
 * **Was hier NICHT passiert.** Nichts wird gespeichert, gesendet oder wiederhergestellt.
 * Der Wert lebt in dieser einen Seitenansicht und ist beim Neuladen weg — dieselbe Zusage
 * wie im Check selbst („nichts davon verlässt euren Browser"), und die einzige Fassung, in
 * der ein persönliches Ergebnis auf einer öffentlichen Seite vertretbar ist.
 */
export type CheckErgebnis = {
  fachLabel: string;
  erfuellt: number;
  von: number;
  luecke: string | null;
} | null;

let wert: CheckErgebnis = null;
const hoerer = new Set<() => void>();

export function setzeCheckErgebnis(neu: CheckErgebnis): void {
  // Gleicher Inhalt, keine Benachrichtigung: sonst rendert die Massen-Spalte bei jedem
  // Klick im Check neu, auch wenn sich an ihrer Aussage nichts ändert.
  if (JSON.stringify(neu) === JSON.stringify(wert)) return;
  wert = neu;
  for (const h of hoerer) h();
}

export function abonniereCheckErgebnis(h: () => void): () => void {
  hoerer.add(h);
  return () => { hoerer.delete(h); };
}

export const leseCheckErgebnis = (): CheckErgebnis => wert;
/** Auf dem Server gibt es kein Ergebnis — und muss es geben, sonst bricht die Hydration. */
export const leseCheckErgebnisServer = (): CheckErgebnis => null;
