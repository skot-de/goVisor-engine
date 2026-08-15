import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { randomUUID } from "node:crypto";

/**
 * EINE Datei aus den Vergabeunterlagen ausliefern — zum Ansehen oder Herunterladen.
 *
 * **Der Pfad aus dem Browser wird nie zum Öffnen benutzt.** Der Python-Helfer läuft die
 * Einträge des Archivs durch und nimmt den, der exakt passt — es gibt gar keine
 * Pfad-Verkettung, an der ein `../` etwas erreichen könnte. Zusätzlich prüft diese Route
 * die Lead-Kennung gegen ein enges Muster.
 *
 * **Was NICHT inline geht:** aktive Inhalte (`.js`, `.exe`, …) werden gar nicht ausgeliefert,
 * SVG nur als Download — SVG kann Skripte tragen, und ein inline gerendertes SVG aus fremder
 * Quelle wäre eine XSS-Lücke mitten im Produkt.
 *
 * ⚠ OFFEN UND BEWUSST SO: hier greift KEINE PII-Schwärzung. Das Projekt schwärzt beim
 * Extrahieren (Ticket 23), aber eine Originaldatei geht unverändert raus. Für Pläne und
 * Zeichnungen ist das unkritisch, für eingescannte Formulare nicht unbedingt. Wer das
 * Feature über den internen Gebrauch hinaus öffnet, muss diese Frage vorher beantworten.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ROOT = path.resolve(process.cwd(), "..");
const LEAD_RE = /^[A-Za-z0-9_-]{1,64}$/;

function run(args: string[]): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/lead_dokumente.py", ...args], { cwd: ROOT });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", reject);
    const t = setTimeout(() => { p.kill("SIGKILL"); reject(new Error("Zeitgrenze")); }, 60_000);
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
  const datei = u.searchParams.get("datei") || "";
  if (!LEAD_RE.test(lead) || !datei || datei.length > 400) {
    return new Response("ungültige Anfrage", { status: 400 });
  }

  const tmp = path.join(os.tmpdir(), `govisor-${randomUUID()}`);
  try {
    const r = await run(["--lead", lead, "--datei", datei, "--nach", tmp]);
    if (r.fehler) return new Response(String(r.fehler), { status: 404 });

    const bytes = fs.readFileSync(tmp);
    const name = String(r.name || "datei");
    // `inline` nur fuer Formate, die der Browser gefahrlos selbst zeigt. Alles andere
    // wird heruntergeladen — der Helfer entscheidet das, nicht die Endung im Aufruf.
    const anordnung = r.inline ? "inline" : "attachment";
    return new Response(new Uint8Array(bytes), {
      headers: {
        "Content-Type": String(r.typ || "application/octet-stream"),
        // Der Dateiname stammt aus dem Archiv (fremde Quelle) → als RFC-5987-Parameter
        // kodiert, damit Anfuehrungszeichen oder Zeilenumbrueche den Header nicht spalten.
        "Content-Disposition":
          `${anordnung}; filename*=UTF-8''${encodeURIComponent(name)}`,
        // Kein Ausfuehren, kein Erraten des Typs — beides waere bei fremden Dateien riskant.
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'",
        "Cache-Control": "private, max-age=300",
      },
    });
  } catch (e) {
    return new Response(`nicht verfügbar: ${String((e as Error).message).slice(0, 120)}`,
                        { status: 404 });
  } finally {
    try { fs.unlinkSync(tmp); } catch { /* schon weg */ }
  }
}
