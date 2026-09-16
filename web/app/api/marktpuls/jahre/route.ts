import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";

/**
 * Marktpuls — die beiden Jahres-Schichten (`jahre`, `bieter`), getrennt ausgeliefert.
 *
 * **Warum eine zweite Route.** Bis Stand 3 lagen beide Schichten in `marktpuls.json`. Sie
 * trugen dort über die Hälfte der Datei und wuchsen mit **jedem Kalenderjahr** um rund
 * 300 Byte weiter — das 50-KB-Budget aus Briefing §5 war damit strukturell erreicht, nicht
 * aus Nachlässigkeit. Gemessen am 2026-09-16: 52,0 KB, davon 27,6 KB Jahres-Schichten.
 *
 * Gebraucht werden sie nur, wenn jemand die Jahresansicht öffnet; die Startansicht ist die
 * Saison. Seit Stand 4 liegt die Hauptdatei bei ~23 KB und wächst nur noch mit den Daten,
 * nicht mit der Zeit.
 *
 * Wie die Hauptroute: statische, aggregierte Datei, keine Einzelverfahren, kein Paywall-Gate.
 * `erzeugt`/`stand` stehen auch hier drin — ein Lauf schreibt beide Dateien mit denselben
 * Stempeln, damit die Anzeige nie zwei Stände unter einer Überschrift zeigt.
 */
export const revalidate = 3600;

export async function GET() {
  const raw = await loadDataFile("marktpuls-jahre.json");
  if (!raw) {
    // ⚠ 503, NICHT 404. Die Datei fehlt nicht, weil es sie nicht gibt, sondern weil der
    // nächtliche Lauf sie (noch) nicht geschrieben hat. Die Anzeige blendet den Umschalter
    // dann aus und zeigt die Saison weiter — ein Teilausfall darf die Seite nicht kosten.
    return NextResponse.json(
      { fehler: "marktpuls-jahre.json nicht verfügbar" },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
  return new NextResponse(raw, {
    headers: {
      "content-type": "application/json",
      "cache-control": "public, max-age=3600, stale-while-revalidate=86400",
    },
  });
}
