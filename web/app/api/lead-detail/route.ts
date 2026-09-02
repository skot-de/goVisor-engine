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

/* Fingerabdruck der Vergabestelle (Kennzahl 3): was verlangt DIESE Stelle fast immer, das
 * andere selten verlangen? Wer das vor dem Oeffnen der Unterlagen weiss, legt die Nachweise
 * bereit, statt sie nachzureichen.
 *
 * ⚠ Der Schluessel ist der KAEUFERNAME, klein und getrimmt. `lead_export` traegt keine
 * Entitaets-Kennung, und einen Join gegen Gold gibt es im Frontend nicht. Folge: zwei
 * Schreibweisen derselben Stelle zaehlen getrennt — der Fingerabdruck wird dadurch
 * schwaecher, nie falsch. */
type Stellenprofil = { markt: Record<string, number>;
                       stellen: Record<string, { typ: string; label: string; k: number; n: number; markt: number }[]> };
let stellenprofil: Stellenprofil | null = null;
async function loadStellenprofil(): Promise<Stellenprofil> {
  if (stellenprofil) return stellenprofil;
  try { const roh = await loadDataFile("stellenprofil.json"); stellenprofil = roh ? JSON.parse(roh) : { markt: {}, stellen: {} }; }
  catch { stellenprofil = { markt: {}, stellen: {} }; }
  return stellenprofil!;
}

/* Aenderungen an den Vergabeunterlagen. Die Stelle stellt eine neue Fassung ein; wer auf der
 * alten kalkuliert hat, rechnet falsch und erfaehrt es nicht — das Portal zeigt nur die neueste.
 *
 * ⚠ NICHT die „Anforderungs-Drift" aus der Uebergabe. Die meint zwei Runden derselben Stelle
 * und ist strukturell nicht rechenbar: `contract_succession` und `doc_checklist` sind disjunkt
 * (0 Paare), weil Unterlagen nur waehrend laufender Frist existieren. Hier geht es um die Drift
 * INNERHALB des Verfahrens — frueher da und naeher an der Entscheidung.
 *
 * ⚠ VERGLICHEN WIRD DER LETZTE SCHRITT, nicht Fassung 1 gegen die neueste: wer die Unterlagen
 * gestern gezogen hat, will wissen, was seitdem passiert ist.
 *
 * ⚠ Dateinamen stammen aus fremden Unterlagen. Wer sie rendert, escaped sie. */
type Unterlagenstand = { version: number; vorige: number; nVersionen: number;
                         geaendert: string[]; nGeaendert: number;
                         neu: string[]; nNeu: number; nWeg: number };
let unterlagenstand: Record<string, Unterlagenstand> | null = null;
async function loadUnterlagenstand(): Promise<Record<string, Unterlagenstand>> {
  if (unterlagenstand) return unterlagenstand;
  try { const roh = await loadDataFile("unterlagenstand.json"); unterlagenstand = roh ? JSON.parse(roh) : {}; }
  catch { unterlagenstand = {}; }
  return unterlagenstand!;
}

/* Bieterfragen und Antworten. Waehrend der Angebotsfrist fragen Bewerber die Vergabestelle,
 * und die Antworten muessen ALLEN Bietern zugaenglich sein (§ 20 Abs. 3 EU-VgV). Wer sie nicht
 * liest, rechnet auf einem ueberholten Stand.
 *
 * ⚠ DIE UEBERGABE SAGT, ES GEBE SIE NICHT — und beruft sich auf eine Machbarkeitsstudie, die
 * die eForms-ATTRIBUTE der Bekanntmachungen durchsucht hat. Dort stimmt das. Die Q&A stecken
 * in den UNTERLAGEN („Bieterinformation", „Bieterfragenkatalog"): 257 Vorgaenge, 172 mit
 * lesbarem Text. Wer eine Studie zitiert, prueft, welche Quelle sie untersucht hat.
 *
 * ⚠ ES SIND ABSCHNITTE, KEINE FRAGE-ANTWORT-PAARE. Die Marke („Frage 3:", „Zu Frage 3:")
 * trennt, sagt aber nicht, ob das Folgende Frage oder Antwort ist — nur 35 % enthalten ein
 * Fragezeichen. Die Anzeige behauptet deshalb keine Ordnung, die die Daten nicht hergeben.
 *
 * ⚠ `text` und `datei` stammen aus fremden Unterlagen. Wer sie rendert, escaped sie. */
type Bieterfragen = { n: number; dateien: string[]; nDateien: number;
                      auszug: { text: string; datei: string }[] };
