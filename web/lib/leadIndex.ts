import "server-only";
import { ausSpeicher, inSpeicher, loadDataFile } from "@/lib/dataSource";
import type { LeadTiming } from "@/lib/alerts";

/* Fristen aller Leads, nach ID. Grundlage für Hinweise (Posteingang und E-Mail-Lauf).
 *
 * ⚠ Liest über `loadDataFile`, NICHT direkt von der Platte. Der Alert-Lauf tat Letzteres
 * (`readdir(process.cwd()/data)`) — auf einem Deployment mit `DATA_BASE_URL` liegt dort
 * nichts, der Lauf hätte also still null Hinweise gefunden und wäre grün gemeldet.
 * Die Branchenliste steht deshalb hier fest statt aus einem Verzeichnis zu kommen: über
 * HTTP gibt es kein `readdir`. */
const BRANCHEN = ["it", "bau", "medizin", "beratung", "sicherheit", "energie", "ohne"];

export async function leadFristen(): Promise<Map<string, LeadTiming>> {
  const schlank = await ausSchlankerDatei();
  if (schlank) return schlank;
  return ausAllenBranchen();
}

/* Der schnelle Weg: EINE Datei mit genau den sechs Feldern, die hier gebraucht werden.
 *
 * ⚠ Gemessen am 2026-08-25: der alte Weg las alle sieben `leads-<branche>.json`
 * nacheinander — 110 MB fuer 43.735 Leads, von denen sechs Felder benutzt werden. Dieselben
 * Felder als eine Datei sind 7,2 MB, also 6,5 %. Der Rest ist Beschreibung, Lose,
 * Anforderungen, Unterlagen — Dinge, die eine Fristenliste nichts angehen. */
async function ausSchlankerDatei(): Promise<Map<string, LeadTiming> | null> {
  const roh = await loadDataFile("leads-fristen.json");
  if (!roh) return null;
  try {
    const arr = JSON.parse(roh) as LeadTiming[];
    if (!Array.isArray(arr)) return null;
    const idx = new Map<string, LeadTiming>();
    for (const l of arr) idx.set(String(l.id), l);
    return idx;
  } catch {
    return null;
  }
}

/* ⚠ UEBERGANG, kein Dauerzustand. Solange `leads-fristen.json` nicht im Datenspeicher
 * liegt (erster Lauf nach dem Umbau), muss der Alert-Lauf trotzdem funktionieren. Das
 * kostet dann aber wieder 110 MB — deshalb LAUT: eine Zeile im Protokoll ist der
 * Unterschied zwischen „Uebergang laeuft" und „wir haben nichts gewonnen und niemand hat
 * es gemerkt". */
let gewarnt = false;
async function ausAllenBranchen(): Promise<Map<string, LeadTiming>> {
  if (!gewarnt) {
    console.error("[fristen] Rückfall auf sieben leads-<branche>.json (110 MB) — "
                  + "leads-fristen.json fehlt. export_web_leads.py laufen lassen und hochladen.");
    gewarnt = true;
  }
  const idx = new Map<string, LeadTiming>();
  for (const b of BRANCHEN) {
    const roh = await loadDataFile(`leads-${b}.json`);
    if (!roh) continue;
    let arr: Record<string, unknown>[];
    try { arr = JSON.parse(roh); } catch { continue; }
    if (!Array.isArray(arr)) continue;
    for (const l of arr) {
      const timing = l.timing as { src?: string } | undefined;
      idx.set(String(l.id), {
        id: String(l.id), titel: l.titel as string | undefined, src: l.src as string | undefined,
        tage: l.tage as number | null | undefined,
        endTage: l.endTage as number | null | undefined,
        endeEcht: timing?.src === "echt",
      });
    }
  }
  return idx;
}

