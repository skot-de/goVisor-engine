import { NextResponse } from "next/server";
import { freischalten, vorgangStand } from "@/lib/kontingent";

/**
 * Vorgangs-Kontingent (Preismodell v1.9 §4.3). GET liefert den Zaehlerstand, POST schaltet
 * einen Vorgang frei. Hinter dem Anmeldetor (middleware.ts). Das Limit setzt der Server
 * (lib/kontingent.ts) — hier wird nichts vom Client ueber das Kontingent entschieden.
 *
 * ⚠ NICHT /api/vorgang — das ist die Vorgangsakte. Dies ist die Abrechnungseinheit (§4.3).
 * ⚠ Noch NICHT an die Ausloeser verdrahtet: das erste Oeffnen von Unterlagen/Bewertung bzw.
 * der Einzelaufruf eines Firmenprofils muss diesen POST rufen — das ist Teil der §3/§4-Gating-
 * Oberflaeche (blur/CTA) und kommt mit ihr. Solange die Paywall aus ist, ist das Limit null
 * (unbegrenzt), der Aufruf also folgenlos.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(await vorgangStand(), { headers: { "cache-control": "no-store" } });
}

export async function POST(req: Request) {
  let body: { art?: string; ref?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }
  const art = body.art === "lead" ? "lead" : body.art === "firma" ? "firma" : null;
  const ref = String(body.ref ?? "").trim();
  if (!art) return NextResponse.json({ error: "art ∈ {lead,firma}" }, { status: 400 });
  if (!ref || ref.length > 200) return NextResponse.json({ error: "ref ungültig" }, { status: 400 });

  const r = await freischalten(art, ref);
  if (!r.ok) {
    return NextResponse.json({ error: r.error },
      { status: r.error === "Anmeldung erforderlich" ? 401 : 400 });
  }
  return NextResponse.json({ ok: true, status: r.status, stand: await vorgangStand() });
}
