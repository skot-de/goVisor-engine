import { NextRequest, NextResponse } from "next/server";
import { bremse } from "@/lib/rateLimit";
import { createClient } from "@/lib/supabase/server";
import { herkunftHost, istBot, pruefe, schreibe, type Ereignis } from "@/lib/telemetrieSenke";

/**
 * Aufnahme der Browser-Ereignisse (Klicks, Verweildauer, Scrolltiefe) → `gov_ereignisse`.
 *
 * ⚠ DIE NUTZERKENNUNG KOMMT VOM SERVER, NIE AUS DEM KOERPER DER ANFRAGE. Wuerde der Client
 *   `nutzer_id` mitschicken duerfen, koennte jeder Ereignisse auf fremde Konten schreiben —
 *   und eine Telemetrie, der man fremde Zeilen unterschieben kann, ist als Grundlage fuer
 *   Produktentscheidungen wertlos. Dasselbe gilt fuer `ist_bot` und `herkunft`: beides wird
 *   hier aus den Kopfzeilen abgeleitet und ein mitgeschickter Wert verworfen.
 *
 * ⚠ ANTWORTET IMMER 204, auch wenn nichts geschrieben wurde. Der Browser soll aus einer
 *   fehlgeschlagenen Messung nichts ableiten und erst recht nicht erneut senden — und ein
 *   Fehlercode in der Netzwerkansicht wuerde bei jeder Fehlersuche ablenken. Was wirklich
 *   schiefging, steht im Serverprotokoll (s. `schreibe`).
 */

/* Grosszuegig, aber begrenzt: Klickkarten erzeugen viele Ereignisse, deshalb buendelt der
 * Client (s. web/lib/telemetrie.ts). 60 Buendel je Minute reichen fuer normales Verhalten
 * und deckeln eine Flut. */
const PRO_MINUTE = 60;
const MAX_JE_BUENDEL = 50;

export async function POST(req: NextRequest) {
  const zuViel = bremse(req, "ereignis-min", PRO_MINUTE, 60_000);
  if (zuViel) return zuViel;

  let roh: unknown;
  try {
    roh = await req.json();
  } catch {
    return new NextResponse(null, { status: 204 });
  }

  const liste = Array.isArray(roh) ? roh : [roh];
  if (!liste.length) return new NextResponse(null, { status: 204 });

  // Wer ist das? Aus der Sitzung, nicht aus der Anfrage. Fehlt sie, ist es anonymer
  // Verkehr — und genau der ist vor dem Start der interessante Teil.
  let nutzer_id: string | null = null;
  let org_id: string | null = null;
  try {
    const sb = await createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (user) {
      nutzer_id = user.id;
      const { data } = await sb.from("user_profiles").select("org_id").eq("id", user.id).maybeSingle();
      org_id = (data?.org_id as string | undefined) ?? null;
    }
  } catch {
    /* fail-open: ohne Anmeldung wird eben anonym gezaehlt */
  }

  const kopf = req.headers;
  const zusatz: Partial<Ereignis> = {
    nutzer_id,
    org_id,
    ist_bot: istBot(kopf.get("user-agent")),
    herkunft: herkunftHost(kopf.get("referer"), kopf.get("host")),
  };

  const sauber = liste
    .slice(0, MAX_JE_BUENDEL)
    .map((e) => pruefe(e, zusatz))
    .filter((e): e is Ereignis => e !== null);

  await schreibe(sauber);
  return new NextResponse(null, { status: 204 });
}

/** Nur POST. Ein GET waere eine Einladung, Ereignisse per Link zu erzeugen. */
export async function GET() {
  return new NextResponse(null, { status: 405, headers: { allow: "POST" } });
}
