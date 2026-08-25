import { NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { loadSupplier } from "@/lib/suppliers";

/* INTERN — Prüfung der Identitäts-Ansprüche.
 *
 * Braucht den Secret-Key: die RLS auf `identity_claims` lässt den Nutzer nur einfügen und
 * lesen, nie den Status setzen — sonst schaltet man sich selbst frei. Deshalb läuft die
 * Entscheidung ausschließlich hier.
 *
 * Wie das Firmen-Radar in Production hart blockiert, außer INTERN_ENABLED=1: die Liste
 * enthält Klarnamen, Domains und Freitexte fremder Unternehmen.
 */
export const runtime = "nodejs";

const OFFEN = "unbestaetigt";

function gesperrt() {
  return process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1";
}

export async function GET() {
  if (gesperrt()) return NextResponse.json({ error: "not found" }, { status: 404 });

  const sb = createAdminClient();
  const { data, error } = await sb.from("identity_claims")
    .select("id, user_id, identity_id, company_name, email_domain, status, grund, nachricht, created_at, bearbeitet_am, bearbeitet_von")
    .order("created_at", { ascending: false }).limit(200);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  // Die Firmen-Fakten dazulegen: ohne sie ist „stimmt der Anspruch?" nicht entscheidbar.
  // Die bekannte Domain gehört hier ausdrücklich hin — das ist das Prüfmerkmal.
  // ⚠ Hoechstens 200 Anspruechen stehen hoechstens 200 Firmen gegenueber — dafuer alle
  // 37.901 zu laden, war das rund Zweihundertfache. Doppelte Kennungen werden nur einmal
  // geholt; der Speicher haelt sie ohnehin fest.
  const ids = [...new Set((data ?? []).map((c) => c.identity_id).filter(Boolean))];
  const idx = new Map((await Promise.all(ids.map(async (i) => [i, await loadSupplier(String(i))] as const)))
    .filter(([, s]) => s));
  const rows = (data ?? []).map((c) => {
    const s = idx.get(c.identity_id);
    return {
      ...c,
      firma: s ? {
        name: s.name, wins: s.wins, buyers: s.buyers, seit: s.seit,
        bekannteDomain: s.domain ?? null, domainBelege: s.domainBelege ?? 0,
        adressenBekannt: s.mailHashes?.length ?? 0,
        topBuyers: s.topBuyers ?? [],
      } : null,
      // Sofort sichtbar machen, was maschinell schon dagegen spricht.
      domainPasst: !!(s?.domain && c.email_domain && s.domain === c.email_domain),
    };
  });
  return NextResponse.json({ claims: rows, offen: rows.filter((r) => r.status === OFFEN).length });
}

export async function POST(req: Request) {
  if (gesperrt()) return NextResponse.json({ error: "not found" }, { status: 404 });

  let body: { id?: string; status?: string; von?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }

  const id = String(body.id ?? "");
  const status = String(body.status ?? "");
  if (!id || !["geprueft", "abgelehnt"].includes(status)) {
    return NextResponse.json({ error: "id und status (geprueft|abgelehnt) nötig" }, { status: 400 });
  }

  const sb = createAdminClient();
  const { error } = await sb.from("identity_claims").update({
    status,
    bearbeitet_am: new Date().toISOString(),
    bearbeitet_von: String(body.von ?? "intern").slice(0, 60),
  }).eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  // Freigabe wirkt erst, wenn sie auch im Profil steht — dort liest die Sperre.
  // Wert-Vokabular ist das der Spalte (`confirmed|probable|none`, CHECK-Constraint),
  // nicht das der Engine — sonst schlägt das Update fehl.
  if (status === "geprueft") {
    const { data: c } = await sb.from("identity_claims").select("user_id").eq("id", id).single();
    if (c?.user_id) {
      const { error: pe } = await sb.from("user_profiles")
        .update({ entity_confidence: "confirmed" }).eq("id", c.user_id);
      // Nicht schlucken: eine Freigabe, die im Profil nicht ankommt, ist keine Freigabe —
      // die Sperre liest dort, nicht in identity_claims.
      if (pe) return NextResponse.json({ error: `Freigabe nicht übernommen: ${pe.message}` }, { status: 500 });
    }
  }
  return NextResponse.json({ ok: true });
}
