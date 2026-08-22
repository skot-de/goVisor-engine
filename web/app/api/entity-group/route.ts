import { NextRequest, NextResponse } from "next/server";
import { loadSuppliers } from "@/lib/suppliers";
import { bremse } from "@/lib/rateLimit";

/* Gruppen-Mitglieder einer Identität (Ticket #7: Gruppe = Identität). Der Onboarding-
 * Einheiten-Screen lädt sie erst, wenn eine Firma bestätigt wurde. */
export async function GET(req: NextRequest) {
  // Offen wie entity-search, also aus demselben Grund gebremst: über die Gruppen-IDs liesse
  // sich die Firmenstruktur genauso abklappern. Im Onboarding fällt hier EIN Aufruf an.
  const zuViel = bremse(req, "entitygroup", 60, 60_000);
  if (zuViel) return zuViel;
  const id = req.nextUrl.searchParams.get("id") || "";
  if (!id) return NextResponse.json({ members: [] });
  const all = await loadSuppliers();
  const s = all.find((x) => x.id === id);
  return NextResponse.json({ members: s?.members || [], name: s?.name || null });
}
