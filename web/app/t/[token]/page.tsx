import { loadLanding } from "@/lib/outreach";
import { LandingMissing, LandingView } from "./LandingView";
import "../../landing.css";

// Outreach-Landing: personalisierte, token-adressierte Auswertung je Zielfirma.
// Öffentlich (kein Konto nötig) — der Einstieg in den Vertriebs-Funnel. On-demand gerendert
// (liest die statische outreach.json), daher serverless-fähig ohne Python.
//
// Diese Datei bleibt Server-Komponente: `loadLanding` liest vom Dateisystem. Die Darstellung
// steckt in `LandingView` — sie braucht `useSprache`, und Hooks gibt es nur im Client.

export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const d = await loadLanding(token);

  if (!d) return <LandingMissing />;
  return <LandingView d={d} token={token} />;
}
