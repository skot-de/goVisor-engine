import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";
import { getTier } from "@/lib/tier";
import { redactDetail } from "@/lib/redact";

// Schwere Felder eines Leads (Beschreibung + Vergabestellen-Profil), erst beim Öffnen
// geladen. Hält die Listen-Ladung schlank. Detail-Dateien werden nach Grundraum gecacht.
// `ohne` = Vergaben, deren Quelle keinen CPV-Code führt (NetServer-Trefferlisten, Teile
// von DÖE). Seit die CPV-Pflicht aus dem Lead-Bau raus ist, sind sie im Bestand — ohne
// diesen Eintrag antwortet die Route auf sie mit HTTP 400 und die Leads wären zwar
// exportiert, aber für die App unerreichbar. Ein Grundraum ist erst durchgängig, wenn
// Export, Route UND Anzeige ihn kennen.
const BRANCHEN = new Set(["it", "bau", "medizin", "beratung", "sicherheit", "energie",
                          "ohne"]);
const cache = new Map<string, Record<string, unknown>>();

async function load(branche: string) {
  if (cache.has(branche)) return cache.get(branche)!;
  const raw = await loadDataFile(`detail-${branche}.json`);
  if (!raw) throw new Error("keine Detaildaten");
  const data = JSON.parse(raw) as Record<string, unknown>;
  cache.set(branche, data);
  return data;
}

// Leistungsbeschreibungs-Volltext aus den Vergabeunterlagen (doc-text.json, aus `index-docs` →
// export_doc_text.py), je notice_id. Einmal geladen, modulweit gecacht.
type DocText = { chars: number; files: number; text: string; truncated: boolean };
/** Volltext EINES Vorgangs.
 *
 * ⚠ WARUM NICHT MEHR DIE SAMMELDATEI. `doc-text.json` war am 2026-08-18 auf 294 MB
 * gewachsen (nach dem Formate-Ausbau). Lokal ist das ein Lesevorgang von der Platte, in der
 * Cloud laedt `loadDataFile` sie ueber das Netz und haelt sie im Speicher — je Instanz, bei
 * jedem Kaltstart, um EINEN Vorgang zu beantworten. `scripts/export_doc_text.py` schreibt
 * deshalb zusaetzlich eine Datei je Vorgang, im Schnitt 61 KB.
 *
 * Einen Rueckfall auf die Sammeldatei gibt es bewusst NICHT: sie waere dieselbe Menge ein
 * zweites Mal, jede Nacht neu hochzuladen. Fehlt die Einzeldatei, fehlt der Volltext —
 * sichtbar, statt still aus einem alten Stand bedient zu werden.
 */
async function ladeVolltext(id: string): Promise<DocText | undefined> {
  const sicher = id.replace(/[^A-Za-z0-9_-]/g, "");
  if (sicher) {
    try {
      const roh = await loadDataFile(`doc-text/${sicher}.json`);
      if (roh) return JSON.parse(roh) as DocText;
    } catch { /* Einzeldatei fehlt oder ist kaputt → Sammeldatei versuchen */ }
  }
  return undefined;
}

// Strukturierte Anforderungs-Signale aus den Vergabeunterlagen (doc-signals.json, aus
// signals-docs → export_doc_signals.py), je notice_id.
// ⚠ DIESE LISTE MUSS VOLLSTAENDIG BLEIBEN. Bis zum 2026-09-01 nannte sie sieben Felder,
// waehrend `doc_signals.parquet` fuenfzehn trug — sechs Signale waren gebaut, gemessen,
// gespeichert und wurden nie gezeigt (binding_until 5.747 Saetze, penalty_pct 4.066,
// site_visit 3.723, presentation_required 3.576, skonto_pct 393). Die Spalten stehen jetzt
// in `govisor/kennzahlen.py`; `tests/test_kennzahlen.py` haelt fest, dass dieser Typ genau
// deren Schluessel fuehrt.
type DocSignals = {
  guarantee: boolean | null; bindingDays: number | null; bindingUntil: string | null;
  eligibility: number | null; certificates: string[]; variants: boolean | null;
  framework: boolean | null; weights: Record<string, number> | null;
  siteVisit: boolean | null; siteVisitMandatory: boolean | null;
  presentationRequired: boolean | null;
  penaltyPct: number | null; skontoPct: number | null;
  // Je Signal das Zitat aus dem Dokument. Kein Messwert, sondern der Beleg dafuer, dass die
  // Zeile darueber nicht geraten ist. Kommt als JSON-Text aus dem Parquet.
  evidence: string | null;
};
let docSignals: Record<string, DocSignals> | null = null;
async function loadDocSignals(): Promise<Record<string, DocSignals>> {
  if (docSignals) return docSignals;
  try { const raw = await loadDataFile("doc-signals.json"); docSignals = raw ? JSON.parse(raw) : {}; }
  catch { docSignals = {}; }
  return docSignals!;
}

// Leistungsumfang + Entscheidungskriterien aus den Unterlagen (doc-struktur.json, aus
// extract_positions.py/extract_criteria.py → export_doc_struktur.py). Anders als die Signale
// oben ist das keine Ableitung, sondern die Tabelle selbst: Positionen aus GAEB-LV und
// Preisblättern, Kriterien aus der UfAB-Matrix.
type DocStruktur = {
  nPositionen?: number; quelle?: string;
  mengen?: Record<string, number>;
  positionen?: { rno: string | null; menge: number | null; einheit: string | null; text: string }[];
  kriterien?: { ausschluss: Record<string, unknown>[]; bewertung: Record<string, unknown>[] };
};
let docStruktur: Record<string, DocStruktur> | null = null;
async function loadDocStruktur(): Promise<Record<string, DocStruktur>> {
  if (docStruktur) return docStruktur;
  try { const raw = await loadDataFile("doc-struktur.json"); docStruktur = raw ? JSON.parse(raw) : {}; }
  catch { docStruktur = {}; }
  return docStruktur!;
}

