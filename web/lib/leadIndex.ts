import "server-only";
import { loadDataFile } from "@/lib/dataSource";
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
