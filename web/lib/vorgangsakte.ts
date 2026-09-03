import { createHash } from "crypto";
import { loadDataFile, ausSpeicher, inSpeicher } from "@/lib/dataSource";

/* Vorgangsakten (scripts/export_vorgaenge.py) — Ausschreibung, Korrekturen, Unterlagen und
 * Zuschlag unter EINER Nummer.
 *
 * Dieselbe Form wie `firma/` und `doc-analysis/`: eine Akte je Datei, Hash als Name. Der
 * Grund ist derselbe, aus dem `firma-profiles.json` am 2026-08-25 aufgeteilt wurde — eine
 * Sammeldatei laedt bei jedem Kaltstart alles, um genau einen Eintrag zu liefern.
 *
 * ⚠ NICHT ALLE VORGAENGE. Gold fuehrt 1,47 Mio.; hier liegen die rund 36.000, die eine
 * heute sichtbare Vergabe enthalten, samt aller Glieder ihrer Ketten. Alles andere
 * beantwortet diese Datei mit `null` — was nicht heisst, dass es den Vorgang nicht gibt,
 * sondern dass er nicht exportiert ist. Die Route muss den Unterschied benennen. */

export type Verlaufseintrag = {
  datum: string | null;
  art: string;
  label: string;
  n: number;
  ids: string[];
  unterlagen: boolean;
};

export type Akte = {
  id: string;
  land: string;
  titel: string | null;
  cpv: string | null;
  schluessel: string;
  vollstaendig: boolean;
  von: string | null;
  bis: string | null;
  zahlen: Record<string, number>;
  verlauf: Verlaufseintrag[];
  dokumente: Array<{
    notice: string; quelle: string | null; url: string | null; gelesen: boolean;
    n: number; dateien: Array<{ name: string; typ: string }>; gekuerzt: number;
  }>;
  kette?: {
    kette: string; position: number; n_glieder: number; min_konfidenz: number | null;
    methode: string; dauerangebot: boolean; gekuerzt: number;
    glieder: Array<{ vorgang: string; position: number; jahr: number | null;
                     konfidenz: number | null; titel: string | null }>;
  };
};

/** Land + Vorgangsnummer → Dateiname. MUSS mit `export_vorgaenge.dateiname` übereinstimmen;
 *  `tests/test_vorgangsakte.py` prüft beide Seiten gegeneinander.
 *
 *  ⚠ Hash statt der sonst üblichen Säuberung `[^A-Za-z0-9_-]` → "": die Nummern sehen
 *  `folder:BA090-26` und `pub:123456-2015` aus, und gesäubert wären `folder:ab-1` und
 *  `folder:ab1` dieselbe Datei. Ein Hash kann in Python und Node nicht auseinanderlaufen.
 *
 *  ⚠ DAS LAND GEHOERT IN DEN SCHLUESSEL. Die Nummer allein ist nicht weltweit eindeutig:
 *  48 Nummern kommen in mehr als einem Land vor (AT∩DE 31, CH∩DE 9, DE∩PL 4). Ohne das
 *  Land überschriebe die österreichische Akte die deutsche, und zwar lautlos. */
export function vorgangDateiname(land: string, id: string): string {
  return createHash("sha1").update(`${land}:${id}`, "utf8").digest("hex");
}

/** Wie viele Zeichen des Hashes den Bündelnamen bilden: 3 → 4.096 Bündel.
 *  MUSS mit `export_vorgaenge.BUENDEL_STELLEN` übereinstimmen. */
const BUENDEL_STELLEN = 3;

/** Eine Akte. `null`, wenn sie nicht exportiert ist.
 *
 * ⚠ 256 BUENDEL, NICHT 53.872 EINZELDATEIEN — und auch keine Sammeldatei. Beide Extreme
 * sind hier schon einmal schiefgegangen: `firma-profiles.json` lud 67 MB, um 1,6 KB zu
 * liefern, und die Einzeldateien liessen `next build` im Node-Heap sterben, weil Next den
 * Projektbaum abgeht (156.000 Dateien unter `web/data`). Ein Bündel ist im Median 21 KB
 * gross; es liegt danach im Speicher und bedient jede weitere Akte daraus umsonst. */
export async function loadVorgang(land: string, id: string): Promise<Akte | null> {
  if (!id || !land) return null;
  const h = vorgangDateiname(land, id);
  const name = h.slice(0, BUENDEL_STELLEN);
  let buendel = ausSpeicher<Record<string, Akte>>(`vorgang-buendel:${name}`);
  if (!buendel) {
    try {
      const roh = await loadDataFile(`vorgang/${name}.json`);
      if (!roh) return null;
      buendel = inSpeicher(`vorgang-buendel:${name}`,
                           JSON.parse(roh) as Record<string, Akte>, roh.length);
    } catch {
      return null;
    }
  }
  return buendel[h] ?? null;
}

/** Bekanntmachung → Vorgangsnummer, damit die Detailansicht einer Vergabe ihre Akte findet.
 *
 * ⚠ BLEIBT SERVERSEITIG. Das Nachschlagewerk ist 3,6 MB. Es liegt im Speicher der Instanz
 * und geht NIE an den Browser. Ins Lead-Json gehoert es auch nicht: dann traegt jeder der
 * 42.678 Leads ein Feld, das fast niemand anfasst — und `export_web_leads.py` haette eine
 * zweite Quelle fuer dieselbe Zuordnung. */
export async function vorgangZuLead(
  leadId: string,
): Promise<{ land: string; id: string } | null> {
  if (!leadId) return null;
  let karte = ausSpeicher<Record<string, string>>("vorgang-lead:geparst");
  if (!karte) {
    const roh = await loadDataFile("vorgang-lead.json");
    if (!roh) return null;
    karte = inSpeicher("vorgang-lead:geparst",
                       JSON.parse(roh) as Record<string, string>, roh.length);
  }
  const eintrag = karte[leadId];
  if (!eintrag) return null;
  // Form `LAND:<nummer>` — die Nummer enthaelt selbst Doppelpunkte (`folder:…`), deshalb
  // NUR am ersten trennen.
  const schnitt = eintrag.indexOf(":");
  if (schnitt < 1) return null;
  return { land: eintrag.slice(0, schnitt), id: eintrag.slice(schnitt + 1) };
}

/** Wie viele Akten der Datenspeicher führt — `null`, wenn er sie gar nicht hat.
 *
 * Trennt „diesen Vorgang gibt es nicht" (404) von „die Akten fehlen" (503). Dieselbe
 * Unterscheidung, die `firma-stand.json` nach einem echten Vorfall bekommen hat: ohne sie
 * sieht ein fehlender Datenspeicher aus wie ein leeres Ergebnis. */
export async function vorgangBestand(): Promise<number | null> {
  const gepuffert = ausSpeicher<number | null>("vorgang:bestand");
  if (gepuffert !== undefined) return gepuffert;
  try {
    const roh = await loadDataFile("vorgang-stand.json");
    const n = roh ? ((JSON.parse(roh) as { n?: number }).n ?? null) : null;
    return inSpeicher("vorgang:bestand", n, 100);
  } catch {
    return inSpeicher("vorgang:bestand", null, 100);
  }
}
