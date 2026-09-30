import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

/**
 * LLM & Kosten (Admin-Portal, Bereich 6). Live-Guthaben (OpenRouter /credits), Reserve/Halt/
 * Wartend (.llm_stand.json) und die Ausgaben aus dem Kostenbuch (scripts/kosten_uebersicht.py).
 *
 * ⚠ Gleiche Sperre wie die uebrigen /api/intern-Routen. Der OpenRouter-Key bleibt
 * serverseitig (.secrets/openrouter.key) — es geht nur das Guthaben nach vorn, nie der Key.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ROOT = path.resolve(process.cwd(), "..");

function llmStand() {
  try {
    const d = JSON.parse(fs.readFileSync(path.join(ROOT, "data", ".llm_stand.json"), "utf8"));
    return { erschoepft: !!d.erschoepft, halt: d.halt ?? null, haltGrund: d.halt_grund ?? null,
             wartend: d.wartend ?? null, fertig: d.fertig ?? null, zeit: d.zeit ?? null,
             anbieter: (d.anbieter ?? []).map((a: { name: string; modell: string; frei: number }) =>
               ({ name: a.name, modell: a.modell, frei: a.frei })) };
  } catch { return null; }
}

async function liveGuthaben() {
  let key = "";
  try { key = fs.readFileSync(path.join(ROOT, ".secrets", "openrouter.key"), "utf8").trim(); } catch { return null; }
  if (!key) return null;
  try {
    const ctrl = AbortSignal.timeout(8000);
    const r = await fetch("https://openrouter.ai/api/v1/credits",
      { headers: { authorization: `Bearer ${key}` }, signal: ctrl });
    if (!r.ok) return { fehler: `HTTP ${r.status}` };
    const j = await r.json();
    const d = j?.data ?? j;
    const total = Number(d.total_credits ?? 0);
    const usage = Number(d.total_usage ?? 0);
    return { total_credits: total, total_usage: usage, guthaben_usd: Math.round((total - usage) * 100) / 100 };
  } catch (e) { return { fehler: String((e as Error).message).slice(0, 80) }; }
}

function kosten(): Promise<Record<string, unknown> | null> {
  return new Promise((resolve) => {
    const p = spawn("python3", ["scripts/kosten_uebersicht.py"], { cwd: ROOT });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", () => resolve(null));
    const t = setTimeout(() => { p.kill("SIGKILL"); resolve(null); }, 30_000);
    p.on("close", (code) => {
      clearTimeout(t);
      if (code !== 0) return resolve(null);
      try { resolve(JSON.parse(out.trim().split("\n").filter(Boolean).pop() || "{}")); }
      catch { resolve(null); }
    });
  });
}

export async function GET() {
  if (process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1") {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const [live, ausgaben] = await Promise.all([liveGuthaben(), kosten()]);
  return NextResponse.json({ live, stand: llmStand(), ausgaben },
    { headers: { "cache-control": "no-store" } });
}
