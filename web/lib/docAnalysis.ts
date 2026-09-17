import "server-only";
import { ladeMitGrund, DATEN_STOERUNG, ausSpeicher, inSpeicher } from "@/lib/dataSource";

/* Welche Vorgaenge haben AUSGEWERTETE Vergabeunterlagen — und wie dicht?
 *
 * ⚠ WARUM ES DIESE DATEI GIBT. `scripts/export_doc_analysis.py` schreibt seit Ticket 23
 * einen Index ueber alle Auswertungen. Bis zum 2026-09-17 las ihn NIEMAND: kein Treffer
 * fuer „doc-analysis-index" unter `web/`. Die Oberflaeche konnte deshalb nicht sagen,
 * welche Ausschreibung ausgewertete Unterlagen hat — man musste jede einzeln oeffnen.
 * Das ist die Fehlerklasse „gebaut, nicht verdrahtet", siehe `pruefe_verdrahtung.py`.
 *
 * ⚠ WARUM NICHT DIE AMPEL ALLEIN. Gemessen ueber alle 10.951 Auswertungen:
 *
 *     gelb 9.695 (88,5 %)   gruen 934 (8,5 %)   rot 322 (2,9 %)
 *
 * Ein Merkmal, das bei neun von zehn denselben Wert traegt, sortiert nichts und filtert
 * nichts. Dieselbe Falle sitzt im bestehenden Filter „Nur mit Link zu den
 * Vergabeunterlagen": 97,3 % der Leads haben so einen Link. Was TRENNT, ist die Dichte
 * (`pruef` streut 0 bis 186, Median 57) und ueberhaupt die Existenz einer Auswertung:
 * die haben 9,4 % der Leads.
 */
export type DocAnalyse = {
  /** "gruen" | "gelb" | "rot" — schwaches Merkmal, siehe Kopf. */
  ampel: string | null;
  /** Pruefpunkte aus der Checkliste. Das trennschaerfste Mass der Informationsdichte. */
  pruef: number;
  /** K.-o.-Kriterien. */
  ko: number;
  /** Ausgewertete Einzeldokumente. */
  dok: number;
};

const SCHLUESSEL = "idx:doc-analyse";

/**
 * Index aller ausgewerteten Vorgaenge — samt der Auskunft, ob gelesen werden konnte.
 *
 * ⚠ Der Unterschied zwischen „es gibt keine Auswertungen" und „der Datenspeicher
 * antwortet nicht" ist fuer die Liste entscheidend: im ersten Fall ist eine Liste ohne
 * Marken richtig, im zweiten ist sie eine Luege. `leadIndex.ts` beschreibt denselben
 * Fehler zweimal im Dateikopf, weil er zweimal passiert ist. Hier steht er von Anfang an.
 */
export async function analyseIndexMitGrund(): Promise<{
  index: Map<string, DocAnalyse>; stoerung: boolean;
}> {
  const zwischen = ausSpeicher<Map<string, DocAnalyse>>(SCHLUESSEL);
  if (zwischen) return { index: zwischen, stoerung: false };

  const { text: roh, grund } = await ladeMitGrund("doc-analysis-index.json");
  const stoerung = grund === DATEN_STOERUNG;
  if (!roh) return { index: new Map(), stoerung };

  let obj: Record<string, unknown>;
  try { obj = JSON.parse(roh); } catch { return { index: new Map(), stoerung }; }
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return { index: new Map(), stoerung };

  const idx = new Map<string, DocAnalyse>();
  for (const [kennung, wert] of Object.entries(obj)) {
    if (!wert || typeof wert !== "object") continue;
    const w = wert as Record<string, unknown>;
    idx.set(String(kennung), {
      ampel: typeof w.ampel === "string" ? w.ampel : null,
      // ⚠ UEBERGANG. Bis zum 2026-09-17 schrieb der Export NUR `ampel`. Ein Index von
      // vorher traegt die Zaehlungen nicht — dann ist 0 der ehrliche Wert, und die
      // Sortierung nach Dichte faellt in sich zusammen statt falsche Reihen zu bauen.
      // Sobald `export_doc_analysis.py` einmal gelaufen ist, sind die Zahlen da.
      pruef: typeof w.pruef === "number" ? w.pruef : 0,
      ko:    typeof w.ko    === "number" ? w.ko    : 0,
      dok:   typeof w.dok   === "number" ? w.dok   : 0,
    });
  }
  // Gewicht grob: Kennung + vier Felder + Map-Overhead. Es geht um die
  // Verdraengungsreihenfolge im gemeinsamen Budget, nicht um Buchhaltung.
  inSpeicher(SCHLUESSEL, idx, idx.size * 80);
  return { index: idx, stoerung };
}

/** Der knappe Weg — fuer Aufrufer, denen der Grund gleich ist. */
export async function analyseIndex(): Promise<Map<string, DocAnalyse>> {
  return (await analyseIndexMitGrund()).index;
}

/**
 * Traegt der Index ueberhaupt Dichtezahlen?
 *
 * Braucht die Oberflaeche, um zwischen „nach Dichte sortieren" und „das kann ich noch
 * nicht" zu unterscheiden. Ohne diese Frage sortierte ein Uebergangs-Index alles auf 0
 * und die Reihenfolge waere zufaellig — was wie ein kaputter Sortierknopf aussaehe.
 */
export function hatDichte(idx: Map<string, DocAnalyse>): boolean {
  for (const v of idx.values()) if (v.pruef > 0) return true;
  return false;
}
