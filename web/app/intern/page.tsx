import { InternFirmen } from "@/components/explorer/InternFirmen";
import "../globals.css";
import "../intern.css";

// INTERNES Vertriebstool (Firmen-Radar). Nicht Teil des Kundenprodukts — enthält Kontaktdaten.
// Die API (/api/intern/firmen) blockiert Production; diese Seite ist für den lokalen Gebrauch.
export const metadata = { title: "goVisor — Firmen-Radar (intern)" };

export default function Page() {
  return <InternFirmen />;
}