let bieterfragen: Record<string, Bieterfragen> | null = null;
async function loadBieterfragen(): Promise<Record<string, Bieterfragen>> {
  if (bieterfragen) return bieterfragen;
  try { const roh = await loadDataFile("bieterfragen.json"); bieterfragen = roh ? JSON.parse(roh) : {}; }
  catch { bieterfragen = {}; }
  return bieterfragen!;
}

/* Widerspruch bei der Angebotsfrist (Kennzahl 9). Die Bekanntmachung sagt „02.09.", die
 * Unterlagen sagen „Ablauf der Angebotsfrist: 01.09., 18:00 Uhr". Wer der Bekanntmachung
 * folgt, kommt einen Tag zu spaet.
 *
 * ⚠ EIN FEHLALARM IST HIER TEURER ALS EIN VERPASSTER BEFUND. Gemeldet wird nur, was den Beleg
 * eindeutig als Angebotsfrist ausweist UND hoechstens 30 Tage abweicht — darueber stehen
 * Lieferfristen, Seitenkoepfe und Jahresdreher (s. `export_fristwiderspruch.py`).
 *
 * ⚠ SIE SAGT NIE „DIE FRIST STIMMT". Beide Seiten liegen nur bei 1.958 von 14.994 Vorgaengen
 * vor. Anwesenheit, kein Freispruch — deshalb Bezug `keine`. */
type Fristwiderspruch = { dok: string; bek: string; tage: number; beleg: string; datei: string };
let fristwiderspruch: Record<string, Fristwiderspruch> | null = null;
async function loadFristwiderspruch(): Promise<Record<string, Fristwiderspruch>> {
  if (fristwiderspruch) return fristwiderspruch;
  try { const roh = await loadDataFile("fristwiderspruch.json"); fristwiderspruch = roh ? JSON.parse(roh) : {}; }
  catch { fristwiderspruch = {}; }
  return fristwiderspruch!;
}

/* Standardtext-Anteil (Kennzahl 8): wie viel dieser Unterlagen steht wortgleich auch in
 * anderen Vergaben? „1.152 Tsd. Zeichen" ueber dem Volltext sagt nicht, ob das 1.152 Tsd.
 * Zeichen Arbeit sind.
 *
 * ⚠ Gemessen je ABSATZ (ab 120 Zeichen, wortgleich in mindestens drei Vorgaengen), nicht je
 * Datei: ganze Dateien sind nur in 2,1 % der Faelle identisch, ein geaendertes Datum im Kopf
 * genuegt. `document_duplicates` beantwortet also eine andere Frage.
 *
 * ⚠ DER VERGLEICH IST SCHON AUFGELOEST. Das Band haengt an der GEMESSENEN Zeichenzahl; hier
 * ist nur `lbChars` bekannt, und das ist die ausgelieferte Laenge. Wer neu einordnete, traefe
 * ein anderes Band (der Anteil sinkt von 41 % auf 10 %, wenn das Paket waechst). */
type Standardtext = { a: number; median: number; hoch: number };
let standardtext: Record<string, Standardtext> | null = null;
async function loadStandardtext(): Promise<Record<string, Standardtext>> {
  if (standardtext) return standardtext;
  try { const roh = await loadDataFile("standardtext.json"); standardtext = roh ? (JSON.parse(roh).leads || {}) : {}; }
  catch { standardtext = {}; }
  return standardtext!;
}

/* Bezifferte Schwellen im Vergleich (Kennzahl 6). „Berufshaftpflicht 5 Mio. EUR fuer
 * Personenschaeden" steht seit jeher in der Checkliste; der Vergleich fehlte.
 *
 * ⚠ EINE WINZIGE DATEI OHNE VORGANGSBEZUG: nur Gruppenwerte, dazu die REGELN, mit denen der
 * Renderer denselben Gruppenschluessel bildet. Zwei gepflegte Einheitenlisten (hier und dort)
 * waeren zwei Listen, die auseinanderlaufen — dieselbe Fehlerform wie die handgetippte
 * Spaltenliste bei den Doc-Signalen.
 *
 * ⚠ VON 223.570 ZAHLEN SIND RUND 2.500 VERGLEICHBAR. Ohne Einheit kein Vergleich (bei
 * `technische_mindestanforderung` fehlt sie in 66 % der Faelle), die Gruppe muss EINE Groesse
 * benennen („mindestens 20 %" — wovon?), und sie muss die Driftpruefung bestehen: der
 * Mindestumsatz faellt mit 2,5× durch, weil sein Median mit unserer Lesetiefe waechst und NICHT
 * mit dem Auftragswert (Korrelation 0,24). Details in `scripts/export_schwellen.py`. */
