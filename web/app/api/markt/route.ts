import { NextResponse } from "next/server";
import { ladeMitGrund, DATEN_STOERUNG } from "@/lib/dataSource";
import { STOERUNG_ANTWORT } from "@/lib/ladegrund.js";
import { getTier } from "@/lib/tier";
import { redactMarkt } from "@/lib/redact";

// Marktblöcke je Grundraum (Chancen-Tab). Für Free werden die Premium-Werte (Bieterzahlen,
// Vergabestellen-Aufschlüsselungen) server-seitig redigiert.
const HEADERS = { "content-type": "application/json", "cache-control": "no-store" };

export async function GET() {
  const { text: raw, grund } = await ladeMitGrund("markt.json");
  // Ein leerer Marktblock heisst „zu diesem Grundraum wissen wir nichts". Bei unerreichbarem
  // Speicher waere das eine Behauptung ueber Daten, die wir gar nicht gelesen haben.
  if (grund === DATEN_STOERUNG) return NextResponse.json(STOERUNG_ANTWORT, { status: 503 });
  if (!raw) return NextResponse.json({});
  const tier = await getTier();
  if (tier === "pro") return new NextResponse(raw, { headers: HEADERS }); // kein Parse-Overhead
  try {
    return NextResponse.json(redactMarkt(JSON.parse(raw), tier));
  } catch {
    return new NextResponse(raw, { headers: HEADERS });
  }
}