// LLM-Vergabe-Analyse aus den Unterlagen (doc-analysis.json, aus analyze_docs.py): Ampel +
// Bieter-Checkliste (K.o./Eignung/Zuschlag/Fristen/Aufwand/vorausfüllbar), je notice_id.
type DocAnalysis = Record<string, unknown>;
/** Auswertung EINES Vorgangs.
 *
 * ⚠ WARUM NICHT MEHR DIE SAMMELDATEI. `doc-analysis.json` war am 2026-08-22 auf 252 MB
 * gewachsen. Diese Route lud und parste sie VOLLSTAeNDIG, um eine einzige Auswertung
 * herauszugreifen — und hielt sie danach in einer Modulvariable OHNE Verfall fest: eine
 * laufende Instanz haette bis zum naechsten Deployment die Auswertungen von gestern
 * geliefert, ohne dass es jemand sieht. Jetzt eine Datei je Vorgang, im Schnitt 40 KB
 * (`scripts/export_doc_analysis.py`), genau wie der Volltext daneben.
 *
 * Kein Rueckfall auf die Sammeldatei: sie ist der ARBEITSSTAND des Analyse-Arbeiters und
 * wird gar nicht mehr hochgeladen. Fehlt die Einzeldatei, fehlt die Auswertung — sichtbar,
 * statt still aus einem alten Stand bedient zu werden.
 */
async function ladeAnalyse(id: string): Promise<DocAnalysis | undefined> {
  const sicher = id.replace(/[^A-Za-z0-9_-]/g, "");
  if (!sicher) return undefined;
  try {
    const roh = await loadDataFile(`doc-analysis/${sicher}.json`);
    if (roh) return JSON.parse(roh) as DocAnalysis;
  } catch { /* fehlt oder kaputt → keine Auswertung */ }
  return undefined;
}

/** Dateiliste EINES Vorgangs: was das Portal ohne Anmeldung anzeigt.
 *
 * ⚠ DAS IST KEIN VOLLTEXT. subreport (DE) und vergabeportal.at (AT) geben die Dateien nur
 * gegen Anmeldung heraus, die LISTE aber öffentlich. Sie beantwortet zwei Fragen, die sonst
 * offen bleiben: gibt es ein Leistungsverzeichnis, und welche Nachweise werden verlangt.
 * Gemessen am 2026-08-22: 944 heute offene Vergaben haben eine solche Liste und KEINEN
 * Volltext — davon 134 in Österreich, wo es bis dahin überhaupt keine Dokumentsignale gab.
 *
 * Jeder Satz trägt `gelesen: false`. Wer das anzeigt, muss den Unterschied zwischen
 * „gelesen" und „nur gelistet" sichtbar machen — sonst behauptet die Oberfläche Wissen
 * über Dokumente, die niemand geöffnet hat.
 */
async function ladeDateiliste(id: string): Promise<Record<string, unknown> | undefined> {
  const sicher = id.replace(/[^A-Za-z0-9_-]/g, "");
  if (!sicher) return undefined;
  try {
    const roh = await loadDataFile(`doc-listing/${sicher}.json`);
    if (roh) return JSON.parse(roh) as Record<string, unknown>;
  } catch { /* keine Liste → nichts anzeigen */ }
  return undefined;
}

export async function GET(req: Request) {
  const u = new URL(req.url);
  const branche = u.searchParams.get("branche") || "";
  const id = u.searchParams.get("id") || "";
  if (!BRANCHEN.has(branche) || !id) {
    return NextResponse.json({ error: "branche/id fehlt" }, { status: 400 });
  }
  try {
    const all = await load(branche);
    const tier = await getTier();   // Free → Premium-Analytik im Detail redigieren (server-seitig)
    const detail = redactDetail(all[id] ?? {}, tier) as Record<string, unknown>;
    // LB-Volltext aus den Vergabeunterlagen anhängen, falls für diese notice_id vorhanden.
    const dt = await ladeVolltext(id);
    if (dt) {
      detail.lbText = dt.text;
      detail.lbFiles = dt.files;
      detail.lbChars = dt.chars;
      detail.lbTruncated = dt.truncated;
    }
    // Strukturierte Anforderungs-Signale aus den Unterlagen (Bürgschaft, Zertifikate, Zuschlagsgewichte …).
    const ds = (await loadDocSignals())[id];
    if (ds) detail.lbSignals = ds;
    // Leistungsumfang (LV-Positionen) + Entscheidungskriterien (A/B-Matrix) aus den Unterlagen.
    const st = (await loadDocStruktur())[id];
    if (st) detail.lbStruktur = st;
    // LLM-Vergabe-Analyse (Ampel + Bieter-Checkliste).
    const an = await ladeAnalyse(id);
    if (an) detail.lbAnalyse = an;
    // Dateiliste des Portals — was dort LIEGT, ohne dass wir es gelesen haben.
    const li = await ladeDateiliste(id);
    if (li) detail.lbListe = li;
    return NextResponse.json(detail);
  } catch {
    return NextResponse.json({ error: "keine Detaildaten" }, { status: 503 });
  }
}