type Schwellen = {
  gruppen: Record<string, { n: number; median: number; hoch: number; label: string }>;
  einheiten: Record<string, string[]>;
  auspraegungen: Record<string, {
    dimension: string; einheitOptional: boolean; sonst: string | null;
    regeln: { name: string; muster: string; sperre: string | null; band: [number, number] | null }[];
  }>;
};
let schwellen: Schwellen | null = null;
async function loadSchwellen(): Promise<Schwellen | null> {
  if (schwellen) return schwellen;
  try { const roh = await loadDataFile("schwellen.json"); schwellen = roh ? JSON.parse(roh) : null; }
  catch { schwellen = null; }
  return schwellen;
}

/* Umfang der Angebotsarbeit (Kennzahlen 4 und 5): das groesste Formular zum Ausfuellen und
 * das groesste Leistungsverzeichnis zum Bepreisen. Beides verschiebt die Angebotsplanung um
 * Tage und steht nirgends in der Bekanntmachung.
 *
 * ⚠ SIE MESSEN NICHT DASSELBE, obwohl ein VHB 223 ein Feld je LV-Position hat: Korrelation
 * -0,02, und von 803 Vorgaengen mit grossem LV haben nur 79 auch ein grosses Formular. Zwei
 * Zeilen in einem Block, nicht eine Zahl.
 *
 * ⚠ NUR DAS LV TRAEGT EINEN VERGLEICH, und das ist gemessen, nicht gesetzt. Das groesste LV
 * je Vorgang ist ueber die Lesetiefe stabil (69 → 96 → 78); die Formularsumme waechst monoton
 * mit (2 → 7 → 16). Ein Marktwert aus derselben Untererfassung liesse jeden tief gelesenen
 * Vorgang extremer aussehen als er ist.
 *
 * ⚠ UND DER LV-VERGLEICH GILT JE GEWERK (CPV 4-stellig). Innerhalb von CPV 45 spreizen die
 * Mediane 5,4-fach: Installation 292 Positionen, Anstrich 54. `median`/`hoch` fehlen, wenn das
 * Gewerk unter 40 Vorgaenge hat — dann steht die Zahl ohne Vergleich, nicht mit einem falschen.
 *
 * ⚠ `datei` und `beleg` stammen aus fremden Vergabeunterlagen. Wer sie rendert, escaped sie
 * selbst (s. `explorerCore.js`, die kv-Zeile escaped nicht mehr fuer den Aufrufer). */
type Umfang = {
  formular?: { felder: number; datei: string; hinweis: boolean; beleg?: string };
  lv?: { pos: number; datei: string; hinweis: boolean; gewerk?: string; median?: number; hoch?: number };
};
let umfang: Record<string, Umfang> | null = null;
async function loadUmfang(): Promise<Record<string, Umfang>> {
  if (umfang) return umfang;
  try { const roh = await loadDataFile("umfang.json"); umfang = roh ? JSON.parse(roh) : {}; }
  catch { umfang = {}; }
  return umfang!;
}

/* Anforderungsprofil (Kennzahl 2): je Bereich die Anzahl, dazu Median und oberstes Zehntel.
 *
 * ⚠ Jeder Bereich traegt seine ART mit (`huerde` / `aufwand` / `umfang`). Die Uebergabe nennt
 * die Kennzahl „Strenge", und fuer die Haelfte der Bereiche stimmt das nicht: `formalitaet`
 * sind ausfuellbare Formulare, `leistung` ist Umfang. Nur `eignung` und `ausschluss` sind
 * Huerden. Das Wort in der Anzeige haengt an der Art, nicht an der Zahl. */
type Profil = { bereiche: Record<string, { n: number; median: number; hoch: number; art: string }>;
                leads: Record<string, Record<string, number>> };
let profil: Profil | null = null;
async function loadProfil(): Promise<Profil> {
  if (profil) return profil;
  try { const roh = await loadDataFile("anforderungsprofil.json"); profil = roh ? JSON.parse(roh) : { bereiche: {}, leads: {} }; }
  catch { profil = { bereiche: {}, leads: {} }; }
  return profil!;
}

/* Zeitfenster gegen Aufwand (Kennzahl 1). Eine kleine Datei: je Vorgang die Tage zwischen
 * Bekanntmachung und Frist, dazu Median und Viertel je Land.
 *
 * ⚠ Warum sie ueberhaupt getrennt liegt: das Veroeffentlichungsdatum steht in SILBER, nicht
 * in `lead_export`. Der grosse Lead-Export haette dafuer einen Join gebraucht, den es dort
 * nicht gibt (s. `scripts/export_fenster.py`). */
type FensterLage = { n: number; median: number; unten: number; oben: number; eng: number };
type Fenster = { rahmen: Record<string, FensterLage>;
                 leads: Record<string, { tage: number; rahmen: string; land: string }> };
