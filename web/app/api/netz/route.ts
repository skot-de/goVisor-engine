import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { loadFirmaProfiles } from "@/lib/firmaProfiles";
import { besterPartner } from "@/lib/netzMatch";

/* Partnersuche für Mehr-Los-Vergaben (Feature I).
 *
 * Bis zum 2026-08-22 gab es hier NICHTS: die Oberfläche versprach Meldung, Treffer und
 * Kontaktfreigabe, aber `netzPartner` schrieb niemand, und die Meldung lebte in einem Set
 * im Browserspeicher. Dieser Endpunkt ist der Unterbau.
 *
 * ⚠ SICHTBARKEITSREGELN, die hier und nirgends sonst durchgesetzt werden:
 *   1. Wer sich selbst nicht gemeldet hat, erfährt nichts. Auch keine Anzahl.
 *   2. Partner ist nur, wer LOSE ABDECKT, DIE MAN SELBST NICHT ABDECKT. Zwei Firmen auf
 *      demselben Los sind Wettbewerber, keine Partner.
 *   3. Dieselbe Firmengruppe ist kein Partner (zwei Konten einer Firma).
 *   4. Name und Kontakt erst, wenn BEIDE Seiten freigegeben haben. Vorher nur Feld,
 *      Größenklasse und die Zahl der gedeckten Lose.
 */

type Zeile = {
  user_id: string; identity_id: string | null; lead_id: string;
  lose: number[]; freigabe: boolean; created_at: string;
};

const LEAD_RE = /^[0-9A-Za-z:._-]{1,80}$/;

/** Alles, was der Fragende über die Gegenseite erfahren darf. */
async function partnerSicht(meins: Zeile, andere: Zeile[]) {
  // Regeln 2 und 3 stecken in `besterPartner` — dort sind sie ohne Datenbank prüfbar.
  const treffer = besterPartner(meins, andere);
  if (!treffer) return null;
  const a = treffer.zeile as Zeile, ergaenzt = treffer.ergaenzt;

  const profile = await loadFirmaProfiles();
  const fp = (a.identity_id ? profile[a.identity_id] : null) as Record<string, unknown> | null;
  const gr = typeof fp?.group_size === "number" ? (fp.group_size as number) : 1;

  const beide = meins.freigabe && a.freigabe;          // Regel 4
  let name: string | null = null, kontakt: string | null = null;
  if (beide) {
    name = (fp?.name as string) || null;
    const sb = createAdminClient();
    const { data } = await sb.from("user_profiles").select("email").eq("id", a.user_id).single();
    kontakt = (data?.email as string) || null;
  }
  return {
    feld: (fp?.schwerpunkt as string) || null,
    groesse: gr > 1 ? `${gr} Einheiten` : "Einzelfirma",
    region: (fp?.hauptregion as string) || null,
    deckung: ergaenzt.length,
    lose: ergaenzt,
    seit: (a.created_at || "").slice(0, 10),
    freigabeGegenseite: a.freigabe,
    n: name, kontakt,
  };
}

async function sitzung() {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  return { sb, user };
}

async function zustand(userId: string, leadId: string, sb: Awaited<ReturnType<typeof createClient>>) {
  const { data: meins } = await sb.from("netz_interesse")
    .select("*").eq("user_id", userId).eq("lead_id", leadId).maybeSingle();
  // Regel 1: ohne eigene Meldung endet die Auskunft hier.
  if (!meins) return { interesse: null, partner: null };
  const admin = createAdminClient();
  const { data: andere } = await admin.from("netz_interesse").select("*").eq("lead_id", leadId);
  const partner = await partnerSicht(meins as Zeile, (andere || []) as Zeile[]);
  return { interesse: { lose: (meins as Zeile).lose || [], freigabe: (meins as Zeile).freigabe }, partner };
}

export async function GET(req: Request) {
  const leadId = new URL(req.url).searchParams.get("leadId") || "";
  if (!LEAD_RE.test(leadId)) return NextResponse.json({ error: "ungültige Lead-ID" }, { status: 400 });
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ interesse: null, partner: null });
  return NextResponse.json(await zustand(user.id, leadId, sb));
}

export async function POST(req: Request) {
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  const body = await req.json().catch(() => null) as
    { leadId?: string; lose?: number[]; freigabe?: boolean; identityId?: string } | null;
  if (!body || !LEAD_RE.test(body.leadId || "")) {
    return NextResponse.json({ error: "ungültige Anfrage" }, { status: 400 });
  }
  const satz: Record<string, unknown> = { user_id: user.id, lead_id: body.leadId };
  if (Array.isArray(body.lose)) {
    // Nur ganze, positive Losnummern, gedeckelt — der Wert kommt aus dem Browser.
    satz.lose = [...new Set(body.lose.filter((n) => Number.isInteger(n) && n > 0 && n < 1000))].slice(0, 200);
  }
  if (typeof body.freigabe === "boolean") satz.freigabe = body.freigabe;
  if (typeof body.identityId === "string") satz.identity_id = body.identityId.slice(0, 120);

  const { error } = await sb.from("netz_interesse").upsert(satz, { onConflict: "user_id,lead_id" });
  if (error) {
    // Solange 0013 nicht im Dashboard gelaufen ist, gibt es die Tabelle nicht. Ohne diesen
    // Zweig kommt eine rohe Postgres-Meldung heraus, und der Knopf tut scheinbar nichts.
    const fehlt = /relation .*netz_interesse.* does not exist|schema cache/i.test(error.message);
    return NextResponse.json(
      { error: fehlt ? "Die Partnersuche ist noch nicht freigeschaltet (Migration 0013 fehlt)." : error.message },
      { status: fehlt ? 503 : 500 });
  }
  return NextResponse.json(await zustand(user.id, body.leadId!, sb));
}

export async function DELETE(req: Request) {
  const leadId = new URL(req.url).searchParams.get("leadId") || "";
  const { sb, user } = await sitzung();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  if (!LEAD_RE.test(leadId)) return NextResponse.json({ error: "ungültige Lead-ID" }, { status: 400 });
  await sb.from("netz_interesse").delete().eq("user_id", user.id).eq("lead_id", leadId);
  return NextResponse.json({ interesse: null, partner: null });
}
