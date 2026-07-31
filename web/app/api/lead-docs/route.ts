import { NextResponse } from "next/server";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

// Vergabeunterlagen-Upload: Datei je notice_id speichern → Pipeline (index → signals →
// LLM-Analyse) fahren → aktualisierte Detail-Felder (lbText/lbSignals/lbAnalyse) zurückgeben.
// Läuft lokal (Node-Runtime, spawnt Python). Nicht für Vercel-Serverless gedacht.
export const runtime = "nodejs";
export const maxDuration = 120;

const ROOT = path.resolve(process.cwd(), "..");   // Server-cwd ist web/ → Repo-Wurzel eine Ebene höher
const ALLOWED = /\.(zip|pdf|docx?|xlsx?|txt|html?)$/i;

function runPipeline(id: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/process_upload.py", id], { cwd: ROOT });
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
  const id = new URL(req.url).searchParams.get("id") || "";
  // notice_id-Muster erzwingen → kein Path-Traversal (keine / oder .).
  if (!/^[0-9A-Za-z_-]{3,40}$/.test(id)) {
    return NextResponse.json({ error: "ungültige id" }, { status: 400 });
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

  try {
    return NextResponse.json(await runPipeline(id));
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 300) }, { status: 500 });
  }
}
