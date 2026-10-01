import { NextRequest, NextResponse } from "next/server";
import { loadSupplier } from "@/lib/suppliers";
import { ladeOeffentlich } from "@/lib/oeffentlich";
import { bremse } from "@/lib/rateLimit";

/**
 * Schnellcheck §7 „Kann ich das gewinnen?" — das öffentliche Teil-Ergebnis OHNE Konto.
 *
 * Eingabe: slug der Ausschreibung + id der (per /api/entity-search bestätigten) Firma.
 * Ausgabe: ein Passungs-BAND und die Anzahl EIGENER vergleichbarer Zuschläge (§7.1.3).
 *
 * ⚠ KEINE Aussage über benannte Dritte, kein Verdrängbarkeits-Wert, keine volle Analyse.
 *   Das Band ist bewusst grob: die genaue Passung (und alles über den Wettbewerb) gibt es
 *   erst im Portal. So verschenken wir die Exklusivschicht nicht an einen offenen Endpunkt.
 *
 * ⚠ Öffentlich (vor dem Anmelde-Tor, muss in der OFFEN-Liste der middleware stehen) — darum
 *   dieselbe Bremse wie /api/entity-search: ohne sie holt eine Schleife den Bestand ab.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PRO_MINUTE = 30, PRO_STUNDE = 300;
const ID_RE = /^(grp|solo):[0-9A-Za-zäöüÄÖÜß:._/-]{1,120}$/;

export async function GET(req: NextRequest) {
  const zuViel = bremse(req, "schnellcheck-min", PRO_MINUTE, 60_000)
              ?? bremse(req, "schnellcheck-std", PRO_STUNDE, 3_600_000);
  if (zuViel) return zuViel;

  const slug = (req.nextUrl.searchParams.get("slug") || "").trim();
  const id = (req.nextUrl.searchParams.get("id") || "").trim();
  if (!slug || !ID_RE.test(id)) return NextResponse.json({ error: "Parameter fehlen" }, { status: 400 });

  const seite = await ladeOeffentlich(slug);
  if (!seite) return NextResponse.json({ error: "unbekannt" }, { status: 404 });

  const firma = await loadSupplier(id);
  if (!firma) return NextResponse.json({ error: "Firma unbekannt" }, { status: 404 });

  // Vergleichbare eigene Zuschläge: dieselbe CPV-Abteilung (die ersten beiden Stellen) wie
  // diese Ausschreibung. `fields` trägt Zuschläge je CPV-4-Feld.
  const abt = (seite.cpv || "").slice(0, 2);
  const vergleichbare = abt
    ? (firma.fields || [])
        .filter((f) => String(f.cpv4 || "").slice(0, 2) === abt)
        .reduce((s, f) => s + (f.wins || 0), 0)
    : 0;

  // Region passt, wenn die Firma bundesweit tätig ist oder die Region der Ausschreibung kennt.
  const regionPasst = firma.regionTyp === "bundesweit"
    || (!!seite.region && (firma.regions || []).some((r) => r && seite.region && r.includes(seite.region!)));

  let band: "hoch" | "mittel" | "niedrig";
  if (vergleichbare >= 3 && regionPasst) band = "hoch";
  else if (vergleichbare >= 1) band = "mittel";
  else band = "niedrig";

  return NextResponse.json(
    { band, vergleichbare, regionPasst, firma: firma.name },
    { headers: { "cache-control": "no-store" } },
  );
}
