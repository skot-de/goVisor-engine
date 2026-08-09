import { StammdatenForm } from "@/components/unternehmen/StammdatenForm";
import "./unternehmen.css";

// #27 Eignungsprofil — Hauptbereich „Unser Unternehmen" (Phase 1: Stammdaten + KMU).
export const metadata = { title: "Unser Unternehmen · goVisor" };

export default function UnternehmenPage() {
  return <StammdatenForm />;
}
