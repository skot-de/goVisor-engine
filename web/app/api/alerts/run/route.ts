import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { dueAlerts, sentFlagFor, alertText } from "@/lib/alerts";
import { leadFristen } from "@/lib/leadIndex";
import { send, mailAktiv } from "@/lib/email";
import { requireCronSecret } from "@/lib/cronAuth";

/* Alert-Lauf (Ticket #9) — cron-getriggert (täglich). Rechnet fällige Frist-/Auslauf-Alerts
 * aus den Watchlists und verschickt sie (E-Mail-Stub bis Provider). Idempotent über die
 * *_sent-Flags. Absicherung: CRON_SECRET-Header, damit nur der Scheduler das aufruft. */

async function run(req: NextRequest) {
  // Fail-closed: ohne CRON_SECRET deaktiviert, sonst nur mit passendem Header (Vercel-Cron/manuell).
  const deny = requireCronSecret(req);
  if (deny) return deny;

  // ⚠ OHNE PROVIDER NICHT „ZUSTELLEN". `send()` meldet auch als Stub Erfolg; der Lauf setzte
  // danach die `*_sent`-Flags, und `dueAlerts` liefert den Hinweis nie wieder. Jeder Lauf
  // hätte also Hinweise VERBRAUCHT, die niemand bekommen hat. Der Posteingang in der App
  // (`/api/alerts`) ist davon unabhängig und rechnet mit neutralen Flags.
  if (!mailAktiv) {
    return NextResponse.json({ ok: true, uebersprungen: true,
      grund: "kein EMAIL_API_KEY — es wird nichts als zugestellt markiert" });
  }

  const admin = createAdminClient();
  const [{ data: watch }, { data: prefsRows }, { data: profiles }] = await Promise.all([
    admin.from("user_watchlist").select("*"),
    admin.from("user_alert_settings").select("*"),
    admin.from("user_profiles").select("id,email"),
  ]);
  const leadIdx = await leadFristen();
  const prefsBy = new Map((prefsRows || []).map((p) => [p.user_id, p]));
  const emailBy = new Map((profiles || []).map((p) => [p.id, p.email]));
  const DEFAULT_PREFS = { deadline_warning_enabled: true, expiry_warning_enabled: false };

  // Fällige Alerts je Nutzer sammeln
  const byUser = new Map<string, { alerts: ReturnType<typeof dueAlerts>; flagUpdates: { id: string; flag: string }[] }>();
  for (const w of watch || []) {
    const lead = leadIdx.get(w.lead_id);
    if (!lead) continue;
    const prefs = prefsBy.get(w.user_id) || DEFAULT_PREFS;
    const due = dueAlerts(lead, w, prefs);
    if (!due.length) continue;
    const bucket = byUser.get(w.user_id) || { alerts: [], flagUpdates: [] };
    bucket.alerts.push(...due);
    for (const a of due) bucket.flagUpdates.push({ id: w.id, flag: sentFlagFor(a.type) });
    byUser.set(w.user_id, bucket);
  }

  let sent = 0;
  for (const [userId, bucket] of byUser) {
    const to = emailBy.get(userId);
    if (!to) continue;
    const lines = bucket.alerts.map((a) => alertText(a).zeile);
    await send({ to, subject: `goVisor: ${bucket.alerts.length} neue Hinweis(e) zu euren Leads`,
      text: ["Neue Hinweise zu euren beobachteten Ausschreibungen:", "", ...lines].join("\n") });
    sent += bucket.alerts.length;
    // *_sent-Flags setzen (dedupliziert weitere Sends)
    for (const u of bucket.flagUpdates) await admin.from("user_watchlist").update({ [u.flag]: true }).eq("id", u.id);
  }

  return NextResponse.json({ ok: true, users: byUser.size, alerts_sent: sent });
}

export const GET = run;    // Vercel-Cron (GET)
export const POST = run;   // manueller/abgesicherter Trigger
