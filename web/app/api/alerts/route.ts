import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { dueAlerts, type AlertPrefs } from "@/lib/alerts";
import { leadFristen } from "@/lib/leadIndex";

/* Posteingang: die Hinweise zu den beobachteten Leads, in der App statt per Mail.
 *
 * WARUM ES DEN GIBT. Die Alarm-Logik stand seit Monaten, zugestellt wurde nie etwas:
 * `lib/email.ts` ist ein Stub, einen Posteingang gab es nicht. Die Startseite versprach
 * trotzdem „Meldung, sobald etwas Passendes erscheint".
 *
 * ⚠ RECHNET BEIM ABRUF, NICHT IM CRON. Ein Posteingang, der auf einen nächtlichen Lauf
 * wartet, ist beim ersten Besuch leer und wirkt kaputt. Die Berechnung ist billig (eine
 * Watchlist gegen eine Map), also läuft sie hier.
 *
 * ⚠ FASST DIE `*_sent`-FLAGS NICHT AN. Die gehören dem E-Mail-Lauf; wer sie hier setzt,
 * verbraucht Hinweise, die per Mail nie jemanden erreicht haben. Deshalb rechnet der
 * Posteingang mit neutralen Flags („was ist JETZT fällig") und entdoppelt über den
 * Unique-Index der Tabelle.
 */

const NEUTRAL = { deadline_14d_sent: false, deadline_3d_sent: false, expiry_warn_sent: false };
const STANDARD: AlertPrefs = { deadline_warning_enabled: true, expiry_warning_enabled: false };

export async function GET() {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ alerts: [], ungelesen: 0 });

  const [{ data: watch }, { data: prefs }] = await Promise.all([
    sb.from("user_watchlist").select("lead_id").eq("user_id", user.id),
    sb.from("user_alert_settings").select("*").eq("user_id", user.id).maybeSingle(),
  ]);

  if (watch?.length) {
    const fristen = await leadFristen();
    const neu: Record<string, unknown>[] = [];
    for (const w of watch) {
      const lead = fristen.get(w.lead_id as string);
      if (!lead) continue;
      for (const a of dueAlerts(lead, NEUTRAL, (prefs as AlertPrefs | null) || STANDARD)) {
        neu.push({ user_id: user.id, lead_id: a.leadId, typ: a.type, titel: a.titel, tage: a.days });
      }
    }
    // `ignoreDuplicates`: ein bereits gelesener Hinweis darf nicht wieder auf ungelesen
    // springen, nur weil die Frist noch läuft.
    if (neu.length) await sb.from("user_alerts").upsert(neu, {
      onConflict: "user_id,lead_id,typ", ignoreDuplicates: true,
    });
  }

  const { data, error } = await sb.from("user_alerts")
    .select("id,lead_id,typ,titel,tage,created_at,gesehen_am")
    .eq("user_id", user.id).order("created_at", { ascending: false }).limit(50);
  if (error) {
    // Solange 0014 nicht gelaufen ist, gibt es die Tabelle nicht. Lesbar sagen statt
    // eine rohe Postgres-Zeile durchzureichen oder still leer zu tun.
    const fehlt = /relation .*user_alerts.* does not exist|schema cache/i.test(error.message);
    return NextResponse.json(
      { alerts: [], ungelesen: 0,
        error: fehlt ? "Der Posteingang ist noch nicht freigeschaltet (Migration 0014 fehlt)." : error.message },
      { status: fehlt ? 503 : 500 });
  }
  return NextResponse.json({
    alerts: data || [],
    ungelesen: (data || []).filter((a) => !a.gesehen_am).length,
  });
}

/** Als gelesen markieren: einzelne IDs oder alles. */
export async function POST(req: Request) {
  const sb = await createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  const body = await req.json().catch(() => null) as { ids?: string[]; alle?: boolean } | null;
  const jetzt = new Date().toISOString();
  let q = sb.from("user_alerts").update({ gesehen_am: jetzt }).eq("user_id", user.id).is("gesehen_am", null);
  if (!body?.alle) {
    const ids = (body?.ids || []).filter((i) => typeof i === "string").slice(0, 100);
    if (!ids.length) return NextResponse.json({ ok: true, markiert: 0 });
    q = q.in("id", ids);
  }
  const { error } = await q;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
