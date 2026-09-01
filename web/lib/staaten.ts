/* Welche Länder goVisor führt — die EINE Stelle im Frontend.
 *
 * WARUM ES DIESE DATEI GIBT. Am 2026-09-01 versprach das Onboarding „jede öffentliche
 * Vergabe in **Deutschland**", während 8.405 von 24.505 Leads (34 %) aus Österreich und der
 * Schweiz kamen. Der Satz war nicht falsch getippt, sondern **stehengeblieben**: er wurde
 * geschrieben, als DE das einzige Land war, und niemand fasst einen Fliesstext an, wenn eine
 * Datenquelle dazukommt. Genau die Altlast, die der EU-weit-Grundsatz meint (CLAUDE.md).
 *
 * Deshalb steht die Liste hier und nicht im Satz. Ein viertes Land ist eine Zeile, und das
 * Versprechen auf der Oberfläche wandert von allein mit.
 *
 * ⚠ ZWEI FORMEN, NICHT EINE. „in der Schweiz", nicht „in Schweiz" — die Präposition steckt
 * im Satz, der Artikel am Land. `components/Marktpuls.tsx` hatte das bereits gelöst und
 * begründet; hier stand dieselbe Liste ein zweites Mal, in FilterPanel, ohne die Dativform.
 * Zwei Listen heisst: ein neues Land wird an einer von beiden vergessen.
 *
 * ⚠ NICHT AN DER DEFINITION ÜBERSETZEN. Modul-Konstanten werden beim Import ausgewertet —
 * durch `t()` gingen sie mit der Sprache des ersten Ladens und blieben dort stehen. Das ist
 * Falle 1 aus der i18n-Mechanik und hat in dieser Datei-Familie schon zugeschlagen.
 * Hier stehen deutsche Literale; übersetzt wird beim Rendern.
 */

/** Code → Name im Nominativ. Reihenfolge = Anzeigereihenfolge (Bestand absteigend). */
export const STAATEN: [string, string][] = [
  ["DE", "Deutschland"], ["AT", "Österreich"], ["CH", "Schweiz"],
];

/** Code → Form nach „in …". Siehe die Dativ-Warnung oben. */
export const LAND_IN: Record<string, string> = {
  DE: "Deutschland", AT: "Österreich", CH: "der Schweiz",
};

/** „Deutschland, Österreich und der Schweiz" — als Baustein für einen Satz mit `{laender}`.
 *
 *  ⚠ Die Namen gehen EINZELN durch `t()`, nicht der fertige Satzteil: sonst stünde in der
 *  englischen Fassung „every public tender in Deutschland, Österreich und der Schweiz".
 *  Auch das „und" ist übersetzt — im Französischen ist es „et", und ein hartes „und" fiele
 *  mitten im Satz auf, ohne dass ein Guard es meldet. */
export function staatenAufzaehlung(t: (s: string) => string): string {
  const namen = STAATEN.map(([code]) => t(LAND_IN[code] ?? code));
  if (namen.length <= 1) return namen[0] ?? "";
  return `${namen.slice(0, -1).join(", ")} ${t("und")} ${namen[namen.length - 1]}`;
}
