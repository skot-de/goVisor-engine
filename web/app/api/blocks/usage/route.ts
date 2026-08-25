import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";

/* Ein VORHANDENER Baustein wird in einem Vorgang verwendet (§9.3).
 *
 * Das ist der andere Weg als in `../route.ts`: dort entsteht ein Baustein aus einer
 * Checkliste und wird im selben Zug als verwendet vermerkt. Hier greift jemand auf einen
 * Baustein zurück, den es längst gibt — und genau das ist die Zahl, die zählt. Ein
 * Baustein, der in fünf Vorgängen half, ist ein anderer als einer, der einmal entstand.
 *
 * ⚠ Kein eigener Rechte-Nachweis nötig: die Regel auf `profile_block_usage` lässt einen
 * Eintrag nur zu, wenn der Baustein dem Anmeldenden gehört (0006). Geprüft am 2026-08-25
 * mit einer FREMDEN, aber bekannten Baustein-Kennung: abgelehnt.
 */
export async function POST(req: Request) {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });

  let eingang: { block_id?: string; lead_id?: string };
  try { eingang = await req.json(); } catch { return NextResponse.json({ error: "kein JSON" }, { status: 400 }); }
  const blockId = String(eingang.block_id || "");
  const leadId = String(eingang.lead_id || "");
  if (!/^[0-9a-f-]{36}$/i.test(blockId)) return NextResponse.json({ error: "ungültige Baustein-ID" }, { status: 400 });
  if (!leadId || leadId.length > 64) return NextResponse.json({ error: "ungültiger Vorgang" }, { status: 400 });

  // ⚠ `.select()` wie bei den anderen schreibenden Wegen: greift die Regel nicht, liefert
  // PostgREST null Zeilen OHNE Fehler — ein `ok` darauf wäre gelogen. Derselbe Fall ist am
  // 2026-08-25 beim Archivieren aufgefallen.
  const { data, error } = await sb.from("profile_block_usage")
    .insert({ block_id: blockId, lead_id: leadId }).select("id");
  if (error) {
    // ⚠ BEIM EINFUEGEN WIRFT DIE REGEL, sie liefert keine leere Antwort — anders als beim
    // Aendern, wo null Zeilen zurueckkommen. Gemessen am 2026-08-25: ein fremder Nutzer bekam
    // „new row violates row-level security policy for table \"profile_block_usage\"" zu
    // lesen. Das ist ein Blick in die Innereien und erklaert nichts; es sagt einem Menschen
    // nicht, was er falsch gemacht hat, und einem Angreifer mehr, als er wissen muss.
    if (error.code === "42501") {
      return NextResponse.json({ error: "Nicht dein Baustein." }, { status: 403 });
    }
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  if (!data?.length) {
    return NextResponse.json({ error: "Nicht dein Baustein." }, { status: 403 });
  }
  return NextResponse.json({ ok: true });
}
