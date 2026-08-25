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

type Eingang = { theme?: string; content?: string; keywords?: string[]; origin?: string;
  sichtbarkeit?: string };

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

/* Die Firma, in die dieser Mensch freigeben DARF — `null`, wenn keine belegt ist.
 *
 * ⚠ NICHT `user_profiles.identity_id`. Das ist eine Selbstauskunft: `saveIdentityCorrection`
 * (§7.3) lässt jeden Nutzer sie frei setzen. Wer den Namen einer fremden Firma einträgt,
 * bekäme sonst deren freigegebene Bausteine zu sehen. Massgeblich ist der BELEGTE Anspruch,
 * den `/api/entity-verify` über die Firmen-Domain vergibt — nicht ein Textfeld.
 * Dieselbe Bedingung steht in der RLS (0016); hier steht sie, um eine ehrliche Fehlermeldung
 * geben zu können statt eines nackten Datenbankfehlers. */
async function belegteFirma(sb: Awaited<ReturnType<typeof createClient>>, uid: string) {
  const { data } = await sb.from("identity_claims").select("identity_id")
    .eq("user_id", uid).in("status", ["belegt", "geprueft"]).limit(1);
  return (data?.[0]?.identity_id as string | undefined) ?? null;
}

/* ⚠ Die Middleware laesst `/api/blocks` ohne Sitzung gar nicht durch (`OFFEN` in
 * `web/middleware.ts` fuehrt es nicht) — anonym kommt hier ein 401 an, nicht diese Route.
 * Die Pruefung bleibt trotzdem stehen: sie ist die Zusicherung dieser Datei, nicht die
 * Wiederholung einer fremden. Ein `{anonym: true}`-Zweig stand hier kurz und war toter
 * Code — der Browser sieht diesen Fall nie. */
export async function GET() {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  // `profile_id` und `sichtbarkeit` gehoeren mit: die Ansicht muss den eigenen Baustein vom
  // freigegebenen einer Kollegin unterscheiden koennen — sonst bietet sie ein Loeschen an,
  // das die Regel ohnehin verweigert.
  const { data, error } = await sb.from("profile_text_blocks")
    .select("id, theme, content_encrypted, keywords, origin, updated_at, sichtbarkeit, profile_id")
    .eq("archived", false).order("updated_at", { ascending: false });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const blocks = [];
  let unlesbar = 0;
  for (const r of data ?? []) {
    try {
      blocks.push({
        id: r.id, theme: r.theme, content: entschluessele(ausHex(r.content_encrypted as string)),
        keywords: r.keywords ?? [], origin: r.origin ?? undefined, saved_at: r.updated_at,
        sichtbarkeit: r.sichtbarkeit ?? "privat", eigen: r.profile_id === user.id,
      });
    } catch {
      // Ein Baustein, der sich nicht entschlüsseln lässt (falscher oder gewechselter
      // Hauptschlüssel), wird GEZÄHLT statt verschwiegen. Stillschweigend weglassen hiesse:
      // die Bibliothek sieht kleiner aus, und niemand fragt warum.
      unlesbar++;
    }
  }
  // Ob dieser Mensch ueberhaupt freigeben kann, entscheidet die Ansicht nicht selbst —
  // sonst raet sie, und ein ausgegrauter Schalter ohne Begruendung ist schlimmer als keiner.
  const firma = await belegteFirma(sb, user.id);
  return NextResponse.json({ blocks, firma, ...(unlesbar ? { unlesbar } : {}) });
}

export async function POST(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });

  let eingang: { blocks?: Eingang[] };
  try { eingang = await req.json(); } catch { return NextResponse.json({ error: "kein JSON" }, { status: 400 }); }
  const roh = Array.isArray(eingang.blocks) ? eingang.blocks : [];
  if (!roh.length) return NextResponse.json({ error: "keine Bausteine" }, { status: 400 });
  if (roh.length > 200) return NextResponse.json({ error: "zu viele auf einmal (max. 200)" }, { status: 400 });

  // Freigeben kann nur, wer eine Firma BELEGT hat. Wer keine hat, legt privat an — statt
  // einen Datenbankfehler zu bekommen, den niemand lesen kann.
  const willFirma = roh.some((b) => b.sichtbarkeit === "firma");
  const firma = willFirma ? await belegteFirma(sb, user.id) : null;
  if (willFirma && !firma) {
    return NextResponse.json({
      error: "Freigeben an die Firma geht erst, wenn eure Firmenzugehörigkeit belegt ist "
             + "(über die Firmen-Domain im Onboarding).", firma: null }, { status: 409 });
  }

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
        sichtbarkeit: b.sichtbarkeit === "firma" ? "firma" : "privat",
        // ⚠ EINGEFROREN, nicht mitwandernd: wer spaeter die Firma wechselt, zieht seine
        // freigegebenen Bausteine nicht in die neue mit. Sie bleiben, wo sie freigegeben
        // wurden, bis der Eigentuemer sie zurueckzieht.
        identity_id: b.sichtbarkeit === "firma" ? firma : null,
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

