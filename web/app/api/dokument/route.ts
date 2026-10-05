import "server-only";
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { verschluessele, entschluessele, KeinSchluessel } from "@/lib/blockCrypto";

export const runtime = "nodejs";          // Buffer + node:crypto fuer die Verschluesselung

/* Dokumente aus Bausteinen (Phase 1, Plan: `docs/funktion-dokument-bauen.md`, Schema: 0038).
 *
 * Ein Dokument ist eine geordnete Folge von Teilen: ein Verweis auf einen Baustein, eine
 * Ueberschrift oder freier Text.
 *
 * ⚠ VERWEIS, NICHT KOPIE. Ein Teil der Art `baustein` traegt nur die Kennung; der Inhalt kommt
 * beim Lesen aus `profile_text_blocks`. Wer eine Fassung einfrieren will, wandelt den Teil in
 * `text` um. Eine Kopie beim Anlegen waere bequemer und wuerde still veralten.
 *
 * ⚠ HIER GILT „WIR SPEICHERN NICHTS" NICHT. Dieser Satz steht in `/api/antwortauftrag` und
 * gehoert dorthin: ein Fragebogen ist Durchgangsware. Ein Dokument wird absichtlich gespeichert.
 * Deshalb verschluesselt (wie die Bausteine) und loeschbar.
 */

/* ⚠ `bytea` reist als Hex-Zeichenkette — dieselbe Falle wie in `/api/blocks`,
 * `/api/antwortauftrag` und `govisor/blockcrypto.py`. */
const zuHex = (b: Buffer) => "\\x" + b.toString("hex");
const ausHex = (s: string) => Buffer.from(s.startsWith("\\x") ? s.slice(2) : s, "hex");

const MAX_TEILE = 300;
const MAX_INHALT = 50_000;
const ARTEN = new Set(["baustein", "ueberschrift", "text"]);

type TeilEin = { art?: string; baustein_id?: string; inhalt?: string; ebene?: number };

async function sitzung() {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  return { sb, user };
}

async function orgVon(sb: Awaited<ReturnType<typeof createClient>>, uid: string) {
  const { data } = await sb.from("user_profiles").select("org_id").eq("id", uid).limit(1);
  return (data?.[0]?.org_id as string | undefined) ?? null;
}

function fehler(wo: string, e: { message: string }, satz: string, status = 500) {
  /* ⚠ Die Datenbankmeldung NICHT durchreichen. Lehre aus 0037: dort stand „Could not find the
   * table … in the schema cache" im Gesicht des Nutzers — fuer ihn sinnlos, fuer einen
   * Angreifer eine Auskunft ueber das Schema. */
  console.error(`[dokument] ${wo}:`, e.message);
  return NextResponse.json({ error: satz }, { status });
}

/** Prueft und normalisiert die Teile aus dem Netz. Wirft bei Unsinn. */
function teileLesen(roh: unknown): { art: string; baustein_id: string | null; inhalt: string | null;
                                     ebene: number | null }[] {
  if (!Array.isArray(roh)) throw new Error("Teile sind keine Liste");
  if (roh.length > MAX_TEILE) throw new Error(`Mehr als ${MAX_TEILE} Teile`);
  return roh.map((t: TeilEin, i) => {
    const art = String(t?.art ?? "");
    if (!ARTEN.has(art)) throw new Error(`Teil ${i + 1}: unbekannte Art`);
    if (art === "baustein") {
      const id = String(t.baustein_id ?? "");
      if (!id) throw new Error(`Teil ${i + 1}: Baustein fehlt`);
      return { art, baustein_id: id, inhalt: null, ebene: null };
    }
    const inhalt = String(t.inhalt ?? "");
    if (!inhalt.trim()) throw new Error(`Teil ${i + 1}: leerer Inhalt`);
    const ebene = art === "ueberschrift" ? Math.min(3, Math.max(1, Number(t.ebene) || 1)) : null;
    return { art, baustein_id: null, inhalt: inhalt.slice(0, MAX_INHALT), ebene };
  });
}

