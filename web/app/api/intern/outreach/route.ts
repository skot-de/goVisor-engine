import { NextResponse } from "next/server";
import path from "node:path";
import { spawn } from "node:child_process";

// INTERN: Outreach-Log (scripts/outreach_log.py) — POST protokolliert eine Ansprache (12-Monats-
// Sperre + Trefferquote), GET liefert die Sperr-Map + Trefferquote. In Production hart blockiert.
export const runtime = "nodejs";
export const maxDuration = 20;

const ROOT = path.resolve(process.cwd(), "..");
const ID_RE = /^(grp|solo):[0-9A-Za-z:._-]{1,120}$/;
const SEG_RE = /^[A-G]$/;
const OUTCOMES = ["angesprochen", "interessiert", "gewonnen", "kein_interesse", "kein_kontakt"];
const TEXT_RE = /^[0-9A-Za-zäöüÄÖÜß .,&'/+()-]{0,80}$/;

function run(args: string[]): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/outreach_log.py", ...args], { cwd: ROOT });
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

function blocked() {
  return process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1";
}

export async function GET() {
  if (blocked()) return NextResponse.json({ error: "not found" }, { status: 404 });
  try {
    const [cooldown, trefferquote] = await Promise.all([run(["--cooldown"]), run(["--trefferquote"])]);
    return NextResponse.json({ cooldown, trefferquote });
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 200) }, { status: 500 });
  }
}

export async function POST(req: Request) {
  if (blocked()) return NextResponse.json({ error: "not found" }, { status: 404 });
  let body: Record<string, string>;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "kein JSON" }, { status: 400 }); }
  const id = String(body.id || "");
  const segment = String(body.segment || "");
  const outcome = String(body.outcome || "angesprochen");
  const name = String(body.name || "");
  if (!ID_RE.test(id)) return NextResponse.json({ error: "ungültige ID" }, { status: 400 });
  if (segment && !SEG_RE.test(segment)) return NextResponse.json({ error: "ungültiges Segment" }, { status: 400 });
  if (!OUTCOMES.includes(outcome)) return NextResponse.json({ error: "ungültiger Ausgang" }, { status: 400 });
  if (name && !TEXT_RE.test(name)) return NextResponse.json({ error: "ungültiger Name" }, { status: 400 });
  const args = ["--log", "--id", id, "--outcome", outcome];
  if (segment) args.push("--segment", segment);
  if (name) args.push("--name", name);
  try {
    return NextResponse.json(await run(args));
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 200) }, { status: 500 });
  }
}
