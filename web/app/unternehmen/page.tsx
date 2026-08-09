import { UnternehmenView } from "@/components/unternehmen/UnternehmenView";
import "./unternehmen.css";

// #27 Eignungsprofil — Hauptbereich „Unser Unternehmen": Stammdaten, Anforderungskatalog,
// Referenzen, Zertifikate, Ausschlüsse, Zielrichtung, Rolle, Vorbefüllung, Export.
export const metadata = { title: "Unser Unternehmen · goVisor" };

export default function UnternehmenPage() {
  return <UnternehmenView />;
}