export async function GET(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  const id = new URL(req.url).searchParams.get("id");

  if (!id) {
    const { data, error } = await sb.from("profile_dokument")
      .select("id, titel, lead_id, profil_id, erstellt_at, updated_at")
      .order("updated_at", { ascending: false }).limit(50);
    if (error) return fehler("liste", error, "Die Dokumente konnten nicht geladen werden.");
    return NextResponse.json({
      dokumente: (data ?? []).map((d) => ({ ...d, eigen: d.profil_id === user.id })),
    });
  }

  const { data: dok, error: e1 } = await sb.from("profile_dokument")
    .select("id, titel, lead_id, profil_id, erstellt_at, updated_at").eq("id", id).limit(1);
  if (e1) return fehler("lesen", e1, "Das Dokument konnte nicht geladen werden.");
  if (!dok?.[0]) return NextResponse.json({ error: "Nicht gefunden" }, { status: 404 });

  const { data: teile, error: e2 } = await sb.from("profile_dokument_teil")
    .select("id, position, art, baustein_id, inhalt_encrypted, ebene")
    .eq("dokument_id", id).order("position", { ascending: true });
  if (e2) return fehler("teile", e2, "Die Teile konnten nicht geladen werden.");

  /* Die Inhalte der verwiesenen Bausteine in EINEM Zug holen, nicht je Teil. */
  const bids = [...new Set((teile ?? []).map((t) => t.baustein_id).filter(Boolean))] as string[];
  const bausteine = new Map<string, { theme: string; content: string }>();
  if (bids.length) {
    const { data: bs } = await sb.from("profile_text_blocks")
      .select("id, theme, content_encrypted").in("id", bids);
    for (const b of bs ?? []) {
      try {
        bausteine.set(b.id, { theme: b.theme,
                              content: entschluessele(ausHex(String(b.content_encrypted))) });
      } catch { /* unten als fehlende Quelle sichtbar */ }
    }
  }

  const raus = (teile ?? []).map((t) => {
    if (t.art === "baustein") {
      const b = t.baustein_id ? bausteine.get(t.baustein_id) : undefined;
      /* ⚠ Ein geloeschter oder unlesbarer Baustein wird SICHTBAR gemacht, nicht weggelassen.
       * Ein stillschweigend verschwundener Absatz ist der schlimmere Ausgang: das Dokument
       * saehe vollstaendig aus und waere es nicht. */
      return { id: t.id, art: t.art, baustein_id: t.baustein_id, ebene: null,
               thema: b?.theme ?? null, inhalt: b?.content ?? null, quelle_fehlt: !b };
    }
    let inhalt: string | null = null;
    try { inhalt = entschluessele(ausHex(String(t.inhalt_encrypted))); } catch { /* s. o. */ }
    return { id: t.id, art: t.art, baustein_id: null, ebene: t.ebene, thema: null,
             inhalt, quelle_fehlt: inhalt === null };
  });

  return NextResponse.json({
    dokument: { ...dok[0], eigen: dok[0].profil_id === user.id }, teile: raus,
  });
}

export async function POST(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });

  let titel = "Ohne Titel", lead_id: string | null = null;
  try {
    const b = await req.json();
    if (b.titel) titel = String(b.titel).slice(0, 200);
    lead_id = b.lead_id ? String(b.lead_id).slice(0, 64) : null;
  } catch { /* leerer Rumpf ist erlaubt: ein Dokument darf ohne Angaben entstehen */ }

  const org_id = await orgVon(sb, user.id);
  if (!org_id) return NextResponse.json({ error: "Keine Organisation hinterlegt." }, { status: 409 });

  const { data, error } = await sb.from("profile_dokument")
    .insert({ org_id, profil_id: user.id, titel, lead_id })
    .select("id, titel, lead_id, erstellt_at, updated_at").limit(1);
  if (error) return fehler("anlegen", error, "Das Dokument konnte nicht angelegt werden.");
  return NextResponse.json({ dokument: data?.[0] ?? null });
}

export async function PATCH(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  const id = new URL(req.url).searchParams.get("id");
  if (!id) return NextResponse.json({ error: "Kein Dokument genannt" }, { status: 400 });

  let titel: string | undefined;
  let teile: ReturnType<typeof teileLesen> | undefined;
  try {
    const b = await req.json();
    if (b.titel !== undefined) titel = String(b.titel).slice(0, 200);
    if (b.teile !== undefined) teile = teileLesen(b.teile);
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message || "Eingabe nicht lesbar" },
                             { status: 400 });
  }

  if (titel !== undefined) {
    const { error } = await sb.from("profile_dokument")
      .update({ titel, updated_at: new Date().toISOString() }).eq("id", id);
    if (error) return fehler("titel", error, "Der Titel konnte nicht gespeichert werden.");
  }

  if (teile) {
    /* ⚠ Die Teile werden GANZ ersetzt, nicht abgeglichen. Umsortieren, Einfuegen und Loeschen
     * in einem Zug ohne Abgleichlogik — die waere die naheliegende Quelle fuer Reihenfolge-
     * fehler. Der Preis steht hier, damit er nicht uebersehen wird: arbeiten zwei Menschen
     * gleichzeitig am selben Dokument, gewinnt der letzte Schreiber vollstaendig. Fuer Phase 1
     * ist das vertretbar; wer Gleichzeitigkeit braucht, braucht ohnehin mehr als diese Route. */
    let reihen;
    try {
      reihen = teile.map((t, i) => ({
        dokument_id: id, position: (i + 1) * 10, art: t.art, baustein_id: t.baustein_id,
        ebene: t.ebene,
        inhalt_encrypted: t.inhalt === null ? null : zuHex(verschluessele(t.inhalt)),
      }));
    } catch (e) {
      /* Fehlt der Schluessel, wird NICHT im Klartext gespeichert — es wird gar nicht gespeichert. */
      if (e instanceof KeinSchluessel) {
        return NextResponse.json({ error: "Verschluesselung nicht eingerichtet." }, { status: 503 });
      }
      throw e;
    }

    const { error: eDel } = await sb.from("profile_dokument_teil").delete().eq("dokument_id", id);
    if (eDel) return fehler("teile loeschen", eDel, "Die Teile konnten nicht gespeichert werden.");
    if (reihen.length) {
      const { error: eIns } = await sb.from("profile_dokument_teil").insert(reihen);
      if (eIns) return fehler("teile schreiben", eIns, "Die Teile konnten nicht gespeichert werden.");
    }
    await sb.from("profile_dokument").update({ updated_at: new Date().toISOString() }).eq("id", id);
  }

  return NextResponse.json({ ok: true });
}

export async function DELETE(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  const id = new URL(req.url).searchParams.get("id");
  if (!id) return NextResponse.json({ error: "Kein Dokument genannt" }, { status: 400 });

  const { error } = await sb.from("profile_dokument").delete().eq("id", id);
  if (error) return fehler("loeschen", error, "Das Dokument konnte nicht geloescht werden.");
  return NextResponse.json({ ok: true });
}
