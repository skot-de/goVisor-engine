import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";

/**
 * Die Vergabeunterlagen eines Leads — Liste und einzelne Datei.
 *
 * **Warum es das gibt.** Wir laden die Unterlagen herunter, lesen sie aus und zeigen die
 * abgeleiteten Aussagen — aber das Dokument selbst konnte man nie öffnen. Gemessen
 * 2026-08-15 sind 30 % der bildreinen PDFs **Pläne und Zeichnungen** und nur 2 %
 * Fotodokumentation. Einen Lageplan will man sehen, nicht als Text lesen; OCR machte daraus
 * bestenfalls versprengte Beschriftungen.
 *
 * **⚠ LOKAL.** Die Archive liegen unter `data/docs` auf der Platte. Auf einem Deployment
 * ohne dieses Verzeichnis liefert die Route eine LEERE Liste mit Begründung — ehrlich leer,
 * nicht kaputt. Wer die Dokumente dort braucht, muss sie in einen Objektspeicher legen;
 * das ist eine eigene Entscheidung.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ROOT = path.resolve(process.cwd(), "..");

// Die Lead-Kennung wandert in einen Prozessaufruf. Sie wird deshalb hier UND im Python-
// Helfer geprueft: doppelt, weil ein Loch an dieser Stelle Dateien ausserhalb des
// Datenverzeichnisses erreichbar machte.
const LEAD_RE = /^[A-Za-z0-9_-]{1,64}$/;

function run(args: string[]): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/lead_dokumente.py", ...args], { cwd: ROOT });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", reject);
    // 30 s: ein grosses Archiv zu oeffnen dauert, aber nicht beliebig lang.
    const t = setTimeout(() => { p.kill("SIGKILL"); reject(new Error("Zeitgrenze")); }, 30_000);
    p.on("close", (code) => {
      clearTimeout(t);
      if (code !== 0) return reject(new Error(err.slice(-200) || `exit ${code}`));
      try { resolve(JSON.parse(out.trim().split("\n").filter(Boolean).pop() || "{}")); }
      catch { reject(new Error("Ausgabe nicht lesbar")); }
    });
  });
}

export async function GET(req: Request) {
  const u = new URL(req.url);
  const lead = u.searchParams.get("lead") || "";
  if (!LEAD_RE.test(lead)) {
    return NextResponse.json({ error: "ungültige Lead-Kennung" }, { status: 400 });
  }
  try {
    const d = await run(["--lead", lead]);
    return NextResponse.json(d);
  } catch (e) {
    // Fehlt `data/docs` (Deployment), ist das kein Fehler des Nutzers — die Liste ist
    // leer und sagt warum. Ein 500 waere hier irrefuehrend.
    return NextResponse.json({
      lead, dateien: [],
      grund: `Unterlagen lokal nicht verfügbar (${String((e as Error).message).slice(0, 80)})`,
    });
  }
}
