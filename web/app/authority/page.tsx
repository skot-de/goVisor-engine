import { VergabeblickView } from "@/components/explorer/VergabeblickView";
import "../explorer.css";
import "../vergabeblick.css";

// Vergabestellen-Seite (profile_type = contracting_authority). Eigener Namespace /authority,
// getrennt von der Anbieter-Sicht (/leads …) — „ein Kern, zwei Profile".
export default function Page() {
  return <VergabeblickView />;
}
