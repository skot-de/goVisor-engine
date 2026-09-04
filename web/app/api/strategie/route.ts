import { NextResponse } from "next/server";
import { ladeMitGrund, DATEN_STOERUNG } from "@/lib/dataSource";
import { STOERUNG_ANTWORT } from "@/lib/ladegrund.js";
import { getTier } from "@/lib/tier";
import { redactStrategie } from "@/lib/redact";

// Strategie-Aggregate (Ticket #10). Vorberechnet via scripts/export_strategie.py,
// nicht live aus den Rohdaten — Ladezeit je Sektion < 800 ms (Akzeptanzkriterium #14).
//
// Härtung 4: im Bieter-Kontext (?ctx=provider) wird die Wettbewerbs-Intelligenz für Free
// server-seitig zur Teaser-Paywall redigiert (redactStrategie). Ohne ctx (Vergabeblick/Käufer)
// unverändert — die Käufer-Sicht hat eine eigene Orientierung.
// LAND. Die Datei ist seit 2026-08-23 nach Land verschluesselt ({DE:{…},AT:{…},CH:{…}});
// diese Route reicht genau EINEN Satz heraus, damit die Form fuer das Frontend unveraendert
// bleibt und die Nutzlast nicht auf das Dreifache waechst.
//
// Warum ueberhaupt: bis dahin war der ganze Bereich deutsch. Ein oesterreichischer Bieter
// sah deutsche Vergabestellen und deutsche Wettbewerbsdichte, ausgegeben als seine. Eine
// DACH-Summe waere keine Loesung gewesen, sondern dieselbe Verwechslung mit mehr Zahlen:
// „wer vergibt in meinem Feld" ist eine Frage an EINEN Markt.
// ⚠ MUSS zu scripts/export_strategie.py:LAENDER passen. Stand 2026-09-03 baute der
// Export LU und diese Menge wies ?land=LU ab — die Daten lagen da, die Tuer war zu.
const LAENDER = new Set(["DE", "AT", "CH", "LU"]);

export async function GET(req: Request) {
  const p = new URL(req.url).searchParams;
  const ctx = p.get("ctx");
  // Freitext aus der Anfrage NIE ungeprueft als Schluessel verwenden.
  const gewuenscht = (p.get("land") || "").toUpperCase();
  const land = LAENDER.has(gewuenscht) ? gewuenscht : "DE";
  try {
    const { text: roh, grund } = await ladeMitGrund("strategie.json");
    // Das ausdrueckliche `status: 200` stand hier fuer „es gibt keine Aggregate". Bei einer
    // Speicherstoerung ist das keine Auskunft, sondern ein Ausfall in ihrer Verkleidung.
    if (grund === DATEN_STOERUNG) return NextResponse.json(STOERUNG_ANTWORT, { status: 503 });
    if (!roh) return NextResponse.json({}, { status: 200 });
    const datei = JSON.parse(roh);
    // Rueckfall auf die alte, flache Form: waehrend eines Deployments kann eine Datei
    // liegen, die vor der Umstellung gebaut wurde. Ohne diesen Zweig waere der ganze
    // Bereich fuer die Dauer des Uebergangs leer — und leer sieht aus wie „keine Daten".
    const flach = !datei.DE && !datei.AT && !datei.CH;
    const raw = flach ? datei : (datei[land] ?? datei.DE ?? {});
    if (ctx === "provider") {
      const tier = await getTier();
      return NextResponse.json(redactStrategie(raw, tier), { headers: { "cache-control": "no-store" } });
    }
    return NextResponse.json(raw, { headers: { "cache-control": "no-store" } });
  } catch {
    return NextResponse.json({}, { status: 200 });
  }
}
