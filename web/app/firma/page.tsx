import { Suspense } from "react";
import { FirmaProfil } from "@/components/explorer/FirmaProfil";
import "../explorer.css";
import "../firma.css";

// Feature #25 — Firmenprofil. Eigener Namespace /firma, rollen-agnostisch: dieselbe Firma,
// egal ob als Wettbewerber, Amtsinhaber oder Zuschlags-Gewinner erreicht. Deep-Link ?id=<identity>.
export default function Page() {
  return (
    <Suspense fallback={<div className="fp-load">Lade Firmenprofil …</div>}>
      <FirmaProfil />
    </Suspense>
  );
}
