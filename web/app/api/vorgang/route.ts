import { NextResponse } from "next/server";
import { loadVorgang, vorgangZuLead, vorgangBestand } from "@/lib/vorgangsakte";

/* Eine Vorgangsakte: Ausschreibung, Korrekturen, Unterlagen und Zuschlag unter einer Nummer.
 *
 * Zwei Zugaenge, weil es zwei Wege gibt, hier zu landen: ueber die Vorgangsnummer selbst
 * (Verlinkung aus einer Kette) und ueber eine Bekanntmachung (Klick aus der Trefferliste,
 * wo der Nutzer nur die Vergabenummer in der Hand hat). */
export const runtime = "nodejs";

// `folder:<uuid>` und `pub:<nummer>` — mehr Formen erzeugt build_vorgaenge.py nicht.
const ID_RE = /^(folder|pub):[0-9A-Za-z:._-]{1,120}$/;
const LEAD_RE = /^[0-9A-Za-z._-]{1,64}$/;
const LAND_RE = /^[A-Z]{2}$/;

export async function GET(req: Request) {
  const q = new URL(req.url).searchParams;
  const lead = q.get("lead") || "";
  let id = q.get("id") || "";
  // ⚠ DAS LAND IST TEIL DES SCHLUESSELS, nicht Beiwerk: 48 Vorgangsnummern kommen in mehr
  // als einem Land vor. `DE` als Vorgabe ist eine Bequemlichkeit fuer getippte Links, keine
  // Annahme ueber den Geltungsbereich — exportiert werden AT, CH, DE und EU.
  let land = (q.get("land") || "DE").toUpperCase();

  if (!id && lead) {
    if (!LEAD_RE.test(lead)) {
      return NextResponse.json({ error: "ungültige Bekanntmachungs-ID" }, { status: 400 });
    }
    const treffer = await vorgangZuLead(lead);
    if (!treffer) {
      // ⚠ NICHT 404. Ein Lead ohne Akte ist der Normalfall ausserhalb der exportierten
      // Menge, kein Fehler. Die Anzeige soll den Verweis weglassen, nicht eine Stoerung
      // melden — deshalb 200 mit einem ausdruecklichen `vorhanden: false`.
      return NextResponse.json({ vorhanden: false, grund: "nicht exportiert" });
    }
    id = treffer.id;
    land = treffer.land;
  }

  if (!ID_RE.test(id) || !LAND_RE.test(land)) {
    return NextResponse.json({ error: "ungültige Vorgangsnummer" }, { status: 400 });
  }

  const akte = await loadVorgang(land, id);
  if (akte) return NextResponse.json({ vorhanden: true, akte });

  // Dieselbe Trennung wie in /api/firma: „gibt es nicht" ist etwas anderes als „ist nicht
  // geladen". Ohne sie sieht ein fehlender Datenspeicher aus wie ein leeres Ergebnis.
  const bestand = await vorgangBestand();
  return NextResponse.json(
    bestand
      ? { vorhanden: false, id, land, grund: "nicht in der exportierten Menge" }
      : { error: "Vorgangsakten nicht geladen — DATA_BASE_URL prüfen "
                 + "(docs/web-data-storage.md)" },
    { status: bestand ? 404 : 503 });
}
