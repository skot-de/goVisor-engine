import { loadLanding } from "@/lib/outreach";
import { LandingMissing, LandingView } from "./LandingView";
import "../../landing.css";

// Outreach-Landing: personalisierte, token-adressierte Auswertung je Zielfirma.
// Öffentlich (kein Konto nötig) — der Einstieg in den Vertriebs-Funnel. On-demand gerendert
// (liest die statische outreach.json), daher serverless-fähig ohne Python.
//
// Diese Datei bleibt Server-Komponente: `loadLanding` liest vom Dateisystem. Die Darstellung
// steckt in `LandingView` — sie braucht `useSprache`, und Hooks gibt es nur im Client.

/* ⚠ NICHT INDIZIEREN. Diese Seite ist oeffentlich, weil sie es sein muss — der Empfaenger
 * soll sie ohne Konto oeffnen koennen. Oeffentlich heisst aber nicht „fuer jeden gedacht":
 * sie zeigt die Auswertung EINER Firma und im Feld `zustellung`, wann wir sie angeschrieben
 * haben und an welche Domain. Ein einziger weitergeleiteter Link genuegt, damit eine
 * Suchmaschine sie einsammelt und dauerhaft anzeigt — und dann steht die Vertriebshistorie
 * im Index, nicht nur beim Empfaenger.
 *
 * `robots.ts` daneben sperrt `/t/` zusaetzlich fuer brave Crawler; diese Kopfzeile gilt auch
 * fuer die, die die robots.txt nicht lesen, und fuer Seiten, die ueber einen Link gefunden
 * werden statt ueber die Wurzel. */
export const metadata = { robots: { index: false, follow: false } };

export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const d = await loadLanding(token);

  if (!d) return <LandingMissing />;
  return <LandingView d={d} token={token} />;
}
