import { NextResponse } from "next/server";
import { mkdir, writeFile, rm, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";

// Ticket #23 §B.2 — Vergabestellen-Entwurf → Nachweisdichte. Datei temporär ablegen, zählen,
// danach verwerfen (nicht persistiert). Läuft lokal (Node spawnt Python).
export const runtime = "nodejs";
export const maxDuration = 60;

const ROOT = path.resolve(process.cwd(), "..");
const ALLOWED = /\.(zip|pdf|docx?|xlsx?|txt|html?)$/i;

function count(file: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/draft_check.py", file], { cwd: ROOT });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", reject);
    p.on("close", (code) => {
      if (code !== 0) return reject(new Error(err.slice(-200) || `exit ${code}`));
      try { resolve(JSON.parse(out.trim().split("\n").filter(Boolean).pop() || "{}")); }
      catch { reject(new Error("Ausgabe nicht lesbar")); }
    });
  });
}

async function baseline(branche: string): Promise<Record<string, unknown>> {
  try {
    const raw = JSON.parse(await readFile(path.join(ROOT, "web", "data", "nachweis-median.json"), "utf-8"));
    const b = raw[branche] || raw._overall || {};
    return { median: b.median ?? null, p75: b.p75 ?? null, median_n: b.n ?? null, branche };
  } catch { return {}; }
}

export async function POST(req: Request) {
  const branche = new URL(req.url).searchParams.get("branche") || "_overall";
  let file: File | null = null;
  try { const f = (await req.formData()).get("file"); if (f instanceof File) file = f; }
  catch { return NextResponse.json({ error: "Upload nicht lesbar" }, { status: 400 }); }
  if (!file) return NextResponse.json({ error: "keine Datei" }, { status: 400 });
  if (file.size > 60 * 1024 * 1024) return NextResponse.json({ error: "Datei zu groß (max 60 MB)" }, { status: 400 });
  const safe = path.basename(file.name).replace(/[^0-9A-Za-z._ -]/g, "_");
  if (!ALLOWED.test(safe)) return NextResponse.json({ error: "Dateityp nicht unterstützt" }, { status: 400 });

  const dir = path.join(os.tmpdir(), "govisor-draft-" + Math.random().toString(36).slice(2));
  await mkdir(dir, { recursive: true });
  const fp = path.join(dir, safe);
  try {
    await writeFile(fp, Buffer.from(await file.arrayBuffer()));
    const [c, b] = await Promise.all([count(fp), baseline(branche)]);
    return NextResponse.json({ ...c, ...b });
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 200) }, { status: 500 });
  } finally {
    await rm(dir, { recursive: true, force: true }).catch(() => {});   // Entwurf nicht behalten
  }
}
