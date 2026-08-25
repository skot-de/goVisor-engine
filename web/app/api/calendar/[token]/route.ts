import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";
import { createAdminClient } from "@/lib/supabase/admin";
import { bremse } from "@/lib/rateLimit";
// ⚠ Maskieren und Falten liegen in Plain JS, damit `node` sie laden und
// `web/scripts/pruefe-ical-faltung.mjs` die ECHTE Fassung pruefen kann.
import { esc, falte } from "@/lib/ical";

// iCal-Feed der beobachteten Leads (Ticket #16 §7). Der Token ist der geheime Schlüssel;
// die Route löst ihn server-seitig (Service-Role) zu user_watchlist auf und emittiert die
// Angebotsfristen als VEVENTs. Kein Termin wird erfunden — nur veröffentlichte Fristen.
// Der Feed liest LIVE aus der Watchlist; die Fristen kommen aus den exportierten Leads.

// `ohne` gehört in den Kalender-Feed: eine Abgabefrist ist eine Frist, unabhängig davon,
// ob die Quelle einen CPV-Code mitliefert.
const BRANCHEN = ["it", "bau", "medizin", "beratung", "sicherheit", "energie", "ohne"];

function icsDate(dmy: string): string | null {
  const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(dmy);
  return m ? `${m[3]}${m[2]}${m[1]}` : null; // YYYYMMDD
}
export async function GET(req: Request, { params }: { params: Promise<{ token: string }> }) {
  // ⚠ DIESE ROUTE STEHT OFFEN — sie muss, weil Outlook und Google keinen Sitzungscookie
  // schicken (s. `OFFEN` in middleware.ts). Damit ist der Token das einzige Geheimnis, und
  // ein offener Endpunkt, der Tokens prueft, laedt zum Durchprobieren ein. Die Bremse macht
  // das Raten unwirtschaftlich; grosszuegig genug, dass ein Kalenderprogramm nie ansteht —
  // die holen im Minuten- bis Stundentakt, nicht 30-mal je Minute.
  const zuViel = bremse(req, "ical", 30, 60_000);
  if (zuViel) return zuViel;

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
  const alleGemerkt = [...want];          // `want` wird unten geleert, die Liste bleibt
  // ⚠ DTSTAMP IST PFLICHT (RFC 5545, 3.6.1). Es fehlte; strenge Clients weisen einen Feed
  // ohne diese Eigenschaft zurueck, andere zeigen ihn — der Ausfall waere also nur bei
  // manchen Nutzern sichtbar und entsprechend schwer zu finden.
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const events: string[] = [];
  for (const b of BRANCHEN) {
    if (!want.size) break;
    let arr: Array<{ id: string; titel?: string; buyer?: string; frist?: { date?: string | null; src?: string } | null }>;
    try {
      // ⚠ Über den Daten-Loader, nicht von der Platte: auf einem Deployment liegt
      // web/data im Objektspeicher (DATA_BASE_URL). Direkt gelesen bliebe der
      // Kalender-Feed still leer — abonniert, aber ohne einen einzigen Termin.
      const roh = await loadDataFile(`leads-${b}.json`);
      if (!roh) continue;
      arr = JSON.parse(roh);
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
        `DTSTAMP:${stamp}`,
        `DTSTART;VALUE=DATE:${d}`,
        `SUMMARY:Angebotsfrist${est ? " (voraussichtlich)" : ""}: ${esc(l.titel || "Ausschreibung")}`,
        `DESCRIPTION:${esc(`${l.buyer || ""} — Angebotsfrist über goVisor`)}`,
        "END:VEVENT",
      ].map(falte).join("\r\n"));
    }
  }

  /* ⚠ DIE TERMINE, DIE IN KEINER BEKANNTMACHUNG STEHEN. Bis zum 2026-08-25 trug dieser
   * Feed genau einen Termin je Lead: die Angebotsfrist. Aus den Vergabeunterlagen kommen
   * die dazu, die dort NICHT stehen und trotzdem ueber Erfolg oder Ausschluss entscheiden —
   * vor allem das **Ende der Bindefrist** und der **letzte Tag fuer Bieterfragen**, der VOR
   * der Angebotsfrist liegt. Erzeugt von `scripts/export_kalender.py`.
   *
   * Die Angebotsfrist aus der Bekanntmachung steht oben schon; hier kommt sie nur dann noch
   * einmal, wenn die Unterlagen ein ABWEICHENDES Datum nennen — dann als Warnung, nicht als
   * zweiter Termin. Welche gilt, kann nur die Vergabestelle sagen. */
  for (const id of alleGemerkt) {
    const sicher = id.replace(/[^A-Za-z0-9_-]/g, "");
    if (!sicher) continue;
    let eintrag: { titel?: string; termine?: Array<{
      art: string; datum: string; label: string; quelle: string;
      beleg?: string | null; konflikt?: boolean; abweichung_tage?: number }> } | null = null;
    try {
      const roh = await loadDataFile(`kalender/${sicher}.json`);
      if (roh) eintrag = JSON.parse(roh);
    } catch { continue; }   // kein Kalender fuer diesen Lead ist kein Fehler
    for (const t of eintrag?.termine ?? []) {
      if (t.quelle !== "unterlagen") continue;
      if (t.art === "angebotsfrist" && !t.konflikt) continue;   // steht oben schon
      const d = t.datum?.replace(/-/g, "");
      if (!d || d.length !== 8) continue;
      const warnung = t.art === "angebotsfrist"
        ? `⚠ Abweichende Angebotsfrist laut Unterlagen (${(t.abweichung_tage ?? 0) > 0 ? "+" : ""}${t.abweichung_tage ?? 0} Tage): `
        : "";
      events.push([
        "BEGIN:VEVENT",
        `UID:govisor-${sicher}-${t.art}-${d}@govisor.eu`,
        `DTSTAMP:${stamp}`,
        `DTSTART;VALUE=DATE:${d}`,
        `SUMMARY:${esc(`${warnung}${t.label}: ${eintrag?.titel || "Ausschreibung"}`)}`,
        `DESCRIPTION:${esc(t.beleg || `${t.label} laut Vergabeunterlagen — über goVisor`)}`,
        "END:VEVENT",
      ].map(falte).join("\r\n"));
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
