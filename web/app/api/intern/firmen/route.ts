import { NextResponse } from "next/server";
import path from "node:path";
import { spawn } from "node:child_process";

// INTERNES Vertriebstool — Firmen-Suche nach Sitz/Name + Schmerz-Signale (scripts/firmen_suche.py).
// Enthält Kontaktdaten → NUR intern. In Production hart blockiert, außer INTERN_ENABLED=1 gesetzt.
export const runtime = "nodejs";
export const maxDuration = 30;

const ROOT = path.resolve(process.cwd(), "..");
const ID_RE = /^(grp|solo):[0-9A-Za-z:._-]{1,120}$/;
const SAFE = /^[0-9A-Za-zäöüÄÖÜß .,&'/+-]{1,60}$/;   // konservativ für Name/Ort/PLZ

function run(args: string[]): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/firmen_suche.py", ...args], { cwd: ROOT });
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

export async function GET(req: Request) {
  // Internes Tool: in Production nur mit explizitem Flag erreichbar (nie öffentlich).
  if (process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1") {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const u = new URL(req.url);
  const id = u.searchParams.get("id");
  const seg = u.searchParams.get("segment");
  try {
    if (id) {
      if (!ID_RE.test(id)) return NextResponse.json({ error: "ungültige ID" }, { status: 400 });
      return NextResponse.json(await run(["--detail", id]));
    }
    if (seg) {
      if (!/^[A-G]$/.test(seg)) return NextResponse.json({ error: "ungültiges Segment" }, { status: 400 });
      const p = (u.searchParams.get("p") || "").trim();
      const args = ["--segment", seg];
      // Knopf-Overrides: streng validiertes k:v,k:v (nur Kleinbuchstaben-Keys + Zahlen)
      if (p) {
        if (!/^[a-z_]+:[0-9.]+(,[a-z_]+:[0-9.]+)*$/.test(p)) return NextResponse.json({ error: "ungültige Parameter" }, { status: 400 });
        args.push("--params", p);
      }
      // Geo-Filter auf den Firmensitz (optional): plz/ort/nuts + radius
      for (const k of ["plz", "ort", "nuts"] as const) {
        const v = (u.searchParams.get(k) || "").trim();
        if (v) {
          if (!SAFE.test(v)) return NextResponse.json({ error: `ungültiger ${k}` }, { status: 400 });
          args.push(`--${k}`, v);
        }
      }
      const gradius = (u.searchParams.get("radius") || "").trim();
      if (gradius) {
        if (!/^\d{1,3}$/.test(gradius)) return NextResponse.json({ error: "ungültiger radius" }, { status: 400 });
        args.push("--radius", gradius);
      }
      return NextResponse.json(await run(args));
    }
    const args = ["--search"];
    for (const k of ["plz", "ort", "name"] as const) {
      const v = (u.searchParams.get(k) || "").trim();
      if (v) {
        if (!SAFE.test(v)) return NextResponse.json({ error: `ungültiger ${k}` }, { status: 400 });
        args.push(`--${k}`, v);
      }
    }
    const radius = (u.searchParams.get("radius") || "").trim();
    if (radius) {
      if (!/^\d{1,3}$/.test(radius)) return NextResponse.json({ error: "ungültiger radius" }, { status: 400 });
      args.push("--radius", radius);
    }
    if (args.length === 1) return NextResponse.json({ error: "Bitte PLZ, Ort oder Name angeben" }, { status: 400 });
    return NextResponse.json(await run(args));
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 200) }, { status: 500 });
  }
}
