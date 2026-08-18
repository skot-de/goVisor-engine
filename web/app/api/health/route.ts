import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";

/**
 * Gesundheitsprobe für die Überwachung. Öffentlich, absichtlich karg.
 *
 * **Wofür.** Eine Betriebsautomatik (Azure Monitor, Uptime-Check, was auch immer) braucht
 * einen Punkt, der ohne Anmeldung sagt, ob die Anwendung ihre Daten findet. `/intern/lauf`
 * kann das nicht sein: die Seite steht hinter Admin-Anmeldung und liefert Zahlen, die
 * niemanden ausserhalb angehen.
 *
 * **Was hier NICHT hineingehört, und warum.** Keine Mengen, keine Dateinamen, keine
 * Fehlermeldungen aus dem Inneren. Eine Gesundheitsprobe wird von jedem abgefragt, der die
 * URL kennt; jede Zahl darin ist eine Auskunft an Unbekannte. „Wie viele Ausschreibungen
 * habt ihr" ist eine Geschäftszahl, kein Betriebszustand.
 *
 * **Warum trotzdem `alter`.** Die gefährlichste Störung dieser Anwendung ist nicht der
 * Ausfall, sondern der stille Stillstand: der Tageslauf bricht ab, das Frontend liefert
 * weiter Daten von vorgestern, und alles sieht gesund aus. Deshalb ist das Alter des
 * Datenstands die eine Zahl, die hier stehen muss — grob, in Stunden.
 *
 * Antwort: `{ status: "ok" | "veraltet" | "keine_daten", alter_stunden, gepruegt }`.
 * HTTP 200 bei ok/veraltet, 503 bei keine_daten — damit ein Uptime-Check auf den HTTP-Code
 * schauen kann und ein Dashboard trotzdem den Unterschied sieht.
 */
export const dynamic = "force-dynamic";

// Ab wann gilt der Stand als veraltet. Der Tageslauf läuft täglich; 30 Stunden lassen einen
// verpassten Lauf durchgehen, zwei nicht. Wer das enger zieht, bekommt Fehlalarme an jedem
// Tag, an dem der Lauf länger braucht.
const VERALTET_AB_STUNDEN = 30;

export async function GET() {
  let stand: string | null = null;
  try {
    const roh = await loadDataFile("regionen.json");
    if (roh) stand = (JSON.parse(roh) as { stand?: string }).stand ?? null;
  } catch { stand = null; }

  if (!stand) {
    return NextResponse.json(
      { status: "keine_daten", alter_stunden: null },
      { status: 503, headers: { "cache-control": "no-store" } });
  }

  // `stand` ist ein Datum ohne Uhrzeit (YYYY-MM-DD). Als Ende des Tages gerechnet, sonst
  // wäre ein Stand von heute früh schon zwölf Stunden alt und die Anzeige nervös.
  const alter = (Date.now() - (Date.parse(`${stand}T23:59:59Z`))) / 3_600_000;
  const stunden = Math.max(0, Math.round(alter));
  return NextResponse.json(
    { status: stunden > VERALTET_AB_STUNDEN ? "veraltet" : "ok", alter_stunden: stunden },
    { headers: { "cache-control": "no-store" } });
}
