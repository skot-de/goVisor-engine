import { Suspense } from "react";
import { Vorgangsakte } from "@/components/explorer/Vorgangsakte";
import "../explorer.css";
import "../vorgang.css";

// Die Vorgangsakte. Eigener Namensraum /vorgang, kein Navigationspunkt: erreichbar aus einer
// Vergabe (?lead=<id>) und aus einer Kette heraus (?id=<vorgangsnummer>).
export default function Page() {
  return (
    <Suspense fallback={<div className="vg-load">Lade Vorgang …</div>}>
      <Vorgangsakte />
    </Suspense>
  );
}
