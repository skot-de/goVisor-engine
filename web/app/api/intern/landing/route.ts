import { NextResponse } from "next/server";
import path from "node:path";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";

// INTERN: erzeugt die Outreach-Landing (/t/<token>) für eine Zielfirma (scripts/export_outreach.py)
// und gibt den Token zurück. In Production hart blockiert (schreibt Daten, internes Werkzeug).
export const runtime = "nodejs";
export const maxDuration = 30;

const ROOT = path.resolve(process.cwd(), "..");
const ID_RE = /^(grp|solo):[0-9A-Za-z:._-]{1,120}$/;

function gen(id: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/export_outreach.py", "--id", id], { cwd: ROOT });
    let err = "";
    p.stderr.on("data", (d) => (err += d));
    p.on("error", reject);
    p.on("close", (code) => (code === 0 ? resolve() : reject(new Error(err.slice(-200) || `exit ${code}`))));
  });
}

export async function POST(req: Request) {
  if (process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1") {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const id = new URL(req.url).searchParams.get("id") || "";
  if (!ID_RE.test(id)) return NextResponse.json({ error: "ungültige ID" }, { status: 400 });
  try {
    await gen(id);
    // Token deterministisch = sha1(identity_id)[:10] (identisch zu export_outreach.token_of)
    const token = createHash("sha1").update(id).digest("hex").slice(0, 10);
    return NextResponse.json({ token, url: `/t/${token}` });
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 200) }, { status: 500 });
  }
}
