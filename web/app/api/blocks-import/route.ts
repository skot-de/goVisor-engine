import { NextResponse } from "next/server";
import path from "node:path";
import { spawn } from "node:child_process";

// Ticket #23 §10 — Alt-Angebot-Import: Text → PII-Schwärzung + Baustein-Extraktion (govisor/blocks).
// Das Originaldokument wird NICHT gespeichert (§10.2); nur der geschwärzte Text geht durch und
// zurückgegeben werden ausschließlich die Bausteine. Läuft lokal (Node spawnt Python).
export const runtime = "nodejs";
export const maxDuration = 60;

const ROOT = path.resolve(process.cwd(), "..");

function extract(text: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/import_blocks.py"], { cwd: ROOT });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", reject);
    p.on("close", (code) => {
      if (code !== 0) return reject(new Error(err.slice(-300) || `exit ${code}`));
      try { resolve(JSON.parse(out.trim().split("\n").filter(Boolean).pop() || "{}")); }
      catch { reject(new Error("Import-Ausgabe nicht lesbar")); }
    });
    p.stdin.write(text); p.stdin.end();
  });
}

export async function POST(req: Request) {
  let text = "";
  try { text = String((await req.json()).text || ""); }
  catch { return NextResponse.json({ error: "Text nicht lesbar" }, { status: 400 }); }
  if (text.trim().length < 40) {
    return NextResponse.json({ error: "Zu wenig Text für einen Baustein" }, { status: 400 });
  }
  if (text.length > 400_000) text = text.slice(0, 400_000);
  try {
    return NextResponse.json(await extract(text));
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 300) }, { status: 500 });
  }
}
