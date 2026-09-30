import { NextResponse } from "next/server";
import path from "node:path";
import { spawn } from "node:child_process";

// INTERN: erzeugt die Outreach-Landing (/t/<token>) für eine Zielfirma (scripts/export_outreach.py)
// und gibt den Token zurück. In Production hart blockiert (schreibt Daten, internes Werkzeug).
export const runtime = "nodejs";
export const maxDuration = 30;

const ROOT = path.resolve(process.cwd(), "..");
// identity_id-Raum: umfasst Umlaute (z. B. `solo:id:HRB99804Köln`) und `/` (z. B.
// `solo:id:114/5559/4478`). Kein Shell (spawn-argv) und kein Pfadbau aus der ID im Skript
// (nur parametrisiertes SQL + HMAC), deshalb sind diese Zeichen hier sicher.
const ID_RE = /^(grp|solo):[0-9A-Za-zäöüÄÖÜß:._/-]{1,120}$/;
// Der Token wird NICHT nachgerechnet — er ist gesalzenes HMAC (export_outreach.token_of),
// dessen Geheimnis serverseitig liegt. Das Skript druckt die fertige Adresse `/t/<token>`.
const TOKEN_RE = /\/t\/([0-9a-f]{12,32})/;

function gen(id: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const p = spawn("python3", ["scripts/export_outreach.py", "--id", id], { cwd: ROOT });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", reject);
    p.on("close", (code) => {
      if (code !== 0) return reject(new Error(err.slice(-200) || `exit ${code}`));
      const m = out.match(TOKEN_RE);
      if (!m) return reject(new Error("Token nicht aus der Ausgabe lesbar"));
      resolve(m[1]);
    });
  });
}

export async function POST(req: Request) {
  if (process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1") {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const id = new URL(req.url).searchParams.get("id") || "";
  if (!ID_RE.test(id)) return NextResponse.json({ error: "ungültige ID" }, { status: 400 });
  try {
    const token = await gen(id);
    return NextResponse.json({ token, url: `/t/${token}` });
  } catch (e) {
    return NextResponse.json({ error: String((e as Error).message).slice(0, 200) }, { status: 500 });
  }
}
