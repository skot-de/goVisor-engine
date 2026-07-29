import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";
import { getTier } from "@/lib/tier";
import { redactMarkt } from "@/lib/redact";

// Marktblöcke je Grundraum (Chancen-Tab). Für Free werden die Premium-Werte (Bieterzahlen,
// Vergabestellen-Aufschlüsselungen) server-seitig redigiert.
const HEADERS = { "content-type": "application/json", "cache-control": "no-store" };

export async function GET() {
  const raw = await loadDataFile("markt.json");
  if (!raw) return NextResponse.json({});
  const tier = await getTier();
  if (tier === "pro") return new NextResponse(raw, { headers: HEADERS }); // kein Parse-Overhead
  try {
    return NextResponse.json(redactMarkt(JSON.parse(raw), tier));
  } catch {
    return new NextResponse(raw, { headers: HEADERS });
  }
}
