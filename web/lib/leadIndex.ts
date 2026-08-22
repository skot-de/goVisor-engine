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
