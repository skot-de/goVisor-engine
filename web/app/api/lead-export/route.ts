import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";

/**
 * Rohdaten-Download je Vorgang: Leistungsverzeichnis bzw. Kriterienmatrix als CSV.
 *
 * Ausgeliefert wird UNSER Arbeitsergebnis — die aus GAEB/Preisblatt bzw. der UfAB-Matrix
 * extrahierte Tabelle (`scripts/export_doc_struktur.py`). Die Original-Unterlagen des
 * Portals geben wir bewusst NICHT weiter: sie ändern sich während der Angebotsfrist
 * (Bieterfragen, Berichtigungen), und eine veraltete Kopie, auf der jemand kalkuliert,
 * wäre ein Haftungsfall. Der Portal-Link steht im Teilnahme-Tab daneben.
 *
 * SICHERHEIT: `id` wird zum Dateinamen. Ohne strenge Prüfung wäre das ein Pfad-Traversal
 * (`?id=../../../.env`) — deshalb Positivliste statt Filterung, und das Verzeichnis kommt
 * aus einer festen Zuordnung, nie aus der Eingabe.
 */
const VERZEICHNIS: Record<string, { dir: string; label: string }> = {
  lv: { dir: "lv", label: "Leistungsverzeichnis" },
  kriterien: { dir: "kriterien", label: "Kriterien" },
};
const ID_OK = /^[A-Za-z0-9_-]{1,64}$/;

export async function GET(req: Request) {
  const u = new URL(req.url);
  const id = u.searchParams.get("id") || "";
  const art = VERZEICHNIS[u.searchParams.get("was") || ""];
  if (!art || !ID_OK.test(id)) {
    return NextResponse.json({ error: "id/was ungültig" }, { status: 400 });
  }
  const csv = await loadDataFile(`${art.dir}/${id}.csv`);
  if (!csv) {
    return NextResponse.json({ error: "keine Daten für diesen Vorgang" }, { status: 404 });
  }
  return new NextResponse(csv, {
    headers: {
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": `attachment; filename="goVisor-${art.label}-${id}.csv"`,
      // Abgeleitete Daten, ändern sich nur mit dem Tageslauf.
      "cache-control": "private, max-age=3600",
    },
  });
}
