import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";
import { getTier } from "@/lib/tier";
import { redactStrategie } from "@/lib/redact";

// Strategie-Aggregate (Ticket #10). Vorberechnet via scripts/export_strategie.py,
// nicht live aus den Rohdaten — Ladezeit je Sektion < 800 ms (Akzeptanzkriterium #14).
//
// Härtung 4: im Bieter-Kontext (?ctx=provider) wird die Wettbewerbs-Intelligenz für Free
// server-seitig zur Teaser-Paywall redigiert (redactStrategie). Ohne ctx (Vergabeblick/Käufer)
// unverändert — die Käufer-Sicht hat eine eigene Orientierung.
export async function GET(req: Request) {
  const ctx = new URL(req.url).searchParams.get("ctx");
  try {
    const roh = await loadDataFile("strategie.json");
    if (!roh) return NextResponse.json({}, { status: 200 });
    const raw = JSON.parse(roh);
    if (ctx === "provider") {
      const tier = await getTier();
      return NextResponse.json(redactStrategie(raw, tier), { headers: { "cache-control": "no-store" } });
    }
    return NextResponse.json(raw, { headers: { "cache-control": "no-store" } });
  } catch {
    return NextResponse.json({}, { status: 200 });
  }
}