/* ── Welcher Grundraum trägt diese Kennung? ───────────────────────────────────────────
 *
 * WOFÜR. Der Vergabe-Verlauf einer Vergabestelle zeigt Zuschläge über ALLE Branchen
 * (`buyer_recent_awards`), die geladene Liste trägt aber immer nur EINEN Grundraum. Ein
 * Klick auf eine Zeile aus einem anderen Grundraum lief bis zum 2026-09-02 in einen
 * `TypeError`, danach in eine Meldung „wechselt oben den Grundraum". Damit die Anwendung
 * das selbst tut, muss sie wissen, WOHIN — und das weiß nur der Server.
 *
 * ⚠ WARUM EIN INDEX UND KEINE SUCHE JE ANFRAGE. Die Alternative wäre, die Branchendateien
 * der Reihe nach zu lesen, bis die Kennung auftaucht: im Mittel dreieinhalb Dateien, also
 * Dutzende MB pro Klick. Der Index ist eine Map über alle Kennungen und liegt im gemeinsamen
 * Zwischenspeicher (Byte-Budget + Verfallszeit wie die Datendateien, s. `lib/dataCache.js`)
 * — gebaut wird er höchstens einmal je Verfallsfenster. */
const IDX_SCHLUESSEL = "idx:lead-branche";

export async function leadBranchen(): Promise<Map<string, string>> {
  const zwischen = ausSpeicher<Map<string, string>>(IDX_SCHLUESSEL);
  if (zwischen) return zwischen;
  const idx = (await brancheAusSchlankerDatei()) ?? (await brancheAusAllenBranchen());
  // Gewicht fürs Budget grob geschätzt: Kennung + Branchenname + Map-Overhead je Eintrag.
  // Genauer zu messen lohnt nicht — es geht um die Verdrängungsreihenfolge, nicht um Buchhaltung.
  return inSpeicher(IDX_SCHLUESSEL, idx, idx.size * 96);
}

/** Der schnelle Weg: dieselbe schlanke Datei wie die Fristen, die seit dem 2026-09-02 auch
 *  den Grundraum je Kennung trägt (`scripts/export_web_leads.py::_frist_zeile`). */
async function brancheAusSchlankerDatei(): Promise<Map<string, string> | null> {
  const roh = await loadDataFile("leads-fristen.json");
  if (!roh) return null;
  try {
    const arr = JSON.parse(roh) as { id?: unknown; branche?: unknown }[];
    if (!Array.isArray(arr) || !arr.length) return null;
    // ⚠ Ein Export von VOR dieser Änderung hat das Feld nicht. Dann ist die Datei nicht etwa
    // leer, sondern liefert lauter `undefined` — ein Index, der zu JEDER Kennung „kein
    // Grundraum" sagt, sähe aus wie „die Ausschreibung gibt es nicht". Das wäre schlimmer
    // als kein Index, weil es wie eine Antwort aussieht.
    if (typeof arr[0]?.branche !== "string") return null;
    const idx = new Map<string, string>();
    for (const l of arr) if (typeof l.branche === "string") idx.set(String(l.id), l.branche);
    return idx;
  } catch {
    return null;
  }
}

/* ⚠ UEBERGANG, kein Dauerzustand — genau wie bei den Fristen oben. Solange der Export ohne
 * `branche` gelaufen ist, muss das Nachladen trotzdem funktionieren; es kostet dann aber die
 * 110 MB, die diese Datei gerade abschaffen sollte. Deshalb LAUT. */
let brancheGewarnt = false;
async function brancheAusAllenBranchen(): Promise<Map<string, string>> {
  if (!brancheGewarnt) {
    console.error("[lead-branche] Rückfall auf sieben leads-<branche>.json (110 MB) — "
                  + "leads-fristen.json trägt kein `branche`. export_web_leads.py laufen "
                  + "lassen und hochladen.");
    brancheGewarnt = true;
  }
  const idx = new Map<string, string>();
  for (const b of BRANCHEN) {
    const roh = await loadDataFile(`leads-${b}.json`);
    if (!roh) continue;
    let arr: { id?: unknown }[];
    try { arr = JSON.parse(roh); } catch { continue; }
    if (!Array.isArray(arr)) continue;
    // Erster Treffer gewinnt: eine Kennung kann in mehreren Grundräumen liegen (Mehr-CPV),
    // und die Reihenfolge hier ist dieselbe wie im Export — sonst wechselte die Antwort
    // zwischen zwei Aufrufen, ohne dass sich an den Daten etwas geändert hätte.
    for (const l of arr) if (!idx.has(String(l.id))) idx.set(String(l.id), b);
  }
  return idx;
}
