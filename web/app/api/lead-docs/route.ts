import { NextResponse } from "next/server";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { rateLimit, darfNoch, clientIp } from "@/lib/rateLimit";

// Kosten-/Abuse-Bremse für die (teure) LLM-Analyse: pro IP und global gedeckelt.
const WINDOW_MS = 10 * 60 * 1000;   // 10-Minuten-Fenster
const PER_IP = 8;                    // je IP max. 8 Analysen / 10 min
const GLOBAL = 40;                   // gesamt max. 40 Analysen / 10 min (Kosten-Obergrenze)

// Vergabeunterlagen-Upload: Datei je notice_id speichern → Pipeline (index → signals →
// LLM-Analyse) fahren → aktualisierte Detail-Felder (lbText/lbSignals/lbAnalyse) zurückgeben.
// Läuft lokal (Node-Runtime, spawnt Python). Nicht für Vercel-Serverless gedacht.
export const runtime = "nodejs";
export const maxDuration = 120;

const ROOT = path.resolve(process.cwd(), "..");   // Server-cwd ist web/ → Repo-Wurzel eine Ebene höher
const ALLOWED = /\.(zip|pdf|docx?|xlsx?|txt|html?)$/i;

function runPipeline(id: string, buyer: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const args = ["scripts/process_upload.py", id];
    if (buyer) args.push(buyer.slice(0, 200));       // §5-4 Lead-Zuordnung (Käufer-Abgleich)
    const p = spawn("python3", args, { cwd: ROOT });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", reject);
    p.on("close", (code) => {
      if (code !== 0) return reject(new Error(err.slice(-300) || `Pipeline exit ${code}`));
      try {
        const last = out.trim().split("\n").filter(Boolean).pop() || "{}";
        resolve(JSON.parse(last));
      } catch {
        reject(new Error("Analyse-Ausgabe nicht lesbar"));
      }
    });
  });
}

export async function POST(req: Request) {
  const u = new URL(req.url);
  const id = u.searchParams.get("id") || "";
  const buyer = u.searchParams.get("buyer") || "";
  // notice_id-Muster erzwingen → kein Path-Traversal (keine / oder .).
  if (!/^[0-9A-Za-z_-]{3,40}$/.test(id)) {
    return NextResponse.json({ error: "ungültige id" }, { status: 400 });
  }
  // Rate-Limit VOR der teuren Analyse — pro IP und global (LLM-Kostenbremse).
  //
  // ⚠ HIER WIRD NUR NACHGESEHEN, NICHT VERBRAUCHT. Bis zum 2026-08-27 zählte diese Stelle
  // mit — vor dem Einlesen der Datei und vor jeder Gültigkeitsprüfung. Eine Anfrage ohne
  // Datei, mit falschem Typ oder zu grosser Datei bekam ihr 400 und hatte den Zähler
  // trotzdem verbraucht. Weil daneben ein GLOBALER Deckel steht, konnte ein angemeldeter
  // Nutzer mit 40 leeren Anfragen die Dokumentanalyse für ALLE anderen zehn Minuten lang
  // sperren, ohne eine einzige Analyse auszulösen — und ein kaputter Client, der stur
  // wiederholt, richtet dasselbe an, ohne es zu wollen.
  //
  // Verbraucht wird unten, unmittelbar bevor die Pipeline anläuft. Gezählt gehört, was man
  // schützen will: der teure Lauf, nicht die Anfrage.
  const ip = clientIp(req);
  const vorab = [darfNoch("leaddocs:global", GLOBAL), darfNoch(`leaddocs:ip:${ip}`, PER_IP)];
  const zuViel = vorab.find((r) => !r.ok);
  if (zuViel) {
    return NextResponse.json(
      { error: "Zu viele Analysen — bitte später erneut.", retryAfter: zuViel.retryAfter },
      { status: 429, headers: { "retry-after": String(zuViel.retryAfter) } });
  }
  let file: File | null = null;
  try {
    const form = await req.formData();
    const f = form.get("file");
    if (f instanceof File) file = f;
  } catch {
    return NextResponse.json({ error: "Upload nicht lesbar" }, { status: 400 });
  }
  if (!file) return NextResponse.json({ error: "keine Datei" }, { status: 400 });
  if (file.size > 60 * 1024 * 1024) {
    return NextResponse.json({ error: "Datei zu groß (max 60 MB)" }, { status: 400 });
  }
  const safe = path.basename(file.name).replace(/[^0-9A-Za-z._ -]/g, "_");
  if (!ALLOWED.test(safe)) {
    return NextResponse.json({ error: "Dateityp nicht unterstützt (ZIP/PDF/DOCX/XLSX)" }, { status: 400 });
  }

  const dir = path.join(ROOT, "data", "docs", "DE", id);
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, safe), Buffer.from(await file.arrayBuffer()));

  // Jetzt ist die Anfrage gültig und die Datei liegt — ab hier kostet es. Zählen.
  const gl = rateLimit("leaddocs:global", GLOBAL, WINDOW_MS);
  const perIp = rateLimit(`leaddocs:ip:${ip}`, PER_IP, WINDOW_MS);
  if (!gl.ok || !perIp.ok) {
    const retry = Math.max(gl.retryAfter, perIp.retryAfter);
    return NextResponse.json(
      { error: "Zu viele Analysen — bitte später erneut.", retryAfter: retry },
      { status: 429, headers: { "retry-after": String(retry) } });
  }

  try {
    return NextResponse.json(await runPipeline(id, buyer));
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 300) }, { status: 500 });
  }
}