let fenster: Fenster | null = null;
async function loadFenster(): Promise<Fenster> {
  if (fenster) return fenster;
  try { const roh = await loadDataFile("fenster.json"); fenster = roh ? JSON.parse(roh) : { rahmen: {}, leads: {} }; }
  catch { fenster = { rahmen: {}, leads: {} }; }
  return fenster!;
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
    /* ⚠ NUR WENN BEIDE SEITEN DA SIND. Das Fenster allein sagt nichts („34 Tage" ist eine
       Frist), die Anforderungszahl allein auch nicht. Erst zusammen entsteht die Aussage,
       und genau deshalb kann sie sonst niemand rechnen. */
    /* ⚠ VERGLICHEN WIRD JE REGELWERK, nicht global. Die Frist ist gesetzlich geregelt und
       streut deshalb kaum; unterschwellig (UVgO) gelten andere Mindestfristen. Ein globaler
       Median markierte jede UVgO-Vergabe als „knapp", obwohl sie ihrem eigenen Rahmen
       entspricht: unter den Vorgaengen mit hoechstens 28 Tagen sind 21 % UVgO, im Rest 4 %. */
    const fw = await loadFenster();
    const eintrag = fw.leads[id];
    const lage = eintrag ? fw.rahmen[`${eintrag.land}:${eintrag.rahmen}`] : undefined;
    if (eintrag && lage && an) detail.lbFenster = { tage: eintrag.tage, rahmen: eintrag.rahmen, ...lage };
    /* Anforderungsprofil: nur die Bereiche, in denen dieser Vorgang im obersten Zehntel
       liegt. ⚠ Hoechstens zwei, nach Abstand zum Median sortiert — sieben Zeilen „mehr als
       ueblich" waeren keine Aussage mehr, sondern eine Tabelle. */
    const pf = await loadProfil();
    const zahlen = pf.leads[id];
    if (zahlen && an) {
      const land = String((detail as { land?: string }).land || "DE");
      const auffaellig = Object.entries(zahlen)
        .map(([bereich, k]) => ({ bereich, k, lage: pf.bereiche[`${land}:${bereich}`] }))
        .filter((x) => x.lage && x.k >= x.lage.hoch)
        /* ⚠ ART VOR VERHAELTNIS. Zuerst sortierte ich nur nach dem Vielfachen des Medians —
           dann stand „Zuschlagskriterien 21 statt 3" (Umfang, 7-fach) VOR
           „Ausschlusskriterien 17 statt 5" (Huerde, 3,4-fach). Eine Huerde kann die
           Bewerbung kosten, ein langer Text nicht. Bei nur zwei Plaetzen entscheidet die
           Reihenfolge darueber, was der Nutzer ueberhaupt zu sehen bekommt. */
        .sort((a, b) => {
          const rang = (art: string) => (art === "huerde" ? 0 : art === "aufwand" ? 1 : 2);
          const d = rang(a.lage!.art) - rang(b.lage!.art);
          return d !== 0 ? d : (b.k / b.lage!.median) - (a.k / a.lage!.median);
        })
        .slice(0, 2)
        .map((x) => ({ bereich: x.bereich, k: x.k, median: x.lage!.median, art: x.lage!.art }));
      if (auffaellig.length) detail.lbProfil = auffaellig;
    }

    /* ⚠ Nur was die Stelle DEUTLICH oefter verlangt als der Markt. Ein Fingerabdruck, der
       die Marktrate nur trifft, ist keiner — dann ist es Verfahrensroutine. */
    const sp = await loadStellenprofil();
    const kaeufer = String((detail as { buyer?: string }).buyer || "").trim().toLowerCase().slice(0, 120);
    const land2 = String((detail as { land?: string }).land || "DE");
    const abdruck = kaeufer ? sp.stellen[`${land2}:${kaeufer}`] : undefined;
    if (abdruck?.length) detail.lbStelle = abdruck.slice(0, 3);
    const uf = (await loadUmfang())[id];
    if (uf) detail.lbUmfang = uf;
    const sw = await loadSchwellen();
    if (sw) detail.lbSchwellen = sw;
    const stt = (await loadStandardtext())[id];
    if (stt) detail.lbStandard = stt;
    const fw2 = (await loadFristwiderspruch())[id];
    if (fw2) detail.lbFristWiderspruch = fw2;
    const bf = (await loadBieterfragen())[id];
    if (bf) detail.lbFragen = bf;
    const us = (await loadUnterlagenstand())[id];
    if (us) detail.lbStand = us;
    // Dateiliste des Portals — was dort LIEGT, ohne dass wir es gelesen haben.
    const li = await ladeDateiliste(id);
    if (li) detail.lbListe = li;
    return NextResponse.json(detail);
  } catch {
    return NextResponse.json({ error: "keine Detaildaten" }, { status: 503 });
  }
}