/** Freigabe umstellen — privat ↔ Firma. Nur der Eigentümer; die Regel erzwingt es zusätzlich. */
export async function PATCH(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  let eingang: { id?: string; sichtbarkeit?: string };
  try { eingang = await req.json(); } catch { return NextResponse.json({ error: "kein JSON" }, { status: 400 }); }
  const id = String(eingang.id || "");
  if (!/^[0-9a-f-]{36}$/i.test(id)) return NextResponse.json({ error: "ungültige ID" }, { status: 400 });
  const nachFirma = eingang.sichtbarkeit === "firma";

  const firma = nachFirma ? await belegteFirma(sb, user.id) : null;
  if (nachFirma && !firma) {
    return NextResponse.json({
      error: "Freigeben an die Firma geht erst, wenn eure Firmenzugehörigkeit belegt ist "
             + "(über die Firmen-Domain im Onboarding)." }, { status: 409 });
  }
  const { data, error } = await sb.from("profile_text_blocks").update({
    sichtbarkeit: nachFirma ? "firma" : "privat",
    // Beim Zuruecknehmen wird die Firma GELOESCHT, nicht behalten: ein privater Baustein
    // mit Firmenvermerk saehe aus wie ein Rest, den jemand vergessen hat.
    identity_id: nachFirma ? firma : null,
    last_edited_by: user.id, updated_at: new Date().toISOString(),
  }).eq("id", id).eq("profile_id", user.id).select("id");
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  // Gleicher Grund wie beim Archivieren: null getroffene Zeilen sind kein Fehler, sondern
  // eine leere Antwort — und ein `ok` darauf wäre falsch.
  if (!data?.length) {
    return NextResponse.json({ error: "Nicht dein Baustein — nur die anlegende Person kann "
                                     + "die Freigabe ändern." }, { status: 403 });
  }
  return NextResponse.json({ ok: true, sichtbarkeit: nachFirma ? "firma" : "privat" });
}

/* ⚠ ARCHIVIEREN STATT LÖSCHEN (§9.2, so steht es auch im Schema). Ein Baustein, den jemand
 * aus der Ansicht nimmt, ist nicht wertlos — er kann in einem alten Angebot stecken, das
 * später noch begründet werden muss. Ein echtes DELETE nähme diese Möglichkeit endgültig. */
export async function DELETE(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  const id = new URL(req.url).searchParams.get("id") || "";
  if (!/^[0-9a-f-]{36}$/i.test(id)) return NextResponse.json({ error: "ungültige ID" }, { status: 400 });
  // ⚠ `.select()` IST HIER KEINE ZIERDE. Trifft die Regel keine Zeile — weil der Baustein
  // jemand anderem gehört —, liefert PostgREST KEINEN Fehler, sondern null Zeilen. Ohne
  // diese Prüfung meldete die Route `ok`, obwohl nichts geschah. Am 2026-08-25 im
  // Durchlauf aufgefallen: Nutzer B bekam „ok" für das Archivieren eines fremden
  // Bausteins, der danach unverändert dastand. Die Daten waren sicher, die Antwort war
  // eine Lüge — und die ist schlimmer, weil niemand nachsieht.
  const { data, error } = await sb.from("profile_text_blocks")
    .update({ archived: true, last_edited_by: user.id }).eq("id", id).select("id");
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!data?.length) {
    return NextResponse.json({ error: "Nicht dein Baustein — nur die anlegende Person kann "
                                     + "ihn archivieren." }, { status: 403 });
  }
  return NextResponse.json({ ok: true });
}
