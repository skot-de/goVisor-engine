import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { createAdminClient } from "@/lib/supabase/admin";

// iCal-Feed der beobachteten Leads (Ticket #16 §7). Der Token ist der geheime Schlüssel;
// die Route löst ihn server-seitig (Service-Role) zu user_watchlist auf und emittiert die
// Angebotsfristen als VEVENTs. Kein Termin wird erfunden — nur veröffentlichte Fristen.
// Der Feed liest LIVE aus der Watchlist; die Fristen kommen aus den exportierten Leads.

const BRANCHEN = ["it", "bau", "medizin", "beratung", "sicherheit", "energie"];

function icsDate(dmy: string): string | null {
  const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(dmy);
  return m ? `${m[3]}${m[2]}${m[1]}` : null; // YYYYMMDD
}
function esc(s: string): string {
  return String(s).replace(/([,;\\])/g, "\\$1").replace(/\r?\n/g, "\\n");
}

export async function GET(_req: Request, { params }: { params: Promise<{ token: string }> }) {
  const { token: raw } = await params;
  const token = raw.replace(/\.ics$/i, "");

  let leadIds: string[] = [];
  try {
    const admin = createAdminClient();
    const { data: feed } = await admin
      .from("user_calendar_feed").select("user_id").eq("feed_token", token).maybeSingle();
    if (!feed) return new NextResponse("Feed nicht gefunden", { status: 404 });
    const { data: wl } = await admin
      .from("user_watchlist").select("lead_id").eq("user_id", feed.user_id);
    leadIds = (wl ?? []).map((r: { lead_id: string }) => r.lead_id);
  } catch {
    return new NextResponse("Feed vorübergehend nicht verfügbar", { status: 503 });
  }

  const want = new Set(leadIds);
  const events: string[] = [];
  for (const b of BRANCHEN) {
    if (!want.size) break;
    let arr: Array<{ id: string; titel?: string; buyer?: string; frist?: { date?: string | null; src?: string } | null }>;
    try {
      arr = JSON.parse(await readFile(path.join(process.cwd(), "data", `leads-${b}.json`), "utf-8"));
    } catch { continue; }
    for (const l of arr) {
      if (!want.has(l.id) || !l.frist?.date) continue;
      const d = icsDate(l.frist.date);
      if (!d) continue;
      want.delete(l.id);
      const est = l.frist.src === "schaetz";
      events.push([
        "BEGIN:VEVENT",
        `UID:govisor-${l.id}@govisor.eu`,
        `DTSTART;VALUE=DATE:${d}`,
        `SUMMARY:Angebotsfrist${est ? " (voraussichtlich)" : ""}: ${esc(l.titel || "Ausschreibung")}`,
        `DESCRIPTION:${esc(`${l.buyer || ""} — Angebotsfrist über goVisor`)}`,
        "END:VEVENT",
      ].join("\r\n"));
    }
  }

  const ics = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//goVisor//Verfahrenskalender//DE",
    "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:goVisor Fristen",
    ...events, "END:VCALENDAR",
  ].join("\r\n");

  return new NextResponse(ics, {
    headers: { "content-type": "text/calendar; charset=utf-8", "cache-control": "no-store" },
  });
}
