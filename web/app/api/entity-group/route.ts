import { NextRequest, NextResponse } from "next/server";
import { loadSuppliers } from "@/lib/suppliers";

/* Gruppen-Mitglieder einer Identität (Ticket #7: Gruppe = Identität). Der Onboarding-
 * Einheiten-Screen lädt sie erst, wenn eine Firma bestätigt wurde. */
export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id") || "";
  if (!id) return NextResponse.json({ members: [] });
  const all = await loadSuppliers();
  const s = all.find((x) => x.id === id);
  return NextResponse.json({ members: s?.members || [], name: s?.name || null });
}
