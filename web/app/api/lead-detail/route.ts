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
let docText: Record<string, DocText> | null = null;
async function loadDocText(): Promise<Record<string, DocText>> {
  if (docText) return docText;
  try { const raw = await loadDataFile("doc-text.json"); docText = raw ? JSON.parse(raw) : {}; }
  catch { docText = {}; }
  return docText!;
}

// Strukturierte Anforderungs-Signale aus den Vergabeunterlagen (doc-signals.json, aus
// signals-docs → export_doc_signals.py), je notice_id.
type DocSignals = {
  guarantee: boolean | null; bindingDays: number | null; eligibility: number | null;
  certificates: string[]; variants: boolean | null; framework: boolean | null;
  weights: Record<string, number> | null;
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
let docAnalysis: Record<string, DocAnalysis> | null = null;
async function loadDocAnalysis(): Promise<Record<string, DocAnalysis>> {
  if (docAnalysis) return docAnalysis;
  try { const raw = await loadDataFile("doc-analysis.json"); docAnalysis = raw ? JSON.parse(raw) : {}; }
  catch { docAnalysis = {}; }
  return docAnalysis!;
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
    const dt = (await loadDocText())[id];
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
    const an = (await loadDocAnalysis())[id];
    if (an) detail.lbAnalyse = an;
    return NextResponse.json(detail);
  } catch {
    return NextResponse.json({ error: "keine Detaildaten" }, { status: 503 });
  }
}
