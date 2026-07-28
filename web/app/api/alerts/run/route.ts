import { NextRequest, NextResponse } from "next/server";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { createAdminClient } from "@/lib/supabase/admin";
import { dueAlerts, sentFlagFor, alertText, type LeadTiming } from "@/lib/alerts";
import { send } from "@/lib/email";

/* Alert-Lauf (Ticket #9) — cron-getriggert (täglich). Rechnet fällige Frist-/Auslauf-Alerts
 * aus den Watchlists und verschickt sie (E-Mail-Stub bis Provider). Idempotent über die
 * *_sent-Flags. Absicherung: CRON_SECRET-Header, damit nur der Scheduler das aufruft. */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function loadLeadIndex(): Promise<Map<string, LeadTiming>> {
  const dir = path.join(process.cwd(), "data");
  const files = (await readdir(dir)).filter((f) => f.startsWith("leads-") && f.endsWith(".json"));
  const idx = new Map<string, LeadTiming>();
  for (const f of files) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const arr = JSON.parse(await readFile(path.join(dir, f), "utf-8")) as any[];
    for (const l of arr) idx.set(l.id, {
      id: l.id, titel: l.titel, src: l.src, tage: l.tage, endTage: l.endTage,
      endeEcht: l?.timing?.src === "echt",
    });
  }
  return idx;
}

async function run(req: NextRequest) {
  // Vercel-Cron schickt `Authorization: Bearer $CRON_SECRET`; manuell via `x-cron-secret`.
  const secret = process.env.CRON_SECRET;
  if (secret) {
    const ok = req.headers.get("x-cron-secret") === secret ||
      req.headers.get("authorization") === `Bearer ${secret}`;
    if (!ok) return NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 });
  }

  const admin = createAdminClient();
  const [{ data: watch }, { data: prefsRows }, { data: profiles }] = await Promise.all([
    admin.from("user_watchlist").select("*"),
    admin.from("user_alert_settings").select("*"),
    admin.from("user_profiles").select("id,email"),
  ]);
  const leadIdx = await loadLeadIndex();
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
