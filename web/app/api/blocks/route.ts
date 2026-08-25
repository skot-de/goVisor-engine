import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { verschluessele, entschluessele, KeinSchluessel } from "@/lib/blockCrypto";

export const runtime = "nodejs";     // Buffer + node:crypto

/* Bausteine ↔ `profile_text_blocks` (Ticket #23 §9, Deploy-Schicht).
 *
 * Die Bibliothek bleibt LOKAL-FIRST: ohne Anmeldung arbeitet sie unverändert im Browser
 * weiter (`localStorage.govisor.blocks`). Diese Route ist die Schicht darüber, damit die
 * Bausteine den Browser überleben.
 *
 * ⚠ WARUM NICHT DIREKT AUS DEM BROWSER, wie bei der Merkliste (`lib/supabase/watchlist.ts`)?
 * Weil der Inhalt verschlüsselt in die Spalte muss und der Schlüssel auf dem Server liegt.
 * Ein Browser-Modul müsste ihn ausliefern — dann wäre er keiner mehr.
 */

type Eingang = { theme?: string; content?: string; keywords?: string[]; origin?: string };

const THEMEN = new Set(["referenzen", "unternehmensdarstellung", "zertifikate_qm",
  "datenschutz_avv", "projektorganisation", "personal_qualifikation",
  "technische_ausstattung", "nachhaltigkeit", "sonstiges"]);

/* ⚠ `bytea` REIST ALS HEX-ZEICHENKETTE. PostgREST liefert `\x48616c6c6f` und erwartet
 * dieselbe Form beim Schreiben — ein Buffer würde als JSON-Objekt `{"0":72,…}` landen und
 * beim Lesen als Chiffrat unbrauchbar sein. Das fällt nicht beim Schreiben auf, sondern
 * erst beim nächsten Entschlüsseln. */
const zuHex = (b: Buffer) => "\\x" + b.toString("hex");
const ausHex = (s: string) => Buffer.from(s.startsWith("\\x") ? s.slice(2) : s, "hex");

async function sitzung() {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  return { sb, user };
}

/* ⚠ Die Middleware laesst `/api/blocks` ohne Sitzung gar nicht durch (`OFFEN` in
 * `web/middleware.ts` fuehrt es nicht) — anonym kommt hier ein 401 an, nicht diese Route.
 * Die Pruefung bleibt trotzdem stehen: sie ist die Zusicherung dieser Datei, nicht die
 * Wiederholung einer fremden. Ein `{anonym: true}`-Zweig stand hier kurz und war toter
 * Code — der Browser sieht diesen Fall nie. */
export async function GET() {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  const { data, error } = await sb.from("profile_text_blocks")
    .select("id, theme, content_encrypted, keywords, origin, updated_at")
    .eq("archived", false).order("updated_at", { ascending: false });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const blocks = [];
  let unlesbar = 0;
  for (const r of data ?? []) {
    try {
      blocks.push({
        id: r.id, theme: r.theme, content: entschluessele(ausHex(r.content_encrypted as string)),
        keywords: r.keywords ?? [], origin: r.origin ?? undefined, saved_at: r.updated_at,
      });
    } catch {
      // Ein Baustein, der sich nicht entschlüsseln lässt (falscher oder gewechselter
      // Hauptschlüssel), wird GEZÄHLT statt verschwiegen. Stillschweigend weglassen hiesse:
      // die Bibliothek sieht kleiner aus, und niemand fragt warum.
      unlesbar++;
    }
  }
  return NextResponse.json({ blocks, ...(unlesbar ? { unlesbar } : {}) });
}

export async function POST(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });

  let eingang: { blocks?: Eingang[] };
  try { eingang = await req.json(); } catch { return NextResponse.json({ error: "kein JSON" }, { status: 400 }); }
  const roh = Array.isArray(eingang.blocks) ? eingang.blocks : [];
  if (!roh.length) return NextResponse.json({ error: "keine Bausteine" }, { status: 400 });
  if (roh.length > 200) return NextResponse.json({ error: "zu viele auf einmal (max. 200)" }, { status: 400 });

  let saetze;
  try {
    saetze = roh
      .filter((b) => typeof b.content === "string" && b.content.trim().length >= 10)
      .map((b) => ({
        profile_id: user.id,
        theme: b.theme && THEMEN.has(b.theme) ? b.theme : "sonstiges",
        content_encrypted: zuHex(verschluessele(b.content!.trim())),
        keywords: Array.isArray(b.keywords) ? b.keywords.slice(0, 20) : null,
        origin: typeof b.origin === "string" ? b.origin.slice(0, 80) : null,
        last_edited_by: user.id,
      }));
  } catch (e) {
    if (e instanceof KeinSchluessel) {
      return NextResponse.json({ error: e.message }, { status: 503 });
    }
    throw e;
  }
  if (!saetze.length) return NextResponse.json({ error: "nichts Brauchbares dabei" }, { status: 400 });

  const { data, error } = await sb.from("profile_text_blocks").insert(saetze).select("id");
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ids: (data ?? []).map((r) => r.id), n: saetze.length });
}

/* ⚠ ARCHIVIEREN STATT LÖSCHEN (§9.2, so steht es auch im Schema). Ein Baustein, den jemand
 * aus der Ansicht nimmt, ist nicht wertlos — er kann in einem alten Angebot stecken, das
 * später noch begründet werden muss. Ein echtes DELETE nähme diese Möglichkeit endgültig. */
export async function DELETE(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  const id = new URL(req.url).searchParams.get("id") || "";
  if (!/^[0-9a-f-]{36}$/i.test(id)) return NextResponse.json({ error: "ungültige ID" }, { status: 400 });
  const { error } = await sb.from("profile_text_blocks")
    .update({ archived: true, last_edited_by: user.id }).eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
