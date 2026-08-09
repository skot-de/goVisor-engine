import { InternClaims } from "@/components/explorer/InternClaims";
import "../../globals.css";
import "../../intern.css";

// INTERN — Prüfung der Identitäts-Ansprüche. Enthält Firmennamen, Domains und Freitexte
// fremder Unternehmen; die API blockiert Production ohne INTERN_ENABLED=1.
export const metadata = { title: "goVisor — Identitäts-Anträge (intern)" };

export default function Page() {
  return <InternClaims />;
}
