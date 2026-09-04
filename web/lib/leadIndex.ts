import "server-only";
import { ladeMitGrund, DATEN_STOERUNG } from "@/lib/dataSource";
import type { LeadTiming } from "@/lib/alerts";

/* Fristen aller Leads, nach ID. Grundlage für Hinweise (Posteingang und E-Mail-Lauf).
 *
 * ⚠ Liest über `loadDataFile`, NICHT direkt von der Platte. Der Alert-Lauf tat Letzteres
 * (`readdir(process.cwd()/data)`) — auf einem Deployment mit `DATA_BASE_URL` liegt dort
 * nichts, der Lauf hätte also still null Hinweise gefunden und wäre grün gemeldet.
 * Die Branchenliste steht deshalb hier fest statt aus einem Verzeichnis zu kommen: über
 * HTTP gibt es kein `readdir`. */
const BRANCHEN = ["it", "bau", "medizin", "beratung", "sicherheit", "energie", "ohne"];

/**
 * Fristen aller Leads — samt der Auskunft, ob ueberhaupt gelesen werden konnte.
 *
 * ⚠ WARUM DAS NOETIG IST, obwohl der Kopf dieser Datei denselben Fehler schon einmal
 * beschreibt. Behoben wurde damals der falsche PFAD (`readdir` statt `loadDataFile`); die
 * FEHLERKLASSE blieb. Ist der Datenspeicher nicht erreichbar, liefern beide Wege eine leere
 * Karte — und `/api/alerts/run` ueberspringt dann jede Beobachtung (`if (!lead) continue`),
 * meldet `{ ok: true }` und verschickt nichts. Der Scheduler sieht 200, und niemand erfaehrt,
 * dass an diesem Tag keine einzige Fristwarnung hinausging.
 *
 * Genau derselbe Satz steht im Kopf der Datei ueber die alte Fassung: „der Lauf haette also
 * still null Hinweise gefunden und waere gruen gemeldet." Nur eben eine Ursache weiter.
 */
export async function leadFristenMitGrund(): Promise<{
  index: Map<string, LeadTiming>; stoerung: boolean;
}> {
  const schlank = await ausSchlankerDatei();
  if (schlank.index) return { index: schlank.index, stoerung: false };
  const breit = await ausAllenBranchen();
  // Die schlanke Datei zaehlt nur mit, wenn ihr Fehlen eine STOERUNG war — dass es sie
  // nicht gibt, ist waehrend des Uebergangs ein erwarteter Zustand.
  return { index: breit.index, stoerung: schlank.stoerung || breit.stoerung };
}

/** Der knappe Weg — unveraendert fuer Aufrufer, denen der Grund gleich ist. */
export async function leadFristen(): Promise<Map<string, LeadTiming>> {
  return (await leadFristenMitGrund()).index;
}

/* Der schnelle Weg: EINE Datei mit genau den sechs Feldern, die hier gebraucht werden.
 *
 * ⚠ Gemessen am 2026-08-25: der alte Weg las alle sieben `leads-<branche>.json`
 * nacheinander — 110 MB fuer 43.735 Leads, von denen sechs Felder benutzt werden. Dieselben
 * Felder als eine Datei sind 7,2 MB, also 6,5 %. Der Rest ist Beschreibung, Lose,
 * Anforderungen, Unterlagen — Dinge, die eine Fristenliste nichts angehen. */
async function ausSchlankerDatei(): Promise<{ index: Map<string, LeadTiming> | null; stoerung: boolean }> {
  const { text: roh, grund } = await ladeMitGrund("leads-fristen.json");
  const stoerung = grund === DATEN_STOERUNG;
  if (!roh) return { index: null, stoerung };
  try {
    const arr = JSON.parse(roh) as LeadTiming[];
    if (!Array.isArray(arr)) return { index: null, stoerung };
    const idx = new Map<string, LeadTiming>();
    for (const l of arr) idx.set(String(l.id), l);
    return { index: idx, stoerung: false };
  } catch {
    return { index: null, stoerung };
  }
}

/* ⚠ UEBERGANG, kein Dauerzustand. Solange `leads-fristen.json` nicht im Datenspeicher
 * liegt (erster Lauf nach dem Umbau), muss der Alert-Lauf trotzdem funktionieren. Das
 * kostet dann aber wieder 110 MB — deshalb LAUT: eine Zeile im Protokoll ist der
 * Unterschied zwischen „Uebergang laeuft" und „wir haben nichts gewonnen und niemand hat
 * es gemerkt". */
let gewarnt = false;
async function ausAllenBranchen(): Promise<{ index: Map<string, LeadTiming>; stoerung: boolean }> {
  if (!gewarnt) {
    console.error("[fristen] Rückfall auf sieben leads-<branche>.json (110 MB) — "
                  + "leads-fristen.json fehlt. export_web_leads.py laufen lassen und hochladen.");
    gewarnt = true;
  }
  const idx = new Map<string, LeadTiming>();
  let stoerung = false;
  for (const b of BRANCHEN) {
    const { text: roh, grund } = await ladeMitGrund(`leads-${b}.json`);
    if (grund === DATEN_STOERUNG) stoerung = true;
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
  return { index: idx, stoerung };
}
